from pathlib import Path

SOURCE = Path("streamlit_app.py").read_text(encoding="utf-8")


def test_streamlit_reads_result_from_backend_response():
    """
    Streamlit should prefer the structured result field from the backend.

    Why this matters:
    Phase 4 made the API return EstimationResult. The UI should consume that
    product contract instead of treating markdown as the primary interface.
    """

    assert 'result.get("result")' in SOURCE or "response.get(\"result\")" in SOURCE


def test_streamlit_renders_phases_with_table_or_dataframe():
    """
    Phases should render as fields in a table.

    Why this matters:
    The product frontend should not parse markdown tables. It should render the
    phase list that Pydantic already validated.
    """

    assert "st.dataframe(" in SOURCE or "st.table(" in SOURCE
    assert "phase_rows" in SOURCE
    assert "duration_weeks" in SOURCE
    assert "cost_eur" in SOURCE
    assert "confidence_pct" in SOURCE


def test_streamlit_displays_total_cost_duration_and_confidence_metrics():
    """
    Key estimation totals should be rendered as metrics.

    Why this matters:
    A product UI should surface cost, duration, and confidence immediately.
    """

    assert "st.metric(" in SOURCE
    assert "total_cost_eur" in SOURCE
    assert "total_duration_weeks" in SOURCE
    assert "confidence_pct" in SOURCE


def test_streamlit_displays_assumptions_risks_and_recommendations():
    """
    Structured narrative sections should be rendered from fields.

    Why this matters:
    Assumptions, risks, and recommendations are first class output fields, not
    text fragments hidden inside markdown.
    """

    assert "Assumptions" in SOURCE
    assert "Risks" in SOURCE
    assert "Recommendations" in SOURCE
    assert 'structured_result.get("assumptions"' in SOURCE
    assert 'structured_result.get("risks"' in SOURCE
    assert 'structured_result.get("recommendations"' in SOURCE


def test_streamlit_still_displays_prompt_version_and_cache_info():
    """
    Prompt and cache metadata should remain visible for auditability.

    Why this matters:
    Product demos should explain which prompt version and cache path produced
    the estimate.
    """

    assert "Prompt version:" in SOURCE
    assert "Cache:" in SOURCE
    assert 'result.get("cached")' in SOURCE
    assert 'result.get("cache_backend")' in SOURCE


def test_streamlit_falls_back_to_text_only_when_result_is_absent():
    """
    Text only compatibility must remain.

    Why this matters:
    Older backend responses, error recovery, and legacy demos should still show
    useful output even without structured result.
    """

    assert "No structured result returned" in SOURCE
    assert 'result.get("text", "")' in SOURCE


def test_streamlit_has_no_chat_input_or_unsupported_min_chars_argument():
    """
    The product interface must stay as a typed form.

    Why this matters:
    Session 04 moved away from chat input, and Streamlit text_area does not use
    a min_chars argument.
    """

    assert "st.chat_input" not in SOURCE
    assert "min_chars=" not in SOURCE


def test_parse_reference_projects_tests_still_have_supported_parser():
    """
    The optional reference project parser should remain available.

    Why this matters:
    Reference projects are part of the product request and exact cache identity.
    """

    assert "def parse_reference_projects" in SOURCE
    assert 'estimated_hours": estimated_hours' in SOURCE
