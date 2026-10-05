"""KAIST 김재철AI대학원 2024~2026 논문을 OpenAlex를 거쳐 Neo4j에 저장한다."""

import os

from kaist_publication_client import KaistPublicationClient
from config import load_environment
from neo4j_repository import Neo4jFieldRepository
from openalex_client import find_work_by_exact_title
from paper_model import paper_graph_from_openalex

TARGET_YEARS = (2026, 2025, 2024)


def main():
    load_environment()
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD 환경 변수를 설정하세요.")

    publications = KaistPublicationClient().fetch_publications(TARGET_YEARS)
    repository = Neo4jFieldRepository(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        os.environ.get("NEO4J_USERNAME", "neo4j"),
        password,
    )

    saved_count = 0
    not_found_titles = []
    try:
        for publication in publications:
            work = find_work_by_exact_title(publication.title)
            if work is None:
                not_found_titles.append(publication.title)
                print(f"[미발견] {publication.title}")
                continue

            paper, topics, authorships = paper_graph_from_openalex(work)
            repository.save_paper(paper, topics, authorships)
            saved_count += 1
            print(f"[저장] {paper.title}")
    finally:
        repository.close()

    print(f"완료: {saved_count}/{len(publications)}편 저장")
    if not_found_titles:
        print("OpenAlex에서 정확히 일치하는 제목을 찾지 못한 논문:")
        for title in not_found_titles:
            print(f"- {title}")


if __name__ == "__main__":
    main()
