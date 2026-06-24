from pathlib import Path


def test_redis_dependency_is_declared_in_pyproject():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert '"redis>=' in pyproject


def test_docker_compose_declares_redis_service():
    candidates = [
        Path("docker-compose.yml"),
        Path("../docker-compose.yml"),
    ]
    compose_files = [path for path in candidates if path.exists()]

    assert compose_files, "Expected docker-compose.yml in project root or repository root."

    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in compose_files)

    assert "redis:" in combined
    assert "6379" in combined
