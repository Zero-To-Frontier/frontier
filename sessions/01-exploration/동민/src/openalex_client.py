"""OpenAlex API에서 Field → Subfield → Topic 계층을 가져온다."""

import os
import time

import requests

from field_model import Field

BASE_URL = "https://api.openalex.org"
MIN_REQUEST_INTERVAL_SECONDS = 0.4
MAX_RATE_LIMIT_RETRIES = 6
_last_request_time = 0.0


def _wait_for_request_slot():
    """제목별 연속 검색이 OpenAlex 요청 제한을 넘지 않도록 속도를 제한한다."""
    global _last_request_time
    wait_seconds = MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_time)
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    _last_request_time = time.monotonic()


def _get(path: str, params: dict | None = None) -> requests.Response:
    """429 응답은 Retry-After를 존중해 재시도하고, 다른 HTTP 오류는 즉시 알린다."""
    request_params = dict(params or {})
    # 연락처를 제공하면 OpenAlex가 요청 출처를 식별하는 데 도움이 된다.
    if mailto := os.environ.get("OPENALEX_MAILTO"):
        request_params["mailto"] = mailto

    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        _wait_for_request_slot()
        response = requests.get(f"{BASE_URL}{path}", params=request_params, timeout=30)
        if response.status_code != 429:
            response.raise_for_status()
            return response

        if attempt == MAX_RATE_LIMIT_RETRIES:
            response.raise_for_status()

        retry_after = response.headers.get("Retry-After")
        try:
            delay_seconds = float(retry_after) if retry_after else 2 ** attempt
        except ValueError:
            delay_seconds = 2 ** attempt
        print(f"OpenAlex 요청 제한: {delay_seconds:.1f}초 후 재시도합니다.")
        time.sleep(delay_seconds)

    raise RuntimeError("OpenAlex 재시도 루프가 예기치 않게 종료되었습니다.")


def _normalize_title(title: str) -> str:
    return " ".join("".join(character.lower() for character in title if character.isalnum() or character.isspace()).split())


def find_work_by_exact_title(title: str) -> dict | None:
    """OpenAlex 검색 결과에서 제목이 정확히 일치하는 Work만 반환한다.

    사이트 목록의 연도는 실제 출판연도와 다를 수 있으므로, 연도 필터를 추가하지 않는다.
    """
    response = _get("/works", {"search": title, "per-page": 10})

    normalized_title = _normalize_title(title)
    for work in response.json().get("results", []):
        candidate_title = work.get("title") or work.get("display_name") or ""
        if _normalize_title(candidate_title) == normalized_title:
            return work
    return None


def get_field_by_name(field_name: str) -> dict | None:
    response = _get("/fields", {"search": field_name})

    for field in response.json()["results"]:
        if field["display_name"].lower() == field_name.lower():
            return field
    return None


def get_subfield_detail(subfield_id: str) -> dict:
    short_id = subfield_id.rsplit("/", 1)[-1]
    response = _get(f"/subfields/{short_id}")
    return response.json()


def fetch_field_hierarchy(field_name: str) -> tuple[Field, list[tuple[Field, list[Field]]]] | None:
    """이름으로 Field를 찾고, 그 하위 Subfield와 Topic을 반환한다."""
    field_data = get_field_by_name(field_name)
    if field_data is None:
        return None

    root = Field(field_data["id"], field_data["display_name"], "field")
    hierarchy = []
    for subfield_data in field_data.get("subfields", []):
        detail = get_subfield_detail(subfield_data["id"])
        subfield = Field(detail["id"], detail["display_name"], "subfield")
        topics = [
            Field(topic["id"], topic["display_name"], "topic")
            for topic in detail.get("topics", [])
        ]
        hierarchy.append((subfield, topics))

    return root, hierarchy
