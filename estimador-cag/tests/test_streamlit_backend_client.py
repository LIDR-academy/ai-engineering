from pathlib import Path

SOURCE = Path("streamlit_app.py").read_text(encoding="utf-8")


def test_streamlit_does_not_import_llm_service_runtime_functions_directly():
    forbidden_imports = [
        "from app.services.llm_service import estimate",
        "from app.services.llm_service import estimate_stream",
        "estimate, estimate_stream",
        "from app.services.llm_service import build_system_prompt",
    ]

    for forbidden in forbidden_imports:
        assert forbidden not in SOURCE

    assert "post_estimation_request(" in SOURCE


def test_streamlit_defines_backend_url_and_estimate_path():
    assert "DEFAULT_BACKEND_URL" in SOURCE
    assert "ESTIMADOR_BACKEND_URL" in SOURCE
    assert "ESTIMATE_PATH" in SOURCE
    assert "/api/v1/estimate" in SOURCE


def test_streamlit_uses_requests_for_typed_backend_call():
    assert "requests.post(" in SOURCE
    assert "build_estimate_url()" in SOURCE
    assert "json=payload" in SOURCE
    assert 'params={"prompt_version": prompt_version}' in SOURCE
    assert "response.raise_for_status()" in SOURCE


def test_streamlit_no_longer_uses_session03_chat_streaming_surface():
    assert "st.chat_input" not in SOURCE
    assert "st.chat_message" not in SOURCE
    assert "st.write_stream" not in SOURCE
    assert "/api/v1/estimate/stream" not in SOURCE
    assert "parse_sse_data_line" not in SOURCE
    assert "build_backend_history" not in SOURCE


def test_streamlit_uses_product_form_controls():
    assert "st.form(" in SOURCE
    assert "st.form_submit_button" in SOURCE
    assert "st.text_area" in SOURCE
    assert "st.selectbox" in SOURCE


def test_streamlit_payload_matches_session04_estimation_request():
    assert '"description": description' in SOURCE
    assert '"project_type": PROJECT_TYPE_OPTIONS[project_type_label]' in SOURCE
    assert '"detail_level": DETAIL_LEVEL_OPTIONS[detail_level_label]' in SOURCE
    assert '"output_format": OUTPUT_FORMAT_OPTIONS[output_format_label]' in SOURCE
    assert '"reference_projects": parse_reference_projects(reference_projects_raw)' in SOURCE


def test_streamlit_displays_session04_response_contract():
    assert 'result.get("result")' in SOURCE
    assert 'result.get("text", "")' in SOURCE
    assert 'result.get("prompt_version", "unknown")' in SOURCE
    assert "Prompt version:" in SOURCE
    assert "Cache:" in SOURCE
    assert "PROMPT_VERSION_OPTIONS" in SOURCE
    assert "Reference projects, optional" in SOURCE


def test_streamlit_does_not_use_local_streaming_cache_as_backend_cache():
    assert "streaming_cache" not in SOURCE
    assert "make_streaming_cache_key" not in SOURCE
    assert "cache_key" not in SOURCE
