"""
Optional Langfuse observability.

Traces benchmark runs, Gemini calls, and datasheet retrieval so they're
visible in a self-hosted Langfuse dashboard (see docker-compose.langfuse.yml
and DOCKER.md). This mirrors the rest of backend/'s graceful-degradation
philosophy (see backend.config's module docstring): nothing here raises if
LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY aren't configured. The langfuse SDK
itself is already safe to use unconfigured -- start_as_current_observation()
and friends just log a warning and no-op rather than raising -- so callers
can unconditionally wrap code in observation() without checking is_enabled()
first; that's exposed mainly for callers that want to skip building
otherwise-unused metadata when tracing is off.
"""

from __future__ import annotations

import contextlib
from functools import lru_cache

from backend.config import config


@lru_cache(maxsize=1)
def _client():
    # Cached so the (potentially noisy, when unconfigured) client setup and
    # its "client disabled" log line only happen once per process, and so
    # every call site shares one client/connection when it is configured.
    from langfuse import get_client

    return get_client()


def is_enabled() -> bool:
    return bool(config.langfuse_public_key and config.langfuse_secret_key)


@contextlib.contextmanager
def observation(as_type: str, name: str, **kwargs):
    """
    Context manager for one logical operation (a Gemini call, a datasheet
    retrieval, a whole benchmark run, ...). `as_type` is one of Langfuse's
    observation types: "generation"/"embedding" for model calls, "span" for
    a generic operation, or "tool"/"chain"/"retriever"/"agent"/"evaluator"/
    "guardrail" for more specific ones. Yields the observation object so
    callers can call .update(...)/.score_trace(...)/.score(...) on it.
    """
    with _client().start_as_current_observation(as_type=as_type, name=name, **kwargs) as obs:
        yield obs


def flush() -> None:
    """Force-send any buffered traces; call at process exit for short-lived scripts."""
    _client().flush()
