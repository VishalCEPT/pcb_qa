import types as pytypes

import pytest
from google.genai import errors as genai_errors
from tenacity import wait_none

from backend import config as config_module
from backend import gemini_client, spice_service
from backend.config import config
from backend.errors import LLMConfigError, LLMRequestError


class FlakyModels:
    def __init__(self, failures):
        self.failures = failures
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("503 UNAVAILABLE")
        return pytypes.SimpleNamespace(text="YES", kwargs=kwargs)


@pytest.fixture
def fake_client(monkeypatch):
    monkeypatch.setattr(config, "gemini_api_key", "test-key")
    monkeypatch.setattr(gemini_client._generate_with_retry.retry, "wait", wait_none())

    def make(failures):
        client = pytypes.SimpleNamespace(models=FlakyModels(failures))
        monkeypatch.setattr(gemini_client, "_get_client", lambda: client)
        return client.models

    return make


def test_missing_api_key(monkeypatch):
    monkeypatch.setattr(config, "gemini_api_key", None)
    with pytest.raises(LLMConfigError):
        gemini_client.generate_content(contents="hi")


def test_transient_failures_are_retried(fake_client):
    models = fake_client(failures=2)
    response = gemini_client.generate_content(contents="hi")
    assert response.text == "YES"
    assert models.calls == 3
    assert response.kwargs["model"] == config.gemini_model


def test_persistent_failure_raises_after_four_attempts(fake_client):
    models = fake_client(failures=100)
    with pytest.raises(LLMRequestError):
        gemini_client.generate_content(contents="hi")
    assert models.calls == 4


@pytest.mark.parametrize("code, expected_calls", [(400, 1), (404, 1), (429, 4)])
def test_client_errors_fail_fast_except_rate_limits(fake_client, code, expected_calls):
    models = fake_client(failures=100)

    def reject(**_kwargs):
        models.calls += 1
        raise genai_errors.ClientError(code, {"error": {"code": code, "message": "nope", "status": "X"}})

    models.generate_content = reject
    with pytest.raises(LLMRequestError):
        gemini_client.generate_content(contents="hi")
    assert models.calls == expected_calls


def test_missing_config_is_not_an_error_at_load_time(monkeypatch):
    monkeypatch.setattr(config_module, "load_dotenv", lambda **_kw: None)
    for var in ("GEMINI_API_KEY", "GEMINI_MODEL", "NGSPICE_PATH", "KICAD_CLI_PATH"):
        monkeypatch.delenv(var, raising=False)

    cfg = config_module.load_config()
    assert cfg.gemini_api_key is None
    assert cfg.ngspice_path == "ngspice"


def test_reload_config_is_visible_to_modules_that_imported_config(monkeypatch):
    monkeypatch.setattr(config_module, "load_dotenv", lambda **_kw: None)
    original = vars(config).copy()
    try:
        monkeypatch.setenv("GEMINI_API_KEY", "reloaded-key")
        monkeypatch.setenv("NGSPICE_PATH", "/opt/ngspice/bin/ngspice")
        config_module.reload_config()

        assert gemini_client.config.gemini_api_key == "reloaded-key"
        assert spice_service.config.ngspice_path == "/opt/ngspice/bin/ngspice"
    finally:
        vars(config).update(original)
