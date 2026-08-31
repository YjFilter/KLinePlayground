"""Shared frontend JS loader for static contract tests.

The browser shares top-level bindings across all ``<script>`` tags, so a
helper may live in ``main_enhanced.js`` or in ``frontend/js/modules/``.
Concatenating the files in the exact order declared by
``frontend/index_enhanced.html`` reproduces that combined scope, keeping the
static assertions valid regardless of where a helper currently lives.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = PROJECT_ROOT / "frontend" / "index_enhanced.html"


def load_frontend_js() -> str:
    """Return all page scripts concatenated in their declared load order."""
    html = INDEX_PATH.read_text(encoding="utf-8")
    sources = re.findall(r'<script src="(js/[^"]+)"', html)
    parts = [
        (PROJECT_ROOT / "frontend" / src.split("?", 1)[0]).read_text(encoding="utf-8")
        for src in sources
    ]
    return "\n\n".join(parts)
