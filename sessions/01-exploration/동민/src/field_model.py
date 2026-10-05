from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    """OpenAlex 분류 체계의 모든 계층(Field/Subfield/Topic)을 표현한다."""

    openalex_id: str
    name: str
    level: str
