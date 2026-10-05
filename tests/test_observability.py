import pytest

from backend import observability
from backend.config import config


@pytest.fixture(autouse=True)
def _reset_client_cache():
    # _client() is process-wide lru_cache'd; clear it around each test so
    # config monkeypatches here don't leak a stale client into other tests.
    observability._client.cache_clear()
    yield
    observability._client.cache_clear()


def test_is_enabled_reflects_config(monkeypatch):
    monkeypatch.setattr(config, "langfuse_public_key", None)
    monkeypatch.setattr(config, "langfuse_secret_key", None)
    assert observability.is_enabled() is False

    monkeypatch.setattr(config, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(config, "langfuse_secret_key", "sk-test")
    assert observability.is_enabled() is True


def test_observation_is_safe_to_use_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "langfuse_public_key", None)
    monkeypatch.setattr(config, "langfuse_secret_key", None)

    with observability.observation("span", name="test-span", input={"a": 1}) as span:
        span.update(output={"b": 2})
        span.score_trace(name="dummy", value=1.0)

    observability.flush()
