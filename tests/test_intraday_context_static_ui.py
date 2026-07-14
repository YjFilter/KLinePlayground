"""Static UI contracts for historical chart-window controls."""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = PROJECT_ROOT / "frontend" / "index_enhanced.html"
CSS_PATH = PROJECT_ROOT / "frontend" / "css" / "style_enhanced.css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_historical_window_control_ids_are_unique() -> None:
    html = _read(HTML_PATH)

    for element_id in (
        "load-earlier-year-btn",
        "load-later-year-btn",
        "chart-window-status",
        "training-day-limit-help",
    ):
        matches = re.findall(rf'\bid=["\']{re.escape(element_id)}["\']', html)
        assert len(matches) == 1, f"#{element_id} must appear exactly once"


def test_historical_window_markup_contract() -> None:
    html = _read(HTML_PATH)

    assert '<button id="load-earlier-year-btn" type="button">往前加载一年</button>' in html
    assert (
        '<button id="load-later-year-btn" type="button" class="hidden">往后加载一年</button>'
        in html
    )
    assert '<span id="chart-window-status" aria-live="polite"></span>' in html


def test_training_limit_uses_real_trading_day_wording() -> None:
    html = _read(HTML_PATH)

    assert "训练交易日限制（0=不限制）" in html
    assert "K线数量限制" not in html
    assert "按实际交易日期统计" in html
    assert "不是30分钟K线根数" in html
    assert "也不是当前显示周期K线根数" in html


def test_training_limit_is_shared_by_specified_and_random_modes() -> None:
    html = _read(HTML_PATH)
    shared_form_start = html.index('<div class="form-grid">', html.index('id="random-tab"'))
    limit_position = html.index('id="max-training-bars"')

    assert limit_position > shared_form_start


def test_chart_window_toolbar_has_required_states() -> None:
    css = _read(CSS_PATH)

    assert ".chart-window-toolbar" in css
    assert ".chart-window-toolbar.is-loading" in css
    assert ".chart-window-toolbar button:disabled" in css
    assert ".chart-window-toolbar .hidden" in css
