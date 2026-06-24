"""
Streamlit product interface for the Session 04 typed estimation flow.

LAYER: frontend
RESPONSIBILITY: Collect typed estimation parameters, call the FastAPI backend,
                and render structured estimate fields.
WHY IT EXISTS: Session 04 turns the estimator from a free chat into a product
               interface with explicit request fields and field based output.
DEPENDS ON: streamlit, requests, FastAPI /api/v1/estimate.
"""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

DEFAULT_BACKEND_URL = "http://localhost:8000"
ESTIMATE_PATH = "/api/v1/estimate"
SEARCH_PATH = "/search"
SEARCH_METRICS_PATH = "/search/metrics"
SESSION_CREATE_PATH = "/sessions"
SESSION_ESTIMATE_PATH_TEMPLATE = "/sessions/{session_id}/estimate"
BACKEND_CONNECT_TIMEOUT_SECONDS = 10
BACKEND_READ_TIMEOUT_SECONDS = 240

PROJECT_TYPE_OPTIONS = {
    "Mobile app": "mobile_app",
    "Web SaaS": "web_saas",
    "Internal tool": "internal_tool",
    "Data pipeline": "data_pipeline",
}

DETAIL_LEVEL_OPTIONS = {
    "Summary": "summary",
    "Medium": "medium",
    "Detailed": "detailed",
}

OUTPUT_FORMAT_OPTIONS = {
    "Phases table": "phases_table",
    "Line items": "line_items",
    "Narrative": "narrative",
}

PROMPT_VERSION_OPTIONS = ["v1", "v2"]

MODEL_TIER_OPTIONS = {
    "DeepSeek flash": "flash",
    "DeepSeek pro": "pro",
    "Kimi 2.5 backup": "backup",
    "Kimi 2.6 backup_pro": "backup_pro",
}


def get_backend_url() -> str:
    """Return the configured backend base URL without a trailing slash."""

    return os.getenv("ESTIMADOR_BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")


def build_estimate_url() -> str:
    """Build the FastAPI estimate endpoint URL used by the product form."""

    return f"{get_backend_url()}{ESTIMATE_PATH}"



def build_search_url() -> str:
    """Build the FastAPI Session 10 retrieval search endpoint URL."""

    return f"{get_backend_url()}{SEARCH_PATH}"


def build_search_metrics_url() -> str:
    """Build the FastAPI retrieval search metrics endpoint URL."""

    return f"{get_backend_url()}{SEARCH_METRICS_PATH}"


def _compact_optional_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop empty optional values before sending a backend request."""

    compacted: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue

        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                compacted[key] = stripped
            continue

        compacted[key] = value

    return compacted


def post_search_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Send a Session 10 retrieval search request to the backend."""

    response = requests.post(
        build_search_url(),
        json=_compact_optional_payload(payload),
        timeout=(BACKEND_CONNECT_TIMEOUT_SECONDS, BACKEND_READ_TIMEOUT_SECONDS),
    )
    response.raise_for_status()
    return response.json()


def get_search_metrics() -> dict[str, Any]:
    """Fetch the in-memory retrieval search metrics dashboard."""

    response = requests.get(
        build_search_metrics_url(),
        timeout=(BACKEND_CONNECT_TIMEOUT_SECONDS, BACKEND_READ_TIMEOUT_SECONDS),
    )
    response.raise_for_status()
    return response.json()


def post_estimation_request(payload: dict[str, Any], prompt_version: str = "v1") -> dict[str, Any]:
    """
    Send the typed estimation payload to the backend.

    Raises:
        requests.HTTPError: When the backend returns a non success response.
        requests.RequestException: For connection and timeout failures.
    """

    response = requests.post(
        build_estimate_url(),
        params={"prompt_version": prompt_version},
        json=payload,
        timeout=90,
    )
    response.raise_for_status()
    return response.json()




def post_session04_estimate_request_for_compatibility(
    payload: dict[str, Any],
    prompt_version_label: str,
) -> dict[str, Any]:
    """Keep the Session 04 typed JSON endpoint available as a real fallback path."""

    return post_estimation_request(payload, prompt_version=prompt_version_label)


def build_session_create_url() -> str:
    """Build the Session 05 session creation URL."""

    return f"{get_backend_url()}{SESSION_CREATE_PATH}"


