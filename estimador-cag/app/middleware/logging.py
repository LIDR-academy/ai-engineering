"""
LAYER: middleware (observability)
RESPONSIBILITY: Log request metadata and expose runtime metrics endpoint.
WHY IT EXISTS: Session 3 requires observability. Middleware captures latency
               and token usage transparently for every /estimate call.
DEPENDS ON: app.config (settings), time, logging
"""

import logging
import time
import uuid
from collections import deque

import structlog
from fastapi import Request

logger = logging.getLogger(__name__)

# Rolling window of last 100 call metrics
_metrics_history: deque[dict] = deque(maxlen=100)
_last_call: dict = {}
_last_request: dict = {}



def setup_structlog():
    """
    Configure structlog for structured application logging.

    LAYER: middleware
    RESPONSIBILITY: Provide structured logs while keeping the metrics contract stable.
    WHY IT EXISTS: Session 03 canonical observability requires structured logs.
    DEPENDS ON: structlog.
    """
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.KeyValueRenderer(
                key_order=[
                    "timestamp",
                    "level",
                    "event",
                    "request_id",
                    "endpoint",
                    "latency_ms",
                ]
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger("estimador_cag")


structured_logger = setup_structlog()


async def logging_middleware(request: Request, call_next):
    """
    ASGI middleware: logs method, path, duration, and request id.
    WHY async: FastAPI middleware must be async to avoid blocking.
    """
    request_id = str(uuid.uuid4())

    record_request_metrics(
        request_id=request_id,
        endpoint=request.url.path,
        latency_ms=None,
    )

    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    latency_ms = int(duration * 1000)

    record_request_metrics(
        request_id=request_id,
        endpoint=request.url.path,
        latency_ms=latency_ms,
    )
    update_last_call_request_latency(
        request_id=request_id,
        endpoint=request.url.path,
        latency_ms=latency_ms,
    )

    structured_logger.bind(
        request_id=request_id,
        endpoint=request.url.path,
    ).info(
        "http_request_completed",
        method=request.method,
        status_code=response.status_code,
        latency_ms=latency_ms,
    )
    return response


def setup_logging(app):
    """
    Wire middleware into the FastAPI app composition root.
    WHY centralized: Keeps main.py clean; middleware is attached here, not in main.
    """
    app.middleware("http")(logging_middleware)



def record_request_metrics(*, request_id: str, endpoint: str, latency_ms: int):
    """
    Record request lifecycle metadata for the next LLM metrics payload.

    LAYER: middleware
    RESPONSIBILITY: Store transport-level observability fields.
    WHY IT EXISTS: request_id, endpoint, and latency come from the HTTP lifecycle,
                   not from the LLM provider response.
    DEPENDS ON: logging_middleware or tests calling this function.
    """
    global _last_request
    _last_request = {
        "request_id": request_id,
        "endpoint": endpoint,
        "latency_ms": latency_ms,
    }



def update_last_call_request_latency(*, request_id: str, endpoint: str, latency_ms: int):
    """
    Update the last LLM metrics payload once request latency is known.

    LAYER: middleware
    RESPONSIBILITY: Complete request lifecycle fields after the route returns.
    WHY IT EXISTS: LLM metrics are recorded inside the route, but latency is only
                   known after call_next finishes.
    DEPENDS ON: _last_call.
    """
    if (
        _last_call.get("request_id") == request_id
        and _last_call.get("endpoint") == endpoint
    ):
        _last_call["latency_ms"] = latency_ms


def record_call_metrics(result: dict):
    """
    Record metrics from a successful LLM call.
    WHY separate function: llm_service.py calls this to push data without
       knowing about HTTP middleware internals.
    """
    global _last_call
    _last_call = {
        "request_id": result.get("request_id") or _last_request.get("request_id"),
        "endpoint": result.get("endpoint") or _last_request.get("endpoint"),
        "model": result.get("model"),
        "tier": result.get("tier"),
        "provider": result.get("provider"),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "latency_ms": result.get("latency_ms") or _last_request.get("latency_ms"),
        "cost_usd": result.get("cost_usd"),
        "cost_source": result.get("cost_source"),
        "pricing_model": result.get("pricing_model"),
        "timestamp": result.get("timestamp"),
        "cached": result.get("cached", False),
        "cache_backend": result.get("cache_backend", "unknown"),
        "fallback_used": result.get("fallback_used", False),
        "finish_reason": result.get("finish_reason"),
        "error_type": result.get("error_type"),
        "stream_output_chars": result.get("stream_output_chars"),
        "stream_chunks": result.get("stream_chunks"),
        "stream_cached": result.get("stream_cached"),
        "stream_started_at": result.get("stream_started_at"),
        "stream_finished_at": result.get("stream_finished_at"),
    }
    _metrics_history.append(_last_call)
    logger.info(f"Metrics recorded: {_last_call['tier']} tokens={_last_call['input_tokens']}/{_last_call['output_tokens']}")


def get_last_metrics() -> dict:
    """Return metrics from the most recent LLM call."""
    return _last_call.copy()


def get_metrics_history() -> list[dict]:
    """Return rolling window of recent call metrics."""
    return list(_metrics_history)
