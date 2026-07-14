"""TASK-013: Static contract tests for the intraday frontend wiring.

These tests inspect ``frontend/js/main_enhanced.js`` as plain text without
launching a browser. They verify the static contracts the task requires:

* ``startTraining`` reads ``#kline-period`` and explicitly sends
  ``data_mode: intraday_30m``.
* Intraday period switching uses the ``/period`` endpoint and does **not**
  call ``/next`` inside that switching branch.
* All four exact period values (``30m``, ``4h_session``, ``daily``,
  ``weekly``) are referenced.
* Intraday snapshot status IDs (``#current-replay-time``,
  ``#next-boundary-time``, ``#current-bar-status``) and completion classes
  (``incomplete-candle``, ``bar-status-incomplete``, ``bar-status-complete``)
  are referenced.
* Intraday ``next`` handles ``response.snapshot`` (via the
  ``extractIntradaySnapshot`` helper) and the ``finished`` flag.
* Intraday ``start`` does **not** auto-call ``nextBar``.
* Legacy data-loading behavior remains present behind a non-intraday branch.

Only ``tests/test_intraday_frontend_static.py`` and
``frontend/js/main_enhanced.js`` are created/modified. No browser, BaoStock,
or external network access is required.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
JS_PATH = PROJECT_ROOT / "frontend" / "js" / "main_enhanced.js"


def _load_js() -> str:
    """Read the frontend JavaScript source as UTF-8 text."""
    with open(JS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


class _StaticTestCase(unittest.TestCase):
    """Base helper that loads the JS source once per test class."""

    @classmethod
    def setUpClass(cls):  # noqa: D401 - unittest hook
        cls.js = _load_js()

    def assertContains(self, needle: str, msg: str | None = None) -> None:
        self.assertIn(needle, self.js, msg)

    def assertNotContains(self, needle: str, msg: str | None = None) -> None:
        self.assertNotIn(needle, self.js, msg)


class StartReadsPeriodAndSendsDataModeTests(_StaticTestCase):
    """startTraining 必须从 #kline-period 读取周期并显式发送 data_mode: intraday_30m。"""

    def test_start_reads_kline_period_select(self):
        # 必须读取 #kline-period 下拉的值，而不是硬编码 'daily'
        self.assertContains("getElementById('kline-period')")

    def test_start_sends_intraday_data_mode(self):
        # 多周期训练启动必须显式声明 data_mode: intraday_30m
        self.assertContains("INTRADAY_DATA_MODE = 'intraday_30m'")
        self.assertContains("data_mode: INTRADAY_DATA_MODE")

    def test_start_sends_actual_trading_day_limit(self):
        self.assertContains("max_training_days:")
        start_idx = self.js.find("async function startTraining")
        next_func_idx = self.js.find("\nasync function ", start_idx + 1)
        start_body = self.js[start_idx:next_func_idx]
        self.assertNotIn("max_bars:", start_body)

    def test_start_no_hardcoded_daily_period(self):
        # 不应再硬编码 const period = 'daily';
        self.assertNotContains("const period = 'daily';")

    def test_start_does_not_auto_call_nextbar_in_intraday_branch(self):
        # 在 intraday 分支里不应出现自动 nextBar() 调用
        # legacy 分支允许 setTimeout(() => { nextBar(); }, 100)
        # 我们检查 startTraining 函数体内的 intraday 分支段
        start_idx = self.js.find("async function startTraining")
        self.assertGreater(start_idx, 0, "缺少 startTraining 函数")
        # startTraining 函数体边界：到下一个 async function 为止
        next_func_idx = self.js.find("\nasync function ", start_idx + 1)
        self.assertGreater(next_func_idx, 0)
        start_body = self.js[start_idx:next_func_idx]
        # 在 startTraining 内找 intraday 分支
        intraday_idx = start_body.find("if (isIntradayMode())")
        self.assertGreater(intraday_idx, 0, "startTraining 中缺少 intraday 分支")
        # intraday 分支结束于 legacy 分支标记之前
        legacy_idx = start_body.find("// === legacy_daily 分支", intraday_idx)
        self.assertGreater(legacy_idx, 0, "找不到 legacy 分支标记")
        intraday_branch = start_body[intraday_idx:legacy_idx]
        self.assertNotIn("nextBar()", intraday_branch,
                         "intraday start 分支不得自动调用 nextBar()")
        self.assertNotIn("setTimeout", intraday_branch,
                         "intraday start 分支不得使用 setTimeout 推进回放")

    def test_start_renders_initial_snapshot_directly(self):
        # intraday start 必须直接渲染 start 返回的顶层 snapshot
        start_idx = self.js.find("async function startTraining")
        self.assertGreater(start_idx, 0)
        next_func_idx = self.js.find("\nasync function ", start_idx + 1)
        self.assertGreater(next_func_idx, 0)
        start_body = self.js[start_idx:next_func_idx]
        intraday_idx = start_body.find("if (isIntradayMode())")
        self.assertGreater(intraday_idx, 0)
        legacy_idx = start_body.find("// === legacy_daily 分支", intraday_idx)
        self.assertGreater(legacy_idx, 0)
        intraday_branch = start_body[intraday_idx:legacy_idx]
        self.assertIn("extractIntradaySnapshot", intraday_branch)
        self.assertIn("applyIntradaySnapshot", intraday_branch)


