from pathlib import Path

STREAMLIT_SOURCE = Path("streamlit_app.py").read_text(encoding="utf-8")


def test_streamlit_creates_and_stores_session_id_on_page_load():
    assert 'SESSION_CREATE_PATH = "/sessions"' in STREAMLIT_SOURCE
    assert "def create_backend_session" in STREAMLIT_SOURCE
    assert "def ensure_session_id" in STREAMLIT_SOURCE
    assert 'st.session_state["session_id"]' in STREAMLIT_SOURCE
    assert "create_backend_session()" in STREAMLIT_SOURCE


def test_streamlit_exposes_new_conversation_button_and_metadata_panel():
    assert "New conversation" in STREAMLIT_SOURCE
    assert "def start_new_conversation" in STREAMLIT_SOURCE
    assert "project_metadata" in STREAMLIT_SOURCE
    assert "Project metadata" in STREAMLIT_SOURCE
    assert "last_project_metadata" in STREAMLIT_SOURCE


def test_streamlit_uses_transcript_area_and_multiple_pdf_docx_uploader():
    assert "Transcript" in STREAMLIT_SOURCE
    assert "st.text_area" in STREAMLIT_SOURCE
    assert "st.file_uploader" in STREAMLIT_SOURCE
    assert 'type=["pdf", "docx"]' in STREAMLIT_SOURCE or "type=('pdf', 'docx')" in STREAMLIT_SOURCE
    assert "accept_multiple_files=True" in STREAMLIT_SOURCE


def test_streamlit_posts_session_estimate_as_multipart_form_data():
    assert 'SESSION_ESTIMATE_PATH_TEMPLATE = "/sessions/{session_id}/estimate"' in STREAMLIT_SOURCE
    assert "def build_session_estimate_url" in STREAMLIT_SOURCE
    assert "def post_session_estimate_request" in STREAMLIT_SOURCE
    assert "requests.post" in STREAMLIT_SOURCE
    assert "data=data" in STREAMLIT_SOURCE
    assert "files=files_payload" in STREAMLIT_SOURCE
    assert "attachments" in STREAMLIT_SOURCE
    assert "transcript" in STREAMLIT_SOURCE


def test_streamlit_keeps_session04_typed_controls_and_model_selector():
    assert "PROJECT_TYPE_OPTIONS" in STREAMLIT_SOURCE
    assert "DETAIL_LEVEL_OPTIONS" in STREAMLIT_SOURCE
    assert "OUTPUT_FORMAT_OPTIONS" in STREAMLIT_SOURCE
    assert "PROMPT_VERSION_OPTIONS" in STREAMLIT_SOURCE
    assert "MODEL_TIER_OPTIONS" in STREAMLIT_SOURCE
    assert "DeepSeek flash" in STREAMLIT_SOURCE
