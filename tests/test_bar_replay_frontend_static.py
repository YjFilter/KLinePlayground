from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
HTML_PATH = ROOT_DIR / "frontend" / "index_enhanced.html"
CSS_PATH = ROOT_DIR / "frontend" / "css" / "style_enhanced.css"
MAIN_JS_PATH = ROOT_DIR / "frontend" / "js" / "main_enhanced.js"
MODULE_JS_PATH = ROOT_DIR / "frontend" / "js" / "modules" / "bar_replay.js"


def test_html_bar_replay_elements():
    """验证 index_enhanced.html 包含截断复盘所需的所有 DOM 元素与脚本引用"""
    html = HTML_PATH.read_text(encoding="utf-8")

    # 1. 顶部控制栏复盘按钮
    assert 'id="chart-bar-replay-btn"' in html
    assert "复盘" in html

    # 2. 截断指示线与提示标签
    assert 'id="chart-replay-cut-indicator"' in html
    assert "cut-indicator-line" in html
    assert "cut-indicator-badge" in html

    # 3. 悬浮复盘控制 HUD 工具栏及其操作按钮与拖拽手柄
    assert 'id="chart-bar-replay-bar"' in html
    assert 'class="replay-bar-drag-handle"' in html
    assert 'id="replay-reselect-cut-btn"' in html
    assert 'id="replay-play-pause-btn"' in html
    assert 'id="replay-step-forward-btn"' in html
    assert 'id="replay-speed-select"' in html
    assert 'id="replay-progress-time"' in html
    assert 'id="replay-progress-fraction"' in html
    assert 'id="replay-exit-btn"' in html

    # 4. 模块加载脚本
    assert '<script src="js/modules/bar_replay.js"></script>' in html


def test_css_bar_replay_selectors():
    """验证 style_enhanced.css 包含复盘样式、悬浮工具栏置顶与自由拖拽样式、光标剪切样式"""
    css = CSS_PATH.read_text(encoding="utf-8")

    assert "#chart-bar-replay-btn.active" in css
    assert ".chart-panels.bar-replay-cutting" in css
    assert ".chart-replay-cut-indicator" in css
    assert ".cut-indicator-line" in css
    assert ".cut-indicator-badge" in css
    assert ".chart-bar-replay-bar" in css
    assert "top: 64px;" in css
    assert ".replay-bar-drag-handle" in css
    assert "cursor: grab;" in css
    assert ".chart-bar-replay-bar.dragging" in css
    assert ".replay-bar-btn" in css
    assert ".replay-play-btn" in css
    assert ".replay-speed-select" in css
    assert ".replay-exit-btn" in css


def test_main_js_bar_replay_wiring():
    """验证 main_enhanced.js 包含完整的状态机、切片更新、量能同步、悬浮栏拖拽、跨周期联动、键盘快捷键与轮询保护"""
    js = MAIN_JS_PATH.read_text(encoding="utf-8")

    assert "barReplayState" in js
    assert "latestRenderedVolumeData" in js
    assert "initBarReplayToolbarEvents" in js
    assert "registerBarReplayChartEvents" in js
    assert "enterBarReplayCutSelection" in js
    assert "cancelBarReplayCutSelection" in js
    assert "executeBarReplayCut" in js
    assert "stepBarReplayForward" in js
    assert "playBarReplay" in js
    assert "pauseBarReplay" in js
    assert "toggleBarReplayPlayPause" in js
    assert "exitBarReplay" in js
    assert "updateBarReplayProgressUI" in js
    assert "updateBarReplayCutIndicator" in js
    assert "handleBarReplayPeriodSwitch" in js

    # 悬浮栏自由拖拽
    assert "dragBound" in js
    assert "replay-bar-drag-handle" in js
    assert "onDragStart" in js
    assert "onDragMove" in js
    assert "onDragEnd" in js

    # 量能数据流水线完整传递
    assert "barReplayState.fullVolumeData" in js
    assert "extractVolumeFromKlines" in js
    assert "latestRenderedVolumeData = formattedVols.map" in js

    # 快捷键映射
    assert "shortcutKey === 'p' || shortcutKey === 'r'" in js
    assert "barReplayState.isSelectingCutPoint" in js
    assert "barReplayState.active" in js

    # 实时轮询阻断
    assert "barReplayState && barReplayState.active" in js


def test_bar_replay_module_exports():
    """验证 bar_replay.js 模块结构与核心函数定义"""
    assert MODULE_JS_PATH.exists()
    content = MODULE_JS_PATH.read_text(encoding="utf-8")

    assert "findBarIndexByTimestamp" in content
    assert "sliceKlineData" in content
    assert "getNextReplayStep" in content
    assert "formatReplayTime" in content
    assert "mapReplayCutToNewPeriod" in content
    assert "createBarReplayState" in content
    assert "KLineBarReplayModule" in content
