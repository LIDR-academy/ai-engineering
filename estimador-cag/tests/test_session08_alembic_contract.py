from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = REPO_ROOT / "estimador-cag"


def test_session08_alembic_files_exist() -> None:
    assert (PROJECT_ROOT / "alembic.ini").is_file()
    assert (PROJECT_ROOT / "alembic" / "env.py").is_file()
    assert (PROJECT_ROOT / "alembic" / "script.py.mako").is_file()
    assert (PROJECT_ROOT / "alembic" / "versions").is_dir()


def test_session08_alembic_reads_database_url_from_environment() -> None:
    env_py = (PROJECT_ROOT / "alembic" / "env.py").read_text(encoding="utf-8")

    assert "DATABASE_URL" in env_py
    assert "os.environ" in env_py or "os.getenv" in env_py
    assert "sqlalchemy.url" in env_py


def test_session08_alembic_registers_pgvector_type_for_reflection() -> None:
    env_py = (PROJECT_ROOT / "alembic" / "env.py").read_text(encoding="utf-8")

    assert "pgvector.sqlalchemy" in env_py
    assert 'ischema_names["vector"]' in env_py
    assert "Vector" in env_py


def test_session08_alembic_uses_async_engine() -> None:
    env_py = (PROJECT_ROOT / "alembic" / "env.py").read_text(encoding="utf-8")

    assert "async_engine_from_config" in env_py
    assert "asyncio.run" in env_py
