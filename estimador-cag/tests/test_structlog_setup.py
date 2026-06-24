
from app.middleware import logging as logging_module


def test_setup_structlog_returns_bound_logger():
    logger = logging_module.setup_structlog()

    assert hasattr(logger, "bind")

    bound = logger.bind(request_id="req-test")
    assert hasattr(bound, "info")
