from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.routers import sessions as sessions_router
from app.services.attachments import ExtractedAttachment, format_attachments_for_prompt
from app.services.sessions import global_session_store


def setup_function():
    global_session_store.reset()


def test_session_endpoint_returns_clean_502_when_provider_times_out(monkeypatch):
    def timeout_estimate_product(request, **kwargs):
        raise TimeoutError("provider timed out after configured limit")

    monkeypatch.setattr(sessions_router, "estimate_product", timeout_estimate_product)

    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]

    response = client.post(
        f"/sessions/{session_id}/estimate",
        data={
            "transcript": "Project: Atlas CRM. Build FastAPI onboarding with PostgreSQL for a team of 3 engineers.",
            "tier": "pro",
        },
    )

    assert response.status_code == 502
    assert "timed out" in response.json()["detail"].lower()


def test_model_switch_between_turns_keeps_session_history(monkeypatch):
    captured = []

    def fake_estimate_product(request, **kwargs):
        captured.append(kwargs)
        return {
            "text": f"Estimate using tier {kwargs.get('tier')}",
            "prompt_version": kwargs.get("prompt_version", "v1"),
            "requested_tier": kwargs.get("tier") or "flash",
            "served_tier": kwargs.get("tier") or "flash",
            "fallback_used": False,
        }

    monkeypatch.setattr(sessions_router, "estimate_product", fake_estimate_product)

    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]

    first = client.post(
        f"/sessions/{session_id}/estimate",
        data={
            "transcript": "Project: Atlas CRM. Build FastAPI onboarding with PostgreSQL for a team of 3 engineers.",
            "tier": "flash",
        },
    )
    second = client.post(
        f"/sessions/{session_id}/estimate",
        data={
            "transcript": "Keep the same Atlas CRM project and add reporting.",
            "tier": "pro",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert captured[0]["tier"] == "flash"
    assert captured[1]["tier"] == "pro"
    assert any("Atlas CRM" in message["content"] for message in captured[1]["conversation_history"])


def test_attachment_prompt_is_capped_to_prevent_pdf_prompt_bloat():
    formatted = format_attachments_for_prompt(
        [ExtractedAttachment(filename="huge.pdf", text="A" * 30_000)]
    )

    assert "--- attachment: huge.pdf ---" in formatted
    assert len(formatted) < 12_000
    assert "truncated" in formatted.lower()


def test_multiple_attachments_preserve_delimiters_and_order():
    formatted = format_attachments_for_prompt(
        [
            ExtractedAttachment(filename="a.pdf", text="First document"),
            ExtractedAttachment(filename="b.docx", text="Second document"),
        ]
    )

    assert formatted.index("a.pdf") < formatted.index("b.docx")
    assert "--- attachment: a.pdf ---" in formatted
    assert "--- end attachment: a.pdf ---" in formatted
    assert "--- attachment: b.docx ---" in formatted
    assert "--- end attachment: b.docx ---" in formatted


def test_streamlit_uses_backend_timeout_longer_than_observed_provider_slow_path():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")

    assert "BACKEND_CONNECT_TIMEOUT_SECONDS = 10" in source
    assert "BACKEND_READ_TIMEOUT_SECONDS = 240" in source
    assert "timeout=(BACKEND_CONNECT_TIMEOUT_SECONDS, BACKEND_READ_TIMEOUT_SECONDS)" in source
