"""KAIST 김재철AI대학원 연도별 논문 페이지 수집기."""

import base64
import json
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable

import requests

KAIST_PUBLICATIONS_URL = "https://gsai.kaist.ac.kr/publication-research-year/?lang=ko"
KAIST_AJAX_URL = "https://gsai.kaist.ac.kr/wp-admin/admin-ajax.php"


@dataclass(frozen=True)
class KaistPublication:
    """KAIST 사이트에 실린 논문 항목."""

    listing_year: int
    title: str
    source_url: str | None


class _PublicationPageParser(HTMLParser):
    """외부 의존성 없이 KAIST 페이지의 논문 제목과 Load More 설정을 읽는다."""

    def __init__(self, default_year: int | None = None):
        super().__init__(convert_charrefs=True)
        self.current_year = default_year
        self.publications: list[KaistPublication] = []
        self.load_more_params: dict[int, dict] = {}
        self._in_year_heading = False
        self._in_article = False
        self._in_title_container = False
        self._in_title_anchor = False
        self._article_title_parts: list[str] = []
        self._article_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attributes = dict(attrs)
        classes = attributes.get("class") or ""

        if tag == "div" and "ctu-ultimate-style-heading" in classes:
            self._in_year_heading = True
        elif tag == "article":
            self._in_article = True
            self._article_title_parts = []
            self._article_url = None
        elif tag == "div" and "gem-news-item-title" in classes:
            self._in_title_container = True
        elif tag == "a" and self._in_title_container:
            self._in_title_anchor = True
            self._article_url = attributes.get("href") or None
        elif tag == "button" and "gsai-blogs-load-more" in classes and self.current_year:
            encoded = attributes.get("data-ajax_default_params")
            if encoded:
                decoded = base64.b64decode(encoded).decode("utf-8")
                self.load_more_params[self.current_year] = json.loads(decoded)

    def handle_data(self, data: str):
        value = data.strip()
        if self._in_year_heading and value.isdigit() and len(value) == 4:
            self.current_year = int(value)
        if self._in_title_anchor and value:
            self._article_title_parts.append(value)

    def handle_endtag(self, tag: str):
        if tag == "a":
            self._in_title_anchor = False
        elif tag == "div" and self._in_title_container:
            self._in_title_container = False
        elif tag == "div" and self._in_year_heading:
            self._in_year_heading = False
        elif tag == "article":
            title = " ".join(self._article_title_parts).strip()
            if self.current_year and title:
                self.publications.append(KaistPublication(
                    listing_year=self.current_year,
                    title=title,
                    source_url=self._article_url,
                ))
            self._in_article = False


def _parse_publications(html: str, default_year: int | None = None) -> _PublicationPageParser:
    parser = _PublicationPageParser(default_year)
    parser.feed(html)
    return parser


class KaistPublicationClient:
    """KAIST 사이트의 초기 목록과 Load More 페이지를 모두 읽는다."""

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()

    def fetch_publications(self, years: Iterable[int]) -> list[KaistPublication]:
        target_years = set(years)
        response = self._session.get(KAIST_PUBLICATIONS_URL, timeout=30)
        response.raise_for_status()
        page = _parse_publications(response.text)

        publications = [
            publication for publication in page.publications
            if publication.listing_year in target_years
        ]
        for year in target_years:
            params = page.load_more_params.get(year)
            if not params:
                continue
            publications.extend(self._fetch_remaining_pages(year, params))

        # 사이트 목록에 같은 게시물이 중복되어도 한 번만 OpenAlex에서 찾도록 한다.
        return list(dict.fromkeys(publications))

    def _fetch_remaining_pages(self, year: int, params: dict) -> list[KaistPublication]:
        next_page = 2
        publications = []
        while next_page:
            payload = {
                "action": "gsai_blog_load_more",
                "data[paged]": str(next_page),
                "data[categories]": params["categories"],
                "data[post_type]": params["post_type"],
                "data[posts_per_page]": params["posts_per_page"],
                "data[hide_comments]": str(params.get("hide_comments", 1)),
            }
            response = self._session.post(KAIST_AJAX_URL, data=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            if result.get("status") != "success":
                raise RuntimeError(f"KAIST 논문 추가 목록 수집 실패: {result}")

            page = _parse_publications(result.get("html", ""), default_year=year)
            publications.extend(page.publications)
            # 서버가 숫자 대신 문자열 "0"을 보낼 수 있으므로 정수로 정규화한다.
            next_page = int(result.get("next_page") or 0)
        return publications
