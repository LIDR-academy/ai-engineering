from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app
from app.routers import sessions as sessions_router
from app.services.sessions import global_session_store

VALID_TRANSCRIPT = (
    "Project: Atlas CRM. The client needs a FastAPI and PostgreSQL onboarding "
    "platform with role approvals, reporting, and email notifications for a team of 3 engineers."
)


def fake_estimate_product(request, **kwargs):
    return {
        "prompt_version": kwargs.get("prompt_version", "v1"),
        "text": "Estimate for Atlas CRM using FastAPI and PostgreSQL with a team of 3 engineers.",
        "requested_tier": kwargs.get("tier") or "flash",
        "served_tier": kwargs.get("tier") or "flash",
        "fallback_used": False,
    }


def setup_function():
    global_session_store.reset()


def test_post_sessions_returns_uuid_v4():
    client = TestClient(app)
    response = client.post("/sessions")
    assert response.status_code == 200
    assert UUID(response.json()["session_id"]).version == 4


def test_unknown_session_returns_404():
    client = TestClient(app)
    response = client.post("/sessions/does-not-exist/estimate", data={"transcript": VALID_TRANSCRIPT})
    assert response.status_code == 404


def test_session_links_two_requests_and_updates_project_metadata(monkeypatch):
    monkeypatch.setattr(sessions_router, "estimate_product", fake_estimate_product)
    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]
    first = client.post(f"/sessions/{session_id}/estimate", data={"transcript": VALID_TRANSCRIPT})
    second = client.post(
        f"/sessions/{session_id}/estimate",
        data={"transcript": "Add a Stripe billing module and keep the same Atlas CRM scope. Can reporting stay in phase two?"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    payload = second.json()
    assert payload["session_id"] == session_id
    assert payload["history_turns"] == 2
    assert payload["project_metadata"]["project_name"] == "Atlas CRM"
    assert "FastAPI" in payload["project_metadata"]["mentioned_technologies"]
    assert "PostgreSQL" in payload["project_metadata"]["mentioned_technologies"]
    assert "Stripe" in payload["project_metadata"]["mentioned_technologies"]
    assert payload["project_metadata"]["assumed_team_size"] == 3


def test_session_history_respects_max_turns(monkeypatch):
    monkeypatch.setattr(sessions_router, "estimate_product", fake_estimate_product)
    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]
    for index in range(8):
        response = client.post(
            f"/sessions/{session_id}/estimate",
            data={"transcript": f"Project: Atlas CRM. Turn {index}. Build FastAPI reporting and PostgreSQL storage for a team of 3 engineers."},
        )
        assert response.status_code == 200
    payload = response.json()
    assert payload["history_turns"] == 6
    assert payload["max_history_turns"] == 6


def test_unsupported_attachment_type_returns_400(monkeypatch):
    monkeypatch.setattr(sessions_router, "estimate_product", fake_estimate_product)
    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]
    response = client.post(
        f"/sessions/{session_id}/estimate",
        data={"transcript": VALID_TRANSCRIPT},
        files={"attachments": ("notes.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported attachment type" in response.json()["detail"]
