from pathlib import Path

SOURCE = Path("streamlit_app.py").read_text(encoding="utf-8")


def test_streamlit_exposes_prompt_version_selector():
    assert "PROMPT_VERSION_OPTIONS" in SOURCE
    assert '"v1"' in SOURCE
    assert '"v2"' in SOURCE
    assert "Prompt version" in SOURCE
    assert "prompt_version_label" in SOURCE


def test_streamlit_posts_prompt_version_query_param():
    assert 'params={"prompt_version": prompt_version}' in SOURCE
    assert "post_estimation_request(payload, prompt_version=prompt_version_label)" in SOURCE


def test_streamlit_accepts_optional_reference_projects():
    assert "Reference projects, optional" in SOURCE
    assert "parse_reference_projects" in SOURCE
    assert "reference_projects_raw" in SOURCE
    assert '"reference_projects": parse_reference_projects(reference_projects_raw)' in SOURCE


def test_parse_reference_projects_supports_name_hours_and_notes():
    import streamlit_app

    parsed = streamlit_app.parse_reference_projects(
        "CRM migration | 260h | permissions and reporting were risky"
    )

    assert parsed == [
        {
            "name": "CRM migration",
            "summary": "permissions and reporting were risky",
            "estimated_hours": 260,
            "notes": "permissions and reporting were risky",
        }
    ]


def test_parse_reference_projects_returns_none_for_empty_input():
    import streamlit_app

    assert streamlit_app.parse_reference_projects("") is None
    assert streamlit_app.parse_reference_projects("   \n   ") is None
