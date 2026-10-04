"""
Backend-wide exception hierarchy.

The GUI catches BackendError (and its subclasses) to show a friendly,
actionable error dialog. Anything else propagates up to
root.report_callback_exception as an unexpected-error safety net.
"""


class BackendError(Exception):
    """Base class for all errors raised by the backend/ package."""


class BoardNotFoundError(BackendError):
    """Raised when a requested board name has no Boards/<name>/ directory."""


class BoardFileMissingError(BackendError):
    """Raised when a required input file (netlist, SPICE export, questions, ...) is missing."""


class MissingDependencyError(BackendError):
    """Raised when an external tool (ngspice, kicad-cli) is not available."""


class SimulationError(BackendError):
    """Raised when an ngspice simulation fails or produces unusable output."""


class LLMConfigError(BackendError):
    """Raised when the LLM client is used without the required configuration (e.g. API key)."""


class LLMRequestError(BackendError):
    """Raised when an LLM request fails after exhausting retries."""
