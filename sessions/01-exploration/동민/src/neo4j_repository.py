"""논문 분야 온톨로지를 Neo4j에 저장한다."""

from typing import Iterable

from neo4j import GraphDatabase

from author_model import Authorship
from field_model import Field
from paper_model import Paper, TopicAssignment


class Neo4jFieldRepository:
    """Field 노드와 부모-자식 관계를 Neo4j에 저장한다."""

    def __init__(self, uri: str, username: str, password: str):
        self._driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        self._driver.close()

    def save_hierarchy(self, root: Field, subfields: Iterable[tuple[Field, list[Field]]]):
        """계층을 멱등적으로 저장한다."""
        rows = []
        for subfield, topics in subfields:
            rows.append({
                "parent_id": root.openalex_id,
                "child_id": subfield.openalex_id,
                "child_name": subfield.name,
                "child_level": subfield.level,
            })
            rows.extend({
                "parent_id": subfield.openalex_id,
                "child_id": topic.openalex_id,
                "child_name": topic.name,
                "child_level": topic.level,
            } for topic in topics)

        # 스키마 변경은 데이터 쓰기 트랜잭션과 함께 실행할 수 없다.
        # 별도 자동 커밋 쿼리로 먼저 제약조건을 보장한다.
        self._ensure_schema()
        with self._driver.session() as session:
            session.execute_write(self._save, root, rows)

    def _ensure_schema(self):
        with self._driver.session() as session:
            session.run(
                "CREATE CONSTRAINT field_openalex_id IF NOT EXISTS "
                "FOR (f:Field) REQUIRE f.openalex_id IS UNIQUE"
            ).consume()
            session.run(
                "CREATE CONSTRAINT paper_openalex_id IF NOT EXISTS "
                "FOR (p:Paper) REQUIRE p.openalex_id IS UNIQUE"
            ).consume()
            session.run(
                "CREATE CONSTRAINT author_openalex_id IF NOT EXISTS "
                "FOR (a:Author) REQUIRE a.openalex_id IS UNIQUE"
            ).consume()

    def save_paper(
        self,
        paper: Paper,
        topic_assignments: Iterable[TopicAssignment],
        authorships: Iterable[Authorship] = (),
    ):
        """논문과 Topic·Author 관계를 멱등적으로 저장한다."""
        topic_rows = [
            {
                "id": assignment.topic.openalex_id,
                "name": assignment.topic.name,
                "score": assignment.score,
            }
            for assignment in topic_assignments
        ]
        author_rows = [
            {
                "id": authorship.author.openalex_id,
                "display_name": authorship.author.display_name,
                "orcid": authorship.author.orcid,
                "author_position": authorship.author_position,
            }
            for authorship in authorships
        ]

        self._ensure_schema()
        with self._driver.session() as session:
            session.execute_write(self._save_paper, paper, topic_rows, author_rows)

    @staticmethod
    def _save(tx, root: Field, rows: list[dict]):
        tx.run(
            "MERGE (f:Field {openalex_id: $id}) "
            "SET f.name = $name, f.level = $level",
            id=root.openalex_id, name=root.name, level=root.level,
        ).consume()
        tx.run(
            "UNWIND $rows AS row "
            "MERGE (parent:Field {openalex_id: row.parent_id}) "
            "MERGE (child:Field {openalex_id: row.child_id}) "
            "SET child.name = row.child_name, child.level = row.child_level "
            "MERGE (parent)-[:HAS_CHILD]->(child)",
            rows=rows,
        ).consume()

    @staticmethod
    def _save_paper(
        tx,
        paper: Paper,
        topic_rows: list[dict],
        author_rows: list[dict],
    ):
        tx.run(
            "MERGE (p:Paper {openalex_id: $openalex_id}) "
            "SET p.title = $title, "
            "    p.publication_year = $publication_year, "
            "    p.publication_date = $publication_date, "
            "    p.doi = $doi, "
            "    p.landing_page_url = $landing_page_url, "
            "    p.pdf_url = $pdf_url, "
            "    p.abstract = $abstract, "
            "    p.paper_type = $paper_type, "
            "    p.language = $language, "
            "    p.cited_by_count = $cited_by_count, "
            "    p.is_open_access = $is_open_access, "
            "    p.oa_status = $oa_status, "
            "    p.updated_date = $updated_date",
            **paper.__dict__,
        ).consume()
        tx.run(
            "MATCH (p:Paper {openalex_id: $paper_id}) "
            "UNWIND $topics AS topic_row "
            "MERGE (topic:Field {openalex_id: topic_row.id}) "
            "SET topic.name = topic_row.name, topic.level = 'topic' "
            "MERGE (p)-[r:HAS_TOPIC]->(topic) "
            "SET r.score = topic_row.score",
            paper_id=paper.openalex_id,
            topics=topic_rows,
        ).consume()
        tx.run(
            "MATCH (p:Paper {openalex_id: $paper_id}) "
            "UNWIND $authors AS author_row "
            "MERGE (author:Author {openalex_id: author_row.id}) "
            "SET author.display_name = author_row.display_name, "
            "    author.orcid = author_row.orcid "
            "MERGE (p)-[r:AUTHORED_BY]->(author) "
            "SET r.author_position = author_row.author_position",
            paper_id=paper.openalex_id,
            authors=author_rows,
        ).consume()
