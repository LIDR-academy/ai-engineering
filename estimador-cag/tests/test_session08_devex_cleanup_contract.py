import json
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEVCONTAINER = REPO_ROOT / ".devcontainer" / "devcontainer.json"
SETUP_SCRIPT = REPO_ROOT / ".devcontainer" / "setup-estimador.sh"
PYPROJECT = REPO_ROOT / "estimador-cag" / "pyproject.toml"


def test_devcontainer_exports_non_paging_terminal_defaults() -> None:
    config = json.loads(DEVCONTAINER.read_text(encoding="utf-8"))

    remote_env = config["remoteEnv"]

    assert remote_env["GIT_PAGER"] == "cat"
    assert remote_env["PAGER"] == "cat"
    assert remote_env["LESS"] == "FRX"
    assert config["customizations"]["vscode"]["settings"]["terminal.integrated.defaultProfile.linux"] == "zsh"


def test_setup_script_installs_idempotent_zsh_and_bash_pager_defaults() -> None:
    script = SETUP_SCRIPT.read_text(encoding="utf-8")

    assert "SESSION08_PAGER_DEFAULTS_START" in script
    assert "SESSION08_PAGER_DEFAULTS_END" in script
    assert "export GIT_PAGER=cat" in script
    assert "export PAGER=cat" in script
    assert "export LESS=FRX" in script
    assert ".zshrc" in script
    assert ".bashrc" in script


def test_sentence_transformers_is_optional_not_core_runtime_dependency() -> None:
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    dependencies = "\n".join(pyproject["project"]["dependencies"])
    optional = pyproject["project"]["optional-dependencies"]

    assert "sentence-transformers" not in dependencies
    assert "local-embeddings" in optional
    assert any("sentence-transformers>=3.3.0" in item for item in optional["local-embeddings"])
