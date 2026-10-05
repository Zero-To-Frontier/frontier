"""프로젝트 루트의 .env 설정을 불러온다."""

from pathlib import Path

from dotenv import load_dotenv


def load_environment():
    """명시적으로 설정된 환경변수는 유지하고, 없는 값만 .env에서 채운다."""
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env", override=False)
