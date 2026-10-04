"""
Application configuration, loaded from environment variables / a .env file.

Nothing in this module raises on missing values — callers (board_service,
spice_service, qa_service) decide what's required for the action being taken,
and raise backend.errors.MissingDependencyError / LLMConfigError with an
actionable message at the point of use. This lets the GUI start up cleanly
even when GEMINI_API_KEY or ngspice aren't configured, and only fail the
specific tab/action that needs them.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class AppConfig:
    gemini_api_key: str | None
    gemini_model: str
    ngspice_path: str
    kicad_cli_path: str | None


def load_config() -> AppConfig:
    """(Re)load configuration from the environment / .env file in the repo root."""
    load_dotenv(override=True)
    return AppConfig(
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        ngspice_path=os.getenv("NGSPICE_PATH", "ngspice"),
        kicad_cli_path=os.getenv("KICAD_CLI_PATH") or None,
    )


# Module-level singleton, refreshed via reload_config().
config = load_config()


def reload_config() -> AppConfig:
    # Mutate in place: other modules hold `from backend.config import config`.
    vars(config).update(vars(load_config()))
    return config