class PeriodSwitchEndpointTests(_StaticTestCase):
    """周期切换必须调用 /period，不调用 /next。"""

    def test_period_switch_uses_period_endpoint(self):
        # switchViewPeriod 的 intraday 分支必须 POST /period
        idx = self.js.find("async function switchViewPeriod")
        self.assertGreater(idx, 0, "缺少 switchViewPeriod 函数")
        # 截取 switchViewPeriod 函数体（到下一个 async function 为止）
        next_func = self.js.find("\nasync function ", idx + 1)
        self.assertGreater(next_func, 0)
        body = self.js[idx:next_func]
        self.assertIn("/period", body, "intraday 周期切换必须调用 /period 接口")
        # body 必须包含 JSON.stringify({ period: ... }) 形式的请求体
        # JS 对象字面量中 period 可以带引号也可以不带，匹配 "period:" 模式
        import re
        period_body_pattern = re.compile(r"JSON\.stringify\(\s*\{\s*['\"]?period['\"]?\s*:")
        self.assertTrue(period_body_pattern.search(body),
                        "intraday 周期切换必须发送 period body")

    def test_period_switch_does_not_call_next_in_intraday_branch(self):
        # intraday 周期切换分支不得调用 /next
        idx = self.js.find("async function switchViewPeriod")
        # 取 switchViewPeriod 整个函数体
        next_func = self.js.find("\nasync function ", idx + 1)
        body = self.js[idx:next_func]
        # 找到 intraday 分支段
        intraday_start = body.find("if (isIntradayMode()) {")
        self.assertGreater(intraday_start, 0, "switchViewPeriod 缺少 intraday 分支")
        # intraday 分支结束于 legacy 分支标记之前
        legacy_marker = body.find("// === legacy_daily 分支", intraday_start)
        if legacy_marker == -1:
            # 也可能是另一种结束标记
            legacy_marker = body.find("const legacyNext", intraday_start)
        self.assertGreater(legacy_marker, 0, "找不到 legacy 分支边界")
        intraday_branch = body[intraday_start:legacy_marker]
        self.assertNotIn("/next", intraday_branch,
                         "intraday 周期切换分支不得调用 /next")
        self.assertNotIn("nextBar(", intraday_branch,
                         "intraday 周期切换分支不得调用 nextBar")


