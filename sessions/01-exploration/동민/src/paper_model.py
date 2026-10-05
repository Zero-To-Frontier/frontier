"""논문 도메인 모델과 OpenAlex Work 객체 변환 로직."""

from dataclasses import dataclass

from author_model import Authorship, authorships_from_openalex
from field_model import Field


@dataclass(frozen=True)
class Paper:
    """검색 및 LLM 근거 제공에 필요한 논문 메타데이터."""

    openalex_id: str
    title: str
    publication_year: int | None
    publication_date: str | None
    doi: str | None
    landing_page_url: str | None
    pdf_url: str | None
    abstract: str | None
    paper_type: str | None
    language: str | None
    cited_by_count: int
    is_open_access: bool
    oa_status: str | None
    updated_date: str | None


@dataclass(frozen=True)
class TopicAssignment:
    """논문과 OpenAlex Topic 간의 관련도."""

    topic: Field
    score: float | None


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    """OpenAlex의 abstract_inverted_index를 일반 텍스트 초록으로 복원한다."""
    if not inverted_index:
        return None

    positioned_words = [
        (position, word)
        for word, positions in inverted_index.items()
        for position in positions
    ]
    return " ".join(word for _, word in sorted(positioned_words))


def paper_from_openalex(work: dict) -> tuple[Paper, list[TopicAssignment]]:
    """OpenAlex Work API 응답을 Paper 및 TopicAssignment로 변환한다."""
    primary_location = work.get("primary_location") or {}
    best_oa_location = work.get("best_oa_location") or {}
    open_access = work.get("open_access") or {}

    paper = Paper(
        openalex_id=work["id"],
        title=work.get("title") or work.get("display_name") or "",
        publication_year=work.get("publication_year"),
        publication_date=work.get("publication_date"),
        doi=work.get("doi"),
        landing_page_url=primary_location.get("landing_page_url"),
        pdf_url=(best_oa_location.get("pdf_url") or primary_location.get("pdf_url")),
        abstract=reconstruct_abstract(work.get("abstract_inverted_index")),
        paper_type=work.get("type"),
        language=work.get("language"),
        cited_by_count=work.get("cited_by_count", 0),
        is_open_access=open_access.get("is_oa", False),
        oa_status=open_access.get("oa_status"),
        updated_date=work.get("updated_date"),
    )
    topic_assignments = [
        TopicAssignment(
            topic=Field(topic["id"], topic["display_name"], "topic"),
            score=topic.get("score"),
        )
        for topic in work.get("topics", [])
    ]
    return paper, topic_assignments


def paper_graph_from_openalex(
    work: dict,
) -> tuple[Paper, list[TopicAssignment], list[Authorship]]:
    """OpenAlex Work 응답을 논문 저장에 필요한 모든 도메인 객체로 변환한다."""
    paper, topic_assignments = paper_from_openalex(work)
    return paper, topic_assignments, authorships_from_openalex(work)
