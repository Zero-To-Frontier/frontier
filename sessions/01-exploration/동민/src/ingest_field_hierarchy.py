"""OpenAlex에서 분야 계층을 가져와 Neo4j에 저장하는 실행 진입점."""

import os

from config import load_environment
from neo4j_repository import Neo4jFieldRepository
from openalex_client import fetch_field_hierarchy


def main():
    load_environment()
    hierarchy = fetch_field_hierarchy("Computer Science")
    if hierarchy is None:
        print("Computer Science field를 찾지 못했습니다.")
        return

    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD 환경 변수를 설정하세요.")

    root, subfields = hierarchy
    repository = Neo4jFieldRepository(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        os.environ.get("NEO4J_USERNAME", "neo4j"),
        password,
    )
    try:
        repository.save_hierarchy(root, subfields)
    finally:
        repository.close()

    topic_count = sum(len(topics) for _, topics in subfields)
    print(f"'{root.name}' 계층을 Neo4j에 저장했습니다. "
          f"(subfields: {len(subfields)}, topics: {topic_count})")


if __name__ == "__main__":
    main()