def build_session_estimate_url(session_id: str) -> str:
    """Build the Session 05 multipart estimate URL for one conversation."""

    return f"{get_backend_url()}{SESSION_ESTIMATE_PATH_TEMPLATE.format(session_id=session_id)}"


def create_backend_session() -> str:
    """Create a backend conversation session and return its UUID."""

    response = requests.post(build_session_create_url(), timeout=(BACKEND_CONNECT_TIMEOUT_SECONDS, BACKEND_READ_TIMEOUT_SECONDS))
    response.raise_for_status()
    payload = response.json()
    return str(payload["session_id"])


def ensure_session_id() -> str:
    """Ensure Streamlit has a backend session id in session_state."""

    if "session_id" not in st.session_state:
        st.session_state["session_id"] = create_backend_session()
    return str(st.session_state["session_id"])


def start_new_conversation() -> None:
    """Reset the Streamlit conversation state and create a fresh backend session."""

    st.session_state["session_id"] = create_backend_session()
    st.session_state["last_project_metadata"] = {}
    st.session_state["last_session_response"] = None


def _build_file_payload(uploaded_files: list[Any] | None) -> list[tuple[str, tuple[str, bytes, str]]]:
    """Convert Streamlit UploadedFile objects to requests multipart tuples."""

    files_payload: list[tuple[str, tuple[str, bytes, str]]] = []
    for uploaded_file in uploaded_files or []:
        media_type = getattr(uploaded_file, "type", None) or "application/octet-stream"
        files_payload.append(
            (
                "attachments",
                (
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    media_type,
                ),
            )
        )
    return files_payload


def post_session_estimate_request(
    session_id: str,
    data: dict[str, Any],
    uploaded_files: list[Any] | None = None,
) -> dict[str, Any]:
    """Send a Session 05 multipart estimation request to the backend."""

    files_payload = _build_file_payload(uploaded_files)
    response = requests.post(
        build_session_estimate_url(session_id),
        data=data,
        files=files_payload,
        timeout=(BACKEND_CONNECT_TIMEOUT_SECONDS, BACKEND_READ_TIMEOUT_SECONDS),
    )
    response.raise_for_status()
    return response.json()


def render_project_metadata_panel(metadata: dict[str, Any] | None) -> None:
    """Render Session 05 project memory for debugging and class review."""

    st.subheader("Project metadata")
    if metadata:
        st.json(metadata)
    else:
        st.caption("No project metadata captured yet.")

def parse_reference_projects(raw_text: str) -> list[dict[str, Any]] | None:
    """Parse optional reference project notes into typed request payload items."""

    projects: list[dict[str, Any]] = []

    for line in raw_text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue

        parts = [part.strip() for part in cleaned.split("|")]
        name = parts[0][:120]
        estimated_hours = None
        notes = None

        if len(parts) >= 2:
            hours_candidate = (
                parts[1]
                .lower()
                .replace("hours", "")
                .replace("hour", "")
                .replace("hrs", "")
                .replace("h", "")
                .strip()
            )
            if hours_candidate.isdigit():
                estimated_hours = int(hours_candidate)
            else:
                notes = parts[1]

        if len(parts) >= 3:
            notes = parts[2]

        summary = notes or cleaned

        projects.append(
            {
                "name": name,
                "summary": summary[:800],
                "estimated_hours": estimated_hours,
                "notes": notes[:800] if notes else None,
            }
        )

    return projects or None


def format_eur(value: int | float | None) -> str:
    """
    Format a euro value for metric cards.

    Why this matters:
    The backend stores numeric fields, while the UI needs a readable product
    presentation.
    """

    if value is None:
        return "unknown"

    return f"€{value:,.0f}"


def render_list_section(title: str, items: list[str] | None) -> None:
    """
    Render a structured list section.

    Why this matters:
    Assumptions, risks, and recommendations are first class fields in
    EstimationResult. The UI should not scrape them from markdown.
    """

    st.markdown(f"### {title}")

    if not items:
        st.caption("No items returned.")
        return

    for item in items:
        st.markdown(f"- {item}")


