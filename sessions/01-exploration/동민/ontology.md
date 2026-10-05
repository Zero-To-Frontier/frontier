# 논문 분야 온톨로지

OpenAlex의 `Field → Subfield → Topic`을 Neo4j의 동일한 `:Field` 노드로 저장한다.
계층은 `(:Field)-[:HAS_CHILD]->(:Field)` 관계로 표현하며, `level` 속성은
`field`, `subfield`, `topic` 중 하나다.

## 실행

프로젝트 루트에서 `.env.example`을 `.env`로 복사한 뒤 Neo4j 접속 정보를 설정한다.

```powershell
Copy-Item .env.example .env
# .env 파일에서 NEO4J_PASSWORD 값을 실제 비밀번호로 변경
pip install -r requirements.txt
python src/ingest_field_hierarchy.py
```


## 코드 구성

- `src/openalex_client.py`: OpenAlex API 호출과 `Field → Subfield → Topic` 수집
- `src/neo4j_repository.py`: Neo4j 노드·관계 저장
- `src/field_model.py`: 두 모듈이 공유하는 `Field` 모델
- `src/paper_model.py`: `Paper` 모델, OpenAlex Work 응답 변환 및 초록 복원
- `src/author_model.py`: 최소 `Author` 모델과 저자 역할 변환
- `src/ingest_field_hierarchy.py`: 분야 계층 수집·저장 실행 진입점
- `src/kaist_publication_client.py`: KAIST 연도별 논문 목록 수집
- `src/ingest_kaist_publications.py`: KAIST 목록을 OpenAlex·Neo4j에 저장

## 논문 저장

OpenAlex Work 응답(`dict`)을 `Paper`와 Topic 관계로 변환한 뒤 저장한다.

```python
from neo4j_repository import Neo4jFieldRepository
from paper_model import paper_graph_from_openalex

paper, topic_assignments, authorships = paper_graph_from_openalex(openalex_work)
repository.save_paper(paper, topic_assignments, authorships)
```

`Paper`는 OpenAlex ID를 키로 `MERGE`되며, Topic은
`(:Paper)-[:HAS_TOPIC {score}]->(:Field {level: "topic"})`로 저장된다.
저자는 `(:Paper)-[:AUTHORED_BY {author_position}]->(:Author)`로 저장된다.

## KAIST 김재철AI대학원 논문 수집

아래 명령은 [KAIST 논문 목록](https://gsai.kaist.ac.kr/publication-research-year/?lang=ko)의
2024·2025·2026년 항목 전체를 가져온다. 각 제목과 정확히 일치하는 OpenAlex Work만
저장하며, 일치하지 않는 제목은 저장하지 않고 마지막에 출력한다.

```powershell
python src/ingest_kaist_publications.py
```

OpenAlex 요청 제한을 피하기 위해 제목 검색은 초당 약 2.5건으로 제한되며,
429 응답을 받으면 서버가 지정한 시간만큼 대기 후 자동 재시도한다. 선택 사항으로
연락처를 설정할 수 있다.

```powershell
$env:OPENALEX_MAILTO = "your-email@example.com"
```

## 분야명으로 하위 주제 검색

```cypher
MATCH (start:Field)
WHERE toLower(start.name) CONTAINS toLower($keyword)
OPTIONAL MATCH (start)-[:HAS_CHILD*0..]->(descendant:Field)
RETURN start.name AS matched_field,
       collect(DISTINCT {name: descendant.name, level: descendant.level}) AS descendants
```