class FourPeriodsHandledTests(_StaticTestCase):
    """四个 intraday 周期值必须都被引用与处理。"""

    def test_intraday_periods_constant_lists_four_values(self):
        # INTRADAY_PERIODS 必须列出四个精确值
        self.assertContains("const INTRADAY_PERIODS = ['30m', '4h_session', 'daily', 'weekly'];")

    def test_each_period_value_appears_in_source(self):
        for period in ("30m", "4h_session", "daily", "weekly"):
            self.assertIn(period, self.js, f"周期值 {period} 未在源码中出现")

    def test_period_badge_handles_all_four(self):
        # formatIntradayPeriodBadge 必须处理四个周期
        idx = self.js.find("function formatIntradayPeriodBadge")
        self.assertGreater(idx, 0, "缺少 formatIntradayPeriodBadge 函数")
        func_body = self.js[idx:idx + 600]
        for period in ("'30m'", "'4h_session'", "'weekly'", "'daily'"):
            self.assertIn(period, func_body,
                          f"formatIntradayPeriodBadge 未处理周期 {period}")


class IntradayStatusIdsAndCompletionClassesTests(_StaticTestCase):
    """intraday 快照状态元素与完成态 class 必须被引用。"""

    def test_status_ids_referenced(self):
        for element_id in ("current-replay-time", "next-boundary-time", "current-bar-status"):
            self.assertIn(element_id, self.js,
                          f"intraday 状态元素 #{element_id} 未被引用")

    def test_completion_classes_referenced(self):
        for cls in ("incomplete-candle", "bar-status-incomplete", "bar-status-complete"):
            self.assertIn(cls, self.js,
                          f"intraday 完成态 class {cls} 未被引用")

    def test_update_intraday_replay_status_function_exists(self):
        idx = self.js.find("function updateIntradayReplayStatus")
        self.assertGreater(idx, 0, "缺少 updateIntradayReplayStatus 函数")

    def test_toggle_classes_use_current_bar_complete(self):
        idx = self.js.find("function updateIntradayReplayStatus")
        func_body = self.js[idx:idx + 1200]
        self.assertIn("current_bar_complete", func_body,
                      "updateIntradayReplayStatus 必须依据 current_bar_complete 切换 class")


class IntradayNextResponseShapeTests(_StaticTestCase):
    """intraday next 必须处理 response.snapshot 与 finished。"""

    def test_extract_intraday_snapshot_helper_exists(self):
        idx = self.js.find("function extractIntradaySnapshot")
        self.assertGreater(idx, 0, "缺少 extractIntradaySnapshot 辅助函数")
        body = self.js[idx:idx + 500]
        # 必须支持 response.snapshot 形态
        self.assertIn("response.snapshot", body,
                      "extractIntradaySnapshot 必须识别 response.snapshot")

    def test_next_uses_extract_intraday_snapshot(self):
        # nextBar 的 intraday 分支必须使用 extractIntradaySnapshot 处理响应
        idx = self.js.find("async function nextBar")
        self.assertGreater(idx, 0, "缺少 nextBar 函数")
        body = self.js[idx:idx + 3000]
        self.assertIn("extractIntradaySnapshot", body,
                      "nextBar 必须使用 extractIntradaySnapshot 解析 intraday 响应")
        self.assertIn("response.snapshot", self.js,
                      "源码中应明确注释 response.snapshot 来源")

    def test_next_handles_finished_flag(self):
        # nextBar 的 intraday 分支必须检查 finished 字段
        idx = self.js.find("async function nextBar")
        body = self.js[idx:idx + 3000]
        # intraday 分支必须在 finished 时 pausePlayback + showReport
        self.assertIn("data.finished", body,
                      "nextBar 必须检查 data.finished 字段")

    def test_next_stops_playback_on_finished(self):
        idx = self.js.find("async function nextBar")
        body = self.js[idx:idx + 3000]
        # finished 分支必须 pausePlayback
        finished_idx = body.find("if (data.finished)")
        self.assertGreater(finished_idx, 0, "nextBar 缺少 finished 分支")
        finished_branch = body[finished_idx:finished_idx + 400]
        self.assertIn("pausePlayback", finished_branch,
                      "intraday finished 必须停止自动播放")


