from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.routers import sessions as sessions_router
from app.services.sessions import global_session_store

REQUIRED_TURN_OBSERVED_FIELDS = {
    "turn_index",
    "session_id",
    "enriched_transcript_chars",
    "attachments_total_chars",
    "messages_in_window",
    "anchors_count",
    "summary_chars",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "latency_ms",
    "cache_hit_kind",
    "last_resolved_tier",
}

VALID_TRANSCRIPT = (
    "Project: Atlas CRM. Build FastAPI onboarding with PostgreSQL reporting, "
    "role approvals, and email notifications for a team of 3 engineers."
)


def make_docx_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def setup_function():
    global_session_store.reset()


def fake_estimate_product(request, **kwargs):
    return {
        "prompt_version": kwargs.get("prompt_version", "v1"),
        "text": "Estimate for Atlas CRM using FastAPI and PostgreSQL.",
        "requested_tier": kwargs.get("tier") or "flash",
        "served_tier": kwargs.get("tier") or "flash",
        "fallback_used": False,
        "input_tokens": 321,
        "output_tokens": 123,
        "cost_usd": 0.00042,
        "cached": False,
        "cache_backend": "redis",
    }


def test_session_estimate_exposes_turn_observed_with_exact_required_fields(monkeypatch):
    monkeypatch.setattr(sessions_router, "estimate_product", fake_estimate_product)
    monkeypatch.setattr(sessions_router.settings, "stress_fake_provider", False)
    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]

    response = client.post(f"/sessions/{session_id}/estimate", data={"transcript": VALID_TRANSCRIPT})

    assert response.status_code == 200
    observation = response.json()["turn_observed"]
    assert set(observation) == REQUIRED_TURN_OBSERVED_FIELDS
    assert observation["turn_index"] == 1
    assert observation["session_id"] == session_id
    assert observation["tokens_in"] == 321
    assert observation["tokens_out"] == 123
    assert observation["cost_usd"] == 0.00042
    assert observation["cache_hit_kind"] in {"none", "exact", "semantic"}
    assert observation["anchors_count"] == 0
    assert observation["summary_chars"] == 0


def test_session_debug_endpoint_exposes_last_turn_observed(monkeypatch):
    monkeypatch.setattr(sessions_router, "estimate_product", fake_estimate_product)
    monkeypatch.setattr(sessions_router.settings, "stress_fake_provider", False)
    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]

    response = client.post(f"/sessions/{session_id}/estimate", data={"transcript": VALID_TRANSCRIPT})
    snapshot = client.get(f"/sessions/{session_id}")

    assert response.status_code == 200
    assert snapshot.status_code == 200
    assert snapshot.json()["last_turn_observed"] == response.json()["turn_observed"]
    assert snapshot.json()["anchors_count"] == 0
    assert snapshot.json()["summary_chars"] == 0


def test_turn_observed_attachment_chars_are_non_zero(monkeypatch):
    monkeypatch.setattr(sessions_router, "estimate_product", fake_estimate_product)
    monkeypatch.setattr(sessions_router.settings, "stress_fake_provider", False)
    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]

    response = client.post(
        f"/sessions/{session_id}/estimate",
        data={"transcript": VALID_TRANSCRIPT},
        files={
            "attachments": (
                "scope.docx",
                make_docx_bytes("ATTACHMENT_FACT_5KB: add HubSpot CRM integration."),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    observation = response.json()["turn_observed"]
    assert observation["attachments_total_chars"] > 0
    assert observation["enriched_transcript_chars"] > len(VALID_TRANSCRIPT)


def test_exact_cache_hit_kind_is_reported(monkeypatch):
    def cached_estimate_product(request, **kwargs):
        payload = fake_estimate_product(request, **kwargs)
        payload["cached"] = True
        return payload

    monkeypatch.setattr(sessions_router, "estimate_product", cached_estimate_product)
    monkeypatch.setattr(sessions_router.settings, "stress_fake_provider", False)
    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]

    response = client.post(f"/sessions/{session_id}/estimate", data={"transcript": VALID_TRANSCRIPT})

    assert response.status_code == 200
    assert response.json()["turn_observed"]["cache_hit_kind"] == "exact"
