"""
Backend facade package wrapping the flat-imported core/ modules in a
hardened, GUI-friendly API.

core/ is not a proper Python package (its modules import each other with
bare names, e.g. `import hierarchical_reader`), so it must be put on
sys.path as a plain directory before any of its modules are imported
anywhere. Doing that here means every backend submodule gets it for free
just by importing `backend`.
"""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CORE_DIR = os.path.join(_REPO_ROOT, "core")

if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

# skidl opens <script>.log / <script>.erc in the CWD at import time; the app
# never uses them, so drop the handlers (which also deletes the files).
from skidl.logger import stop_log_file_output  # noqa: E402

stop_log_file_output()

# Verify TLS against the OS certificate store rather than certifi's bundle, so
# HTTPS to Gemini works behind corporate TLS-inspecting proxies.
import truststore  # noqa: E402

truststore.inject_into_ssl()
