"""저자 도메인 모델과 OpenAlex authorships 변환 로직."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Author:
    """OpenAlex 저자의 최소 식별 정보."""

    openalex_id: str
    display_name: str
    orcid: str | None


@dataclass(frozen=True)
class Authorship:
    """특정 논문에서 한 저자의 역할."""

    author: Author
    author_position: str | None


def authorships_from_openalex(work: dict) -> list[Authorship]:
    """OpenAlex Work의 authorships를 Author 및 저자 역할 목록으로 변환한다."""
    authorships = []
    for authorship_data in work.get("authorships", []):
        author_data = authorship_data.get("author") or {}
        author_id = author_data.get("id")
        if not author_id:
            # OpenAlex 저자 ID가 없는 원시 저자명은 동일 인물 식별이 불가능하므로 제외한다.
            continue

        authorships.append(Authorship(
            author=Author(
                openalex_id=author_id,
                display_name=author_data.get("display_name") or "",
                orcid=author_data.get("orcid"),
            ),
            author_position=authorship_data.get("author_position"),
        ))
    return authorships
