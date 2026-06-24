from app.services.conversation import (
    ConversationTurn,
    build_conversation_messages,
    summarize_conversation_stub,
)


def test_build_conversation_messages_preserves_system_prompt_first():
    messages = build_conversation_messages(
        system_prompt="SYSTEM PROMPT",
        transcription="Current meeting transcript",
        history=[
            ConversationTurn(role="user", content="Previous user message"),
            ConversationTurn(role="assistant", content="Previous assistant estimate"),
        ],
        max_history_turns=4,
    )

    assert messages[0] == {"role": "system", "content": "SYSTEM PROMPT"}
    assert messages[-1] == {
        "role": "user",
        "content": "TRANSCRIPCION DE REUNION:\nCurrent meeting transcript",
    }


def test_build_conversation_messages_keeps_recent_history_only():
    history = [
        ConversationTurn(role="user", content="old user"),
        ConversationTurn(role="assistant", content="old assistant"),
        ConversationTurn(role="user", content="recent user"),
        ConversationTurn(role="assistant", content="recent assistant"),
    ]

    messages = build_conversation_messages(
        system_prompt="SYSTEM",
        transcription="Now estimate this",
        history=history,
        max_history_turns=2,
    )

    contents = [message["content"] for message in messages]

    assert "old user" not in contents
    assert "old assistant" not in contents
    assert "recent user" in contents
    assert "recent assistant" in contents


def test_build_conversation_messages_rejects_invalid_roles():
    try:
        ConversationTurn(role="system", content="malicious override")
    except ValueError as exc:
        assert "role" in str(exc)
    else:
        raise AssertionError("ConversationTurn must reject non user or assistant roles")


def test_summarize_conversation_stub_is_explicitly_not_real_summary():
    summary = summarize_conversation_stub(
        [
            ConversationTurn(role="user", content="Hello"),
            ConversationTurn(role="assistant", content="Hi"),
        ]
    )

    assert summary["status"] == "deferred"
    assert "future" in summary["note"].lower()