def render_cache_and_prompt_metadata(result: dict[str, Any]) -> None:
    """
    Render prompt and cache metadata for auditability.

    Why this matters:
    During class review we can explain which prompt version, cache state, model,
    provider, and tier produced the estimate.
    """

    prompt_version = result.get("prompt_version", "unknown")
    st.caption(f"Prompt version: {prompt_version}")

    cached = result.get("cached")
    cache_backend = result.get("cache_backend")
    model = result.get("model")
    provider = result.get("provider")
    tier = result.get("tier")
    requested_tier = result.get("requested_tier")
    served_tier = result.get("served_tier")
    fallback_used = result.get("fallback_used")
    semantic_cache_mode = result.get("semantic_cache_mode")
    semantic_candidate_found = result.get("semantic_candidate_found")

    cache_label = "hit" if cached else "miss" if cached is False else "unknown"
    metadata_parts = [
        f"Cache: {cache_label}",
        f"backend={cache_backend or 'unknown'}",
        f"model={model or 'unknown'}",
        f"provider={provider or 'unknown'}",
        f"tier={tier or 'unknown'}",
        f"requested_tier={requested_tier or 'unknown'}",
        f"served_tier={served_tier or 'unknown'}",
        f"fallback_used={fallback_used}",
        f"semantic_cache_mode={semantic_cache_mode or 'unknown'}",
        f"semantic_candidate_found={semantic_candidate_found}",
    ]

    st.caption(" | ".join(metadata_parts))


