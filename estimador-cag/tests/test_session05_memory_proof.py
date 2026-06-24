from fastapi.testclient import TestClient

from app.main import app
from app.routers import sessions as sessions_router
from app.services.sessions import global_session_store

VALID_FIRST_TURN = (
    "Project: Atlas CRM. The client needs a FastAPI and PostgreSQL onboarding "
    "platform with role approvals for a team of 3 engineers."
)


def setup_function():
    global_session_store.reset()


def fake_estimate_product(request, **kwargs):
    return {
        "prompt_version": kwargs.get("prompt_version", "v1"),
        "text": "Estimate for Atlas CRM using FastAPI, PostgreSQL, and a team of 3 engineers.",
        "requested_tier": kwargs.get("tier") or "flash",
        "served_tier": kwargs.get("tier") or "flash",
        "fallback_used": False,
    }


def test_second_turn_sends_previous_turn_history_to_estimator(monkeypatch):
    captured_calls = []

    def capturing_estimate_product(request, **kwargs):
        captured_calls.append({"request": request, "kwargs": kwargs})
        return fake_estimate_product(request, **kwargs)

    monkeypatch.setattr(sessions_router, "estimate_product", capturing_estimate_product)

    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]

    first = client.post(
        f"/sessions/{session_id}/estimate",
        data={"transcript": VALID_FIRST_TURN},
    )
    second = client.post(
        f"/sessions/{session_id}/estimate",
        data={"transcript": "Can reporting stay in phase two while keeping the same scope?"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(captured_calls) == 2

    first_history = captured_calls[0]["kwargs"].get("conversation_history")
    second_history = captured_calls[1]["kwargs"].get("conversation_history")

    assert first_history == []
    assert second_history
    assert second_history[0]["role"] == "user"
    assert "Atlas CRM" in second_history[0]["content"]
    assert second_history[1]["role"] == "assistant"
    assert "Atlas CRM" in second_history[1]["content"]


def test_effective_history_sent_to_estimator_never_exceeds_max_turns(monkeypatch):
    captured_histories = []

    def capturing_estimate_product(request, **kwargs):
        captured_histories.append(kwargs.get("conversation_history") or [])
        return fake_estimate_product(request, **kwargs)

    monkeypatch.setattr(sessions_router, "estimate_product", capturing_estimate_product)

    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]

    for index in range(8):
        response = client.post(
            f"/sessions/{session_id}/estimate",
            data={
                "transcript": (
                    f"Project: Atlas CRM. Turn {index}. Build FastAPI and PostgreSQL "
                    "onboarding for a team of 3 engineers."
                )
            },
        )
        assert response.status_code == 200

    last_history = captured_histories[-1]
    assert len(last_history) <= 12
    assert not any("Turn 0" in message["content"] for message in last_history)
    assert any("Turn 2" in message["content"] for message in last_history)


def test_two_sessions_keep_independent_project_metadata_and_history(monkeypatch):
    captured_calls = []

    def capturing_estimate_product(request, **kwargs):
        captured_calls.append({"description": request.description, "kwargs": kwargs})
        return {
            "prompt_version": kwargs.get("prompt_version", "v1"),
            "text": f"Estimate for {request.description}",
            "requested_tier": kwargs.get("tier") or "flash",
            "served_tier": kwargs.get("tier") or "flash",
            "fallback_used": False,
        }

    monkeypatch.setattr(sessions_router, "estimate_product", capturing_estimate_product)

    client = TestClient(app)

    session_a = client.post("/sessions").json()["session_id"]
    session_b = client.post("/sessions").json()["session_id"]

    response_a1 = client.post(
        f"/sessions/{session_a}/estimate",
        data={
            "transcript": (
                "Project: Atlas CRM. Build FastAPI onboarding with PostgreSQL "
                "for a team of 3 engineers."
            )
        },
    )
    response_b1 = client.post(
        f"/sessions/{session_b}/estimate",
        data={
            "transcript": (
                "Project: Boreal ERP. Build Spring Boot invoicing with PostgreSQL "
                "for a team of 5 engineers."
            )
        },
    )
    response_a2 = client.post(
        f"/sessions/{session_a}/estimate",
        data={"transcript": "Keep the same Atlas CRM scope and add reporting."},
    )

    assert response_a1.status_code == 200
    assert response_b1.status_code == 200
    assert response_a2.status_code == 200

    payload_a2 = response_a2.json()
    payload_b1 = response_b1.json()

    assert payload_a2["project_metadata"]["project_name"] == "Atlas CRM"
    assert payload_b1["project_metadata"]["project_name"] == "Boreal ERP"

    assert payload_a2["history_turns"] == 2
    assert payload_b1["history_turns"] == 1

    second_atlas_call_history = captured_calls[2]["kwargs"].get("conversation_history") or []
    assert any("Atlas CRM" in message["content"] for message in second_atlas_call_history)
    assert not any("Boreal ERP" in message["content"] for message in second_atlas_call_history)
