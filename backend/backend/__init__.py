"""Compatibility shim for running `python -m backend.*` from within `backend/`.

When the working directory is this `backend/` folder, Python cannot normally
import the top-level `backend` package (`../backend`). This package extends its
module search path to include the parent directory so existing absolute imports
like `backend.scripts.run_pipeline` continue to work.
"""

from __future__ import annotations

import sys
from pathlib import Path

# `backend/backend/__init__.py` -> parent `backend/` directory containing
# `scripts`, `pipeline`, and `api`.
_parent_backend_dir = Path(__file__).resolve().parent.parent
_parent_str = str(_parent_backend_dir)
_module = sys.modules[__name__]
_package_path = list(getattr(_module, "__path__", []))
if _parent_str not in _package_path:
    _package_path.append(_parent_str)
_module.__path__ = _package_path
