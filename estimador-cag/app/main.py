"""
LAYER: main (application entry point)
RESPONSIBILITY: Bootstrap FastAPI, register routers, middleware, and health/metrics.
WHY IT EXISTS: Composition root pattern: all wiring happens in one place
               so the app is predictable and testable.
DEPENDS ON: app.routers.estimations, app.middleware.logging
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.embedding_pipeline.router import router as embedding_router
from app.middleware.logging import get_last_metrics, setup_logging
from app.routers.estimations import router as estimations_router
from app.routers.search import router as search_router
from app.routers.sessions import router as sessions_router
from app.services.litellm_timeout import install_litellm_request_timeout

install_litellm_request_timeout()

app = FastAPI(
    title="LIDR Estimador CAG",
    description="Context-Augmented Generation (CAG) estimator",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Wire observability middleware
setup_logging(app)

# Transport layer
app.include_router(estimations_router)
app.include_router(sessions_router)
app.include_router(embedding_router, prefix="/embeddings", tags=["embeddings"])
app.include_router(search_router, tags=["search"])


@app.get("/health", tags=["health"])
def health_check():
    """Health endpoint for Codespaces port forwarding."""
    return {"status": "ok", "version": "0.3.0"}


@app.get("/metrics", tags=["observability"])
def metrics():
    """
    Runtime metrics from the last LLM call.
    WHY: Session 3 observability requirement. Shows tokens, tier, latency.
    """
    return get_last_metrics()

SESSION08_DEMO_HTML_PATH = Path(__file__).resolve().parents[1] / "docs" / "session08_search_demo.html"
SSE_SESSION08_DEMO_HTML_PATH = Path(__file__).resolve().parents[1] / "docs" / "session08_search_demo.html"
SSE_DEMO_HTML_PATH = Path(__file__).resolve().parents[1] / "docs" / "sse_demo.html"


@app.get("/demo", include_in_schema=False)
def browser_demo() -> FileResponse:
    """
    LAYER: presentation helper
    RESPONSIBILITY: Serve the Session 08 pgvector search demo from FastAPI.
    WHY IT EXISTS: Gives reviewers one safe browser path that exercises
                   /embeddings/ingest and /search instead of the older LLM estimate demo.
    DEPENDS_ON: docs/session08_search_demo.html
    """
    return FileResponse(SESSION08_DEMO_HTML_PATH)


@app.get("/sse-demo", include_in_schema=False)
def sse_demo() -> FileResponse:
    """
    LAYER: presentation helper
    RESPONSIBILITY: Keep the older synchronous-vs-SSE demo available explicitly.
    WHY IT EXISTS: Preserves Session 03 demonstration material without making it
                   the default Session 08 browser path.
    DEPENDS_ON: docs/sse_demo.html
    """
    return FileResponse(SSE_DEMO_HTML_PATH)


@app.get("/", include_in_schema=False)
def root_demo() -> FileResponse:
    """
    LAYER: presentation helper
    RESPONSIBILITY: Serve the Session 08 search demo from the root URL.
    WHY IT EXISTS: Gives nontechnical testers one obvious URL for the current deliverable.
    DEPENDS_ON: docs/session08_search_demo.html
    """
    return FileResponse(SESSION08_DEMO_HTML_PATH)
