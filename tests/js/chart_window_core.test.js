'use strict';

// chart_window_core.js 纯逻辑单测。
// 运行：node --test tests/js/
// pytest 门禁通过 tests/test_js_unit.py 自动执行本目录。

const { test } = require('node:test');
const assert = require('node:assert/strict');
const core = require('../../frontend/js/modules/chart_window_core.js');

test('createEmptyChartWindowState 返回完整空窗口结构', () => {
    const state = core.createEmptyChartWindowState();
    assert.deepEqual(state.kline_data, []);
    assert.deepEqual(state.volume_data, []);
    assert.deepEqual(state.trade_markers, []);
    assert.equal(state.has_earlier, false);
    assert.equal(state.has_later, false);
    assert.equal(state.read_only, false);
    assert.equal(state.period, 'daily');
});

test('formatIntradayPeriodBadge 周期别名映射', () => {
    assert.equal(core.formatIntradayPeriodBadge('1d'), '1D');
    assert.equal(core.formatIntradayPeriodBadge('2d'), '2D');
    assert.equal(core.formatIntradayPeriodBadge('3d'), '3D');
    assert.equal(core.formatIntradayPeriodBadge('4h_session'), '4h');
    assert.equal(core.formatIntradayPeriodBadge('weekly'), '1W');
    assert.equal(core.formatIntradayPeriodBadge('daily'), '1D');
    assert.equal(core.formatIntradayPeriodBadge('15m'), '15m');
    assert.equal(core.formatIntradayPeriodBadge('unknown'), '1D');
});

test('extractIntradaySnapshot 解包嵌套 snapshot', () => {
    const snapshot = { current_time: '2026-01-01 10:00:00' };
    assert.equal(core.extractIntradaySnapshot({ snapshot }), snapshot);
    assert.equal(core.extractIntradaySnapshot(snapshot), snapshot);
    assert.equal(core.extractIntradaySnapshot(null), null);
    assert.equal(core.extractIntradaySnapshot('text'), null);
});

test('intradayBarToTimestamp 转换为 UTC 秒时间戳', () => {
    assert.equal(
        core.intradayBarToTimestamp({ start_time: '2026-08-30 10:00:00' }),
        Math.floor(Date.UTC(2026, 7, 30, 10, 0, 0) / 1000)
    );
    assert.equal(core.intradayBarToTimestamp({ time: 12345 }), 12345);
    assert.equal(core.intradayBarToTimestamp({ end_time: '2026-08-30' }), Math.floor(Date.UTC(2026, 7, 30) / 1000));
    assert.equal(core.intradayBarToTimestamp({}), 0);
    assert.equal(core.intradayBarToTimestamp(null), 0);
});

test('buildIntradayKlineChartData 构造蜡烛数组', () => {
    const bars = [{ start_time: '2026-08-30 10:00:00', open: '1', high: '2', low: '0.5', close: '1.5', volume: '10' }];
    const chartData = core.buildIntradayKlineChartData(bars);
    assert.equal(chartData.length, 1);
    assert.equal(chartData[0].open, 1);
    assert.equal(chartData[0].volume, 10);
    assert.deepEqual(core.buildIntradayKlineChartData('bad'), []);
});

test('mergeTimedItems 按 time 去重（后到覆盖）并升序排序', () => {
    const merged = core.mergeTimedItems(
        [{ time: 2, v: 'old' }, { time: 1, v: 'a' }],
        [{ time: 2, v: 'new' }, { time: 3, v: 'c' }],
        (item) => item
    );
    assert.deepEqual(merged, [
        { time: 1, v: 'a' },
        { time: 2, v: 'new' },
        { time: 3, v: 'c' },
    ]);
    assert.deepEqual(core.mergeTimedItems(null, null, (item) => item), []);
});

test('mergeChartWindow 合并 K 线与成交量且不混合周期', () => {
    const base = core.createEmptyChartWindowState();
    base.kline_data = [{ time: 1, open: 1, high: 1, low: 1, close: 1, volume: 0 }];
    const next = {
        kline_data: [{ time: 2, open: 2, high: 2, low: 2, close: 2, volume: 0 }],
        volume_data: [{ time: 2, value: 5 }],
        trade_markers: [{ time: 2, position: 'belowBar' }],
        has_later: true,
    };
    const merged = core.mergeChartWindow(base, next);
    assert.deepEqual(merged.kline_data.map((bar) => bar.time), [1, 2]);
    assert.equal(merged.volume_data.length, 1);
    assert.equal(merged.trade_markers.length, 1);
    assert.equal(merged.has_later, true);
});

test('mergeChartWindow 未提供 trade_markers 时保留旧值', () => {
    const base = core.createEmptyChartWindowState();
    base.trade_markers = [{ time: 1 }];
    const merged = core.mergeChartWindow(base, { kline_data: [] });
    assert.equal(merged.trade_markers.length, 1);
});

test('parseChartWindowTimestamp 接受 Date/秒/毫秒/字符串', () => {
    const date = new Date(Date.UTC(2026, 0, 2, 3, 4, 5));
    assert.deepEqual(core.parseChartWindowTimestamp(date), date);
    assert.equal(core.parseChartWindowTimestamp(1788084000).getTime(), 1788084000 * 1000);
    assert.equal(core.parseChartWindowTimestamp('1788084000').getTime(), 1788084000 * 1000);
    assert.equal(core.parseChartWindowTimestamp('2026-08-30 10:00:00').getTime(), Date.UTC(2026, 7, 30, 10, 0, 0));
    assert.equal(core.parseChartWindowTimestamp('2026-08-30').getTime(), Date.UTC(2026, 7, 30));
    assert.equal(core.parseChartWindowTimestamp(''), null);
    assert.equal(core.parseChartWindowTimestamp('not-a-date'), null);
});

test('shiftChartWindowYear 平移年份并钳制闰日', () => {
    assert.equal(core.shiftChartWindowYear('2026-08-30 10:00:00', -1), '2025-08-30 10:00:00');
    assert.equal(core.shiftChartWindowYear('2024-02-29 00:00:00', 1), '2025-02-28 00:00:00');
    assert.equal(core.shiftChartWindowYear('', 1), '');
});

test('earlier/laterChartWindowTimestamp 比较并保留原始字符串', () => {
    assert.equal(core.earlierChartWindowTimestamp('2026-01-01', '2025-01-01'), '2025-01-01');
    assert.equal(core.laterChartWindowTimestamp('2026-01-01', '2025-01-01'), '2026-01-01');
    assert.equal(core.earlierChartWindowTimestamp(null, '2025-01-01'), '2025-01-01');
    assert.equal(core.laterChartWindowTimestamp(null, null), null);
});

test('normalizeChartCandle/Volume/Marker 归一化字段类型', () => {
    assert.deepEqual(
        core.normalizeChartCandle({ time: 100, open: '1', high: '2', low: '0.5', close: '1.5' }),
        { time: 100, open: 1, high: 2, low: 0.5, close: 1.5, volume: 0 }
    );
    assert.deepEqual(
        core.normalizeChartVolume({ time: 100, volume: '7' }),
        { time: 100, value: 7, color: '#999999' }
    );
    assert.deepEqual(core.normalizeChartMarker({ position: 'aboveBar', time: '2026-08-30' }).time,
        Math.floor(Date.UTC(2026, 7, 30) / 1000));
});
