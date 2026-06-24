from fastapi.testclient import TestClient

from app.main import app
from app.routers import sessions as sessions_router
from app.schemas.estimation import EstimationResult
from app.services.sessions import global_session_store


def setup_function():
    global_session_store.reset()


def fake_structured_result(summary: str) -> EstimationResult:
    return EstimationResult(
        summary=summary,
        project_type="internal_tool",
        detail_level="summary",
        output_format="narrative",
        total_duration_weeks=2,
        total_cost_eur=3000,
        confidence_pct=80,
        phases=[
            {
                "name": "Implementation",
                "summary": "Build the first version.",
                "duration_weeks": 2,
                "cost_eur": 3000,
                "confidence_pct": 80,
                "tasks": ["Build backend", "Build frontend"],
                "risks": [],
            }
        ],
        assumptions=[],
        risks=[],
        recommendations=[],
    )


def test_session_history_uses_structured_assistant_payload_not_rendered_markdown(monkeypatch):
    captured_histories = []

    def fake_estimate_product(request, **kwargs):
        captured_histories.append(kwargs.get("conversation_history") or [])
        return {
            "prompt_version": kwargs.get("prompt_version", "v1"),
            "text": "## Product estimate\n\n| Phase | Hours |\n| --- | --- |\n| Build | 40 |",
            "result": fake_structured_result("Atlas CRM structured estimate."),
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
            "transcript": (
                "Project: Atlas CRM. Build FastAPI onboarding with PostgreSQL "
                "for a team of 3 engineers."
            )
        },
    )
    second = client.post(
        f"/sessions/{session_id}/estimate",
        data={"transcript": "Keep the same Atlas CRM project and add reporting."},
    )

    assert first.status_code == 200
    assert second.status_code == 200

    second_history = captured_histories[1]
    assistant_messages = [
        message["content"]
        for message in second_history
        if message["role"] == "assistant"
    ]

    assert assistant_messages
    assert "Atlas CRM structured estimate" in assistant_messages[0]
    assert "## Product estimate" not in assistant_messages[0]
    assert "| Phase |" not in assistant_messages[0]