def render_structured_estimate(result: dict[str, Any]) -> None:
    """
    Render the backend EstimationResponse.

    Structured result is the primary UI path. Text is a compatibility fallback.

    Why this matters:
    Phase 5 closes the product loop. The frontend now consumes fields from
    EstimationResult instead of parsing model prose.
    """

    structured_result = result.get("result")

    st.subheader("Estimate")

    if not structured_result:
        st.warning("No structured result returned. Falling back to text output.")
        st.markdown(result.get("text", ""))
        render_cache_and_prompt_metadata(result)
        return

    st.markdown("### Summary")
    st.info(structured_result.get("summary", "No summary returned."))

    metric_cost, metric_duration, metric_confidence = st.columns(3)

    with metric_cost:
        st.metric("Total cost", format_eur(structured_result.get("total_cost_eur")))

    with metric_duration:
        duration = structured_result.get("total_duration_weeks", "unknown")
        st.metric("Duration", f"{duration} weeks")

    with metric_confidence:
        confidence = structured_result.get("confidence_pct", "unknown")
        st.metric("Confidence", f"{confidence}%")

    phases = structured_result.get("phases") or []
    phase_rows = [
        {
            "Phase": phase.get("name"),
            "Summary": phase.get("summary"),
            "Duration weeks": phase.get("duration_weeks"),
            "Cost EUR": phase.get("cost_eur"),
            "Confidence %": phase.get("confidence_pct"),
            "Tasks": ", ".join(phase.get("tasks") or []),
            "Risks": ", ".join(phase.get("risks") or []),
        }
        for phase in phases
    ]

    st.markdown("### Phases")
    if phase_rows:
        st.dataframe(phase_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No phases returned.")

    section_assumptions, section_risks, section_recommendations = st.columns(3)

    with section_assumptions:
        render_list_section("Assumptions", structured_result.get("assumptions"))

    with section_risks:
        render_list_section("Risks", structured_result.get("risks"))

    with section_recommendations:
        render_list_section("Recommendations", structured_result.get("recommendations"))

    with st.expander("Compatibility text"):
        st.markdown(result.get("text", ""))

    render_cache_and_prompt_metadata(result)



def render_search_result_card(result: dict[str, Any], rank: int) -> None:
    """Render one retrieval search result."""

    distance = result.get("distance")
    distance_label = f"{distance:.4f}" if isinstance(distance, (int, float)) else "unknown"
    chunk_type = result.get("chunk_type", "unknown")
    content = result.get("content", "")

    st.markdown(f"#### {rank}. {chunk_type}")

    metric_distance, metric_chunk, metric_document = st.columns(3)

    with metric_distance:
        st.metric("distance", distance_label)

    with metric_chunk:
        st.metric("chunk_type", chunk_type)

    with metric_document:
        st.metric("document_id", result.get("document_id", "unknown"))

    st.write(content)

    with st.expander("metadata"):
        st.json(result.get("metadata") or {})


def render_search_metrics_dashboard(metrics: dict[str, Any] | None) -> None:
    """Render the in-memory search metrics snapshot returned by /search/metrics."""

    if not metrics:
        st.caption("No search metrics loaded yet. Run a search or click Refresh search metrics.")
        return

    total = metrics.get("total_searches_recorded", 0)
    success_count = metrics.get("success_count", 0)
    failure_count = metrics.get("failure_count", 0)
    last_search = metrics.get("last_search") or {}

    metric_total, metric_success, metric_failure, metric_last_count = st.columns(4)

    with metric_total:
        st.metric("recorded searches", total)

    with metric_success:
        st.metric("successes", success_count)

    with metric_failure:
        st.metric("failures", failure_count)

    with metric_last_count:
        st.metric("last result count", last_search.get("result_count", "unknown"))

    if last_search:
        st.markdown("#### Last search")
        st.json(last_search)

    history = metrics.get("history") or []
    if history:
        st.markdown("#### Recent search history")
        st.dataframe(history[-10:], use_container_width=True, hide_index=True)
    else:
        st.caption("No search history returned yet.")


def render_session10_search_panel() -> None:
    """Render the Session 10 retrieval search UI backed by /search."""

    st.markdown("## Session 10 retrieval search")
    st.caption(
        "Search historical budgets using the Session 10 retrieval stack. "
        "Vector mode preserves the pgvector baseline; hybrid mode adds lexical search and RRF fusion."
    )

    with st.form("session10_retrieval_search_form"):
        query = st.text_input(
            "Search historical budgets",
            value="REST API development with JWT authentication for financial sector",
        )

        col_mode, col_k, col_recall = st.columns(3)

        with col_mode:
            search_mode_label = st.selectbox(
                "search_mode",
                options=["Vector only", "Hybrid RRF"],
                index=1,
                help="Vector only uses the pgvector baseline. Hybrid RRF fuses vector and lexical retrieval.",
            )
            search_mode = "hybrid" if search_mode_label == "Hybrid RRF" else "vector"

        with col_k:
            k = st.number_input("k", min_value=1, max_value=20, value=5, step=1)

        with col_recall:
            recall_k = st.number_input(
                "recall_k",
                min_value=1,
                max_value=100,
                value=8,
                step=1,
                help="Internal candidate pool used by hybrid and reranking measurements.",
            )

        col_sector, col_country, col_stack, col_scope = st.columns(4)

        with col_sector:
            client_sector = st.text_input("client_sector", placeholder="finance")

        with col_country:
            client_country = st.text_input("client_country", placeholder="ES")

        with col_stack:
            tech_stack = st.text_input("tech_stack", placeholder="python")

        with col_scope:
            scope = st.text_input("scope", placeholder="backend")

        submitted = st.form_submit_button("Run semantic search", type="primary")

    if submitted:
        payload = {
            "query": query,
            "k": int(k),
            "search_mode": search_mode,
            "recall_k": int(recall_k),
            "client_sector": client_sector,
            "client_country": client_country,
            "tech_stack": tech_stack,
            "scope": scope,
        }

        with st.spinner("Searching pgvector chunks..."):
            try:
                search_result = post_search_request(payload)
            except requests.HTTPError as exc:
                response_text = exc.response.text if exc.response is not None else str(exc)
                st.error(f"Search backend returned an error: {response_text}")
                return
            except requests.RequestException as exc:
                st.error(f"Could not reach search backend: {exc}")
                return

        result_count = len(search_result.get("results") or [])
        search_time_ms = search_result.get("search_time_ms", "unknown")
        st.success(
            f"Returned {result_count} results in {search_time_ms} ms "
            f"using {search_mode} search with recall_k={int(recall_k)}."
        )

        try:
            st.session_state["last_search_metrics"] = get_search_metrics()
        except requests.RequestException as exc:
            st.warning(f"Search succeeded, but metrics refresh failed: {exc}")

        with st.expander("filters_applied", expanded=True):
            st.json(search_result.get("filters_applied") or {})

        for index, result in enumerate(search_result.get("results") or [], start=1):
            render_search_result_card(result, index)

    with st.expander("Search metrics dashboard", expanded=True):
        if st.button("Refresh search metrics"):
            try:
                st.session_state["last_search_metrics"] = get_search_metrics()
            except requests.RequestException as exc:
                st.error(f"Could not load search metrics dashboard: {exc}")

        render_search_metrics_dashboard(st.session_state.get("last_search_metrics"))


def main() -> None:
    """Render the Session 05 conversational memory plus attachments product UI."""

    st.set_page_config(
        page_title="AI Software Estimator",
        page_icon="🧠",
        layout="wide",
    )

    st.title("AI Software Estimator")
    st.caption(
        "Session 05 product interface with conversational memory, local attachment extraction, "
        "typed controls, structured estimates, and Session 10 retrieval search."
    )

    render_session10_search_panel()
    st.divider()

    session_error: str | None = None
    try:
        session_id = ensure_session_id()
    except requests.RequestException as exc:
        session_id = ""
        session_error = str(exc)

    with st.sidebar:
        st.subheader("Backend")
        st.code(get_backend_url())
        st.caption("Set ESTIMADOR_BACKEND_URL when running outside localhost.")

        st.subheader("Conversation")
        if session_id:
            st.code(session_id)
        else:
            st.warning("No backend session yet.")

        if st.button("New conversation", type="secondary"):
            try:
                start_new_conversation()
                st.rerun()
            except requests.RequestException as exc:
                st.error(f"Could not create a new backend session: {exc}")

        render_project_metadata_panel(st.session_state.get("last_project_metadata"))

    if session_error:
        st.error(f"Could not create a backend session: {session_error}")
        st.info("Start the FastAPI backend, then reload this page.")
        return

    with st.form("product_estimation_form"):
        transcript = st.text_area(
            "Transcript",
            max_chars=2000,
            height=220,
            placeholder=(
                "Paste the latest client conversation turn. The backend keeps project metadata "
                "and recent history inside the current session."
            ),
        )

        uploaded_files = st.file_uploader(
            "Attachments",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            help="Upload PDFs or Word documents with technical specs, proposals, or scope notes.",
        )

        col_project, col_detail, col_format = st.columns(3)

        with col_project:
            project_type_label = st.selectbox(
                "Project type",
                options=list(PROJECT_TYPE_OPTIONS.keys()),
                index=1,
            )

        with col_detail:
            detail_level_label = st.selectbox(
                "Detail level",
                options=list(DETAIL_LEVEL_OPTIONS.keys()),
                index=1,
            )

        with col_format:
            output_format_label = st.selectbox(
                "Output format",
                options=list(OUTPUT_FORMAT_OPTIONS.keys()),
                index=0,
            )

        col_prompt, col_model = st.columns(2)

        with col_prompt:
            prompt_version_label = st.selectbox(
                "Prompt version",
                options=PROMPT_VERSION_OPTIONS,
                index=0,
            )

        with col_model:
            model_tier_label = st.selectbox(
                "Model",
                options=list(MODEL_TIER_OPTIONS.keys()),
                index=0,
                help="Starting provider tier. Fallback ladder remains active.",
            )

        reference_projects_raw = st.text_area(
            "Reference projects, optional",
            height=120,
            placeholder=(
                "Optional calibration notes, one project per line. Example: "
                "CRM migration | 260h | permissions and reporting were risky"
            ),
        )

        submitted = st.form_submit_button("Generate estimate", type="primary")

    if not submitted:
        st.info("Create or continue a conversation, then generate an estimate when the project shape is clear.")
        return

    description = transcript.strip()
    if len(description) < 20:
        st.error("Project description must contain at least 20 characters.")
        return

    payload = {
        "description": description,
        "project_type": PROJECT_TYPE_OPTIONS[project_type_label],
        "detail_level": DETAIL_LEVEL_OPTIONS[detail_level_label],
        "output_format": OUTPUT_FORMAT_OPTIONS[output_format_label],
        "tier": MODEL_TIER_OPTIONS[model_tier_label],
        "reference_projects": parse_reference_projects(reference_projects_raw),
    }

    data = {
        "transcript": description,
        "project_type": payload["project_type"],
        "detail_level": payload["detail_level"],
        "output_format": payload["output_format"],
        "prompt_version": prompt_version_label,
        "tier": payload["tier"],
    }

    if payload["reference_projects"]:
        data["reference_projects"] = str(payload["reference_projects"])

    with st.spinner("Generating session-aware product estimate..."):
        try:
            result = post_session_estimate_request(
                st.session_state["session_id"],
                data=data,
                uploaded_files=uploaded_files,
            )
        except requests.HTTPError as exc:
            response_text = exc.response.text if exc.response is not None else str(exc)
            st.error(f"Backend returned an error: {response_text}")
            return
        except requests.RequestException as exc:
            st.error(f"Could not reach backend: {exc}")
            return

    st.session_state["last_session_response"] = result
    st.session_state["last_project_metadata"] = result.get("project_metadata") or {}

    render_structured_estimate(result)

    with st.expander("Session response"):
        st.json(result)

    with st.expander("Multipart form payload"):
        st.json(data)



if __name__ == "__main__":
    main()
