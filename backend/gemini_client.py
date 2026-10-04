"""
Gemini API client wrapper.

Central place for API-key validation, model selection, and retry/backoff, so
no caller touches `google.genai` configuration directly or loses an entire
run to one transient error (the original llm_evaluation/test_gemini_*.py
scripts had no retry/backoff/timeout at all around generate_content calls).
"""

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.config import config
from backend.errors import LLMConfigError, LLMRequestError


class _RetryableError(Exception):
    """Wraps transient google-genai failures so tenacity can retry them uniformly."""


def _is_retryable(exc: Exception) -> bool:
    # 4xx (bad request, bad key, unknown model) won't succeed on retry; only
    # timeouts and rate limits are worth waiting for. Network/5xx errors are.
    if isinstance(exc, genai_errors.ClientError):
        return exc.code in (408, 429)
    return True


def _get_client() -> genai.Client:
    if not config.gemini_api_key:
        raise LLMConfigError(
            "GEMINI_API_KEY is not set. Add it to a .env file in the repo root "
            "or set it as an environment variable."
        )
    return genai.Client(api_key=config.gemini_api_key)


@retry(
    retry=retry_if_exception_type(_RetryableError),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _generate_with_retry(client: genai.Client, **kwargs):
    try:
        return client.models.generate_content(**kwargs)
    except Exception as exc:
        if not _is_retryable(exc):
            raise LLMRequestError(f"Gemini rejected the request: {exc}") from exc
        raise _RetryableError(str(exc)) from exc


def generate_content(contents, tools: list | None = None, model: str | None = None):
    """
    Call Gemini's generate_content with retry/backoff.

    Raises LLMConfigError if no API key is configured, LLMRequestError if the
    request is rejected outright (4xx) or all retry attempts are exhausted.
    """
    client = _get_client()
    gen_config = types.GenerateContentConfig(tools=tools) if tools else None

    try:
        return _generate_with_retry(
            client,
            model=model or config.gemini_model,
            contents=contents,
            config=gen_config,
        )
    except _RetryableError as exc:
        raise LLMRequestError(f"Gemini request failed after retries: {exc}") from exc