class ResetSnapshotTests(_StaticTestCase):
    """intraday reset 必须渲染 response.snapshot 并同步 active_period。"""

    def test_reset_uses_extract_intraday_snapshot(self):
        idx = self.js.find("async function resetTraining")
        self.assertGreater(idx, 0, "缺少 resetTraining 函数")
        body = self.js[idx:idx + 2500]
        intraday_marker = body.find("isIntradayMode()")
        self.assertGreater(intraday_marker, 0, "resetTraining 缺少 intraday 分支")
        intraday_branch = body[intraday_marker:]
        self.assertIn("extractIntradaySnapshot", intraday_branch,
                      "resetTraining intraday 分支必须使用 extractIntradaySnapshot")
        self.assertIn("applyIntradaySnapshot", intraday_branch,
                      "resetTraining intraday 分支必须重新渲染快照")
        self.assertIn("syncIntradayActivePeriod", self.js,
                      "缺少 syncIntradayActivePeriod 调用以同步 active_period")


class LegacyBranchPreservedTests(_StaticTestCase):
    """非 intraday 模式必须保留 legacy 数据加载与 nextBar 推进路径。"""

    def test_legacy_load_initial_data_present(self):
        # legacy 分支必须保留对 /data 的 fetch 与 applyTrainingSnapshot
        idx = self.js.find("async function loadInitialData")
        self.assertGreater(idx, 0)
        body = self.js[idx:idx + 5000]
        self.assertIn("legacy_daily", body,
                      "loadInitialData 必须保留 legacy_daily 分支标记")
        self.assertIn("applyTrainingSnapshot", body,
                      "legacy loadInitialData 必须继续调用 applyTrainingSnapshot")
        # legacy 分支必须保留指标与筹码分布调用
        self.assertIn("loadTechnicalIndicator", body,
                      "legacy loadInitialData 必须保留 loadTechnicalIndicator 调用")

    def test_legacy_next_advances_via_new_bar(self):
        idx = self.js.find("async function nextBar")
        body = self.js[idx:idx + 5000]
        self.assertIn("legacy_daily", body,
                      "nextBar 必须保留 legacy_daily 分支标记")
        self.assertIn("data.new_bar", body,
                      "legacy nextBar 必须继续使用 data.new_bar 推进")
        self.assertIn("data.requires_full_refresh", body,
                      "legacy nextBar 必须保留 requires_full_refresh 处理")

    def test_legacy_switch_view_period_present(self):
        idx = self.js.find("async function switchViewPeriod")
        body = self.js[idx:idx + 3000]
        self.assertIn("legacy_daily", body,
                      "switchViewPeriod 必须保留 legacy_daily 分支")
        self.assertIn("refreshTrainingView", body,
                      "legacy switchViewPeriod 必须继续调用 refreshTrainingView")

    def test_is_intraday_mode_helper_exists(self):
        idx = self.js.find("function isIntradayMode")
        self.assertGreater(idx, 0, "缺少 isIntradayMode 辅助函数")
        body = self.js[idx:idx + 300]
        self.assertIn("INTRADAY_DATA_MODE", body,
                      "isIntradayMode 必须基于 INTRADAY_DATA_MODE 判断")
        self.assertIn("currentTraining.data_mode", body,
                      "isIntradayMode 必须检查 currentTraining.data_mode")


class IntradayAvoidsLegacyOnlyEndpointsTests(_StaticTestCase):
    """intraday 模式必须避免请求依赖 legacy kline_processor 的接口。"""

    def test_chip_distribution_skipped_for_intraday(self):
        idx = self.js.find("async function updateChipDistribution")
        body = self.js[idx:idx + 2500]
        self.assertIn("isIntradayMode()", body,
                      "updateChipDistribution 必须在 intraday 模式提前返回")

    def test_load_technical_indicator_skipped_for_intraday(self):
        idx = self.js.find("async function loadTechnicalIndicator")
        body = self.js[idx:idx + 1500]
        self.assertIn("isIntradayMode()", body,
                      "loadTechnicalIndicator 必须在 intraday 模式提前返回")

    def test_update_adjustment_skipped_for_intraday(self):
        idx = self.js.find("async function updateAdjustment")
        body = self.js[idx:idx + 1500]
        self.assertIn("isIntradayMode()", body,
                      "updateAdjustment 必须在 intraday 模式提前返回")

    def test_start_auto_sync_skipped_for_intraday(self):
        idx = self.js.find("function startAutoSync")
        body = self.js[idx:idx + 1500]
        self.assertIn("isIntradayMode()", body,
                      "startAutoSync 必须在 intraday 模式提前返回")


