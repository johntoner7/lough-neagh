"""Compatibility shim for running `python -m backend.*` from within `backend/`.

When the working directory is this `backend/` folder, Python cannot normally
import the top-level `backend` package (`../backend`). This package extends its
module search path to include the parent directory so existing absolute imports
like `backend.scripts.run_pipeline` continue to work.
"""

from __future__ import annotations

from pathlib import Path

_parent_backend_dir = Path(__file__).resolve().parent.parent
_parent_str = str(_parent_backend_dir)
if _parent_str not in __path__:
    __path__.append(_parent_str)
