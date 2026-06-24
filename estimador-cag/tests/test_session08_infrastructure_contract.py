import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = REPO_ROOT / "estimador-cag"


def test_session08_compose_declares_pgvector_postgres_service() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert re.search(r"(?m)^  postgres:\s*$", compose)
    assert "image: pgvector/pgvector:pg16" in compose
    assert "POSTGRES_DB: estimator" in compose
    assert "POSTGRES_USER: estimator" in compose
    assert "POSTGRES_PASSWORD: estimator" in compose
    assert '"5432:5432"' in compose
    assert "postgres_data:/var/lib/postgresql/data" in compose
    assert 'pg_isready -U estimator -d estimator' in compose


def test_session08_compose_keeps_existing_redis_service() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert re.search(r"(?m)^  redis:\s*$", compose)
    assert "image: redis:7-alpine" in compose


def test_session08_database_dependencies_are_declared() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = "\n".join(pyproject["project"]["dependencies"])

    assert "sqlalchemy>=2.0" in dependencies
    assert "asyncpg>=0.29" in dependencies
    assert "pgvector>=0.3" in dependencies
    assert "alembic>=1.13" in dependencies