class RuntimeCompatibilityTests(_StaticTestCase):
    """覆盖静态测试容易遗漏的真实浏览器兼容分支。"""

    def test_random_mode_uses_intraday_for_all_periods(self):
        start_idx = self.js.find("async function startTraining")
        next_func_idx = self.js.find("\nasync function ", start_idx + 1)
        start_body = self.js[start_idx:next_func_idx]
        self.assertIn("data_mode: INTRADAY_DATA_MODE", start_body)
        self.assertNotIn("isRandomMode && period !== 'daily'", start_body)
        self.assertNotIn("盲盒模式目前仅支持日线启动", start_body)

    def test_intraday_timestamp_preserves_market_wall_clock(self):
        idx = self.js.find("function intradayBarToTimestamp")
        body = self.js[idx:idx + 1200]
        self.assertIn("Date.UTC", body)
        self.assertNotIn("+08:00", body)


class IntradayVolumeFromKlineTests(_StaticTestCase):
    """intraday 成交量必须从 snapshot.kline_data 的 volume 字段构造。"""

    def test_build_intraday_volume_data_function_exists(self):
        idx = self.js.find("function buildIntradayVolumeData")
        self.assertGreater(idx, 0, "缺少 buildIntradayVolumeData 函数")
        body = self.js[idx:idx + 800]
        self.assertIn("volume", body,
                      "buildIntradayVolumeData 必须读取 volume 字段")
        self.assertIn("klineData", body,
                      "buildIntradayVolumeData 必须接收 klineData 参数")

    def test_apply_intraday_snapshot_uses_kline_data(self):
        idx = self.js.find("function applyIntradaySnapshot")
        self.assertGreater(idx, 0, "缺少 applyIntradaySnapshot 函数")
        body = self.js[idx:idx + 2500]
        self.assertIn("snapshot.kline_data", body,
                      "applyIntradaySnapshot 必须从 snapshot.kline_data 读取数据")
        self.assertIn("buildIntradayVolumeData", body,
                      "applyIntradaySnapshot 必须用 buildIntradayVolumeData 构造成交量")


class PlaybackSingleNextPerAdvanceTests(_StaticTestCase):
    """播放每次只调用一次 /next；推进单位由 active_period 决定。"""

    def test_playback_uses_nextbar_only(self):
        idx = self.js.find("async function playbackTick")
        body = self.js[idx:idx + 900]
        self.assertIn("await nextBar()", body,
                      "playbackTick 必须以 nextBar 作为唯一推进入口")

    def test_playback_waits_for_next_before_scheduling_again(self):
        idx = self.js.find("async function playbackTick")
        self.assertGreater(idx, 0, "缺少串行 playbackTick")
        body = self.js[idx:idx + 900]
        self.assertIn("await nextBar()", body)
        self.assertIn("setTimeout(playbackTick", body)
        self.assertNotIn("setInterval(nextBar", self.js)
    def test_intraday_next_does_not_loop(self):
        # nextBar 的 intraday 分支只能调用一次 /next
        idx = self.js.find("async function nextBar")
        intraday_marker = self.js.find("isIntradayMode()", idx)
        self.assertGreater(intraday_marker, 0)
        # 取到 intraday 分支结束（legacy 分支标记）
        legacy_marker = self.js.find("// === legacy_daily 分支", intraday_marker)
        self.assertGreater(legacy_marker, 0)
        intraday_branch = self.js[intraday_marker:legacy_marker]
        # intraday 分支内 fetch /next 应只出现一次
        self.assertEqual(intraday_branch.count("/next"), 1,
                         "intraday nextBar 必须只调用一次 /next")
        # 不应自调用
        self.assertNotIn("nextBar(", intraday_branch,
                         "intraday nextBar 不得自调用 nextBar()")


if __name__ == "__main__":
    unittest.main()
