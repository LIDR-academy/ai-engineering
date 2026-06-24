from uuid import UUID

from app.services.sessions import ConversationHistory, ProjectMetadata, SessionStore


def test_session_store_creates_uuid_v4_session():
    store = SessionStore()
    session = store.create_session()
    parsed = UUID(session.session_id)
    assert parsed.version == 4
    assert store.get_session(session.session_id) is session


def test_conversation_history_keeps_system_prompt_and_sliding_turn_window():
    history = ConversationHistory(max_turns=6)
    for index in range(8):
        history.add_turn(f"user {index}", f"assistant {index}")
    messages = history.to_messages_list("system prompt")
    assert history.turn_count == 6
    assert messages[0] == {"role": "system", "content": "system prompt"}
    assert len(messages) == 13
    assert {"role": "user", "content": "user 0"} not in messages
    assert {"role": "assistant", "content": "assistant 0"} not in messages
    assert messages[1] == {"role": "user", "content": "user 2"}


def test_project_metadata_prompt_block_is_empty_until_facts_exist():
    metadata = ProjectMetadata()
    assert metadata.to_prompt_block() == ""
    metadata = ProjectMetadata(
        project_name="Atlas CRM",
        assumed_team_size=3,
        mentioned_technologies=["FastAPI", "PostgreSQL"],
        agreed_scope="Build onboarding and reporting.",
    )
    block = metadata.to_prompt_block()
    assert "project_name: Atlas CRM" in block
    assert "assumed_team_size: 3" in block
    assert "mentioned_technologies: FastAPI, PostgreSQL" in block
