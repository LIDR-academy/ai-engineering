"""Install bounded request timeouts for LiteLLM provider calls.

The fallback ladder can only advance to the next provider after the current
LiteLLM call raises. Some provider calls can otherwise hang longer than the
HTTP stress-runner timeout, so this module installs a conservative default
request_timeout on every LiteLLM completion call that does not already provide
one.
"""

from __future__ import annotations

import os
from functools import wraps
from typing import Any

import litellm

_DEFAULT_TIMEOUT_SECONDS = 35.0
_ORIGINAL_COMPLETION = litellm.completion
_INSTALLED = False


def _configured_timeout_seconds() -> float:
    raw_value = (
        os.getenv("LITELLM_REQUEST_TIMEOUT_SECONDS")
        or os.getenv("LLM_REQUEST_TIMEOUT_SECONDS")
        or str(_DEFAULT_TIMEOUT_SECONDS)
    )
    try:
        return max(1.0, float(raw_value))
    except ValueError:
        return _DEFAULT_TIMEOUT_SECONDS


def install_litellm_request_timeout() -> None:
    """Patch LiteLLM completion once so fallback can progress after timeouts."""

    global _INSTALLED
    if _INSTALLED:
        return

    @wraps(_ORIGINAL_COMPLETION)
    def completion_with_default_timeout(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("request_timeout", _configured_timeout_seconds())
        return _ORIGINAL_COMPLETION(*args, **kwargs)

    litellm.completion = completion_with_default_timeout
    _INSTALLED = True
