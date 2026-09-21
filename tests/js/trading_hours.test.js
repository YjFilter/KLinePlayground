'use strict';

// trading_hours.js 单测。
// 运行：node --test tests/js/

const { test } = require('node:test');
const assert = require('node:assert/strict');
const th = require('../../frontend/js/modules/trading_hours.js');

// 图表显示层已按北京时间（UTC+8）渲染，时段窗口按东八区换算回 UTC 时间戳：
// 北京 08:00 = 00:00:00Z，北京 24:00 = 16:00:00Z（当日）。
const day0 = Date.UTC(2026, 7, 30, 0, 0, 0) / 1000;
const iso = (sec) => new Date(sec * 1000).toISOString();

test('周期门控：4H 及以下才显示时段色带（包含 4H）', () => {
    for (const period of ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '3h', '4h']) {
        assert.equal(th.isIntradayCryptoPeriod(period), true, period);
    }
    for (const period of ['6h', '8h', '12h', 'daily', '2d', '3d', 'weekly', '', undefined]) {
        assert.equal(th.isIntradayCryptoPeriod(period), false, String(period));
    }
});

test('8-24 全天窗口：默认东八区，可视返回单段（北京 08:00~24:00 = 00:00Z~16:00Z）', () => {
    const segments = th.computeTradingHourSegments(day0, day0 + 86400, { start: 8, end: 24 });
    assert.equal(segments.length, 1);
    assert.equal(iso(segments[0][0]), '2026-08-30T00:00:00.000Z');
    assert.equal(iso(segments[0][1]), '2026-08-30T16:00:00.000Z');
});

test('显式 tzOffsetMinutes=0 可覆盖默认值，窗口按图表时间原文对齐', () => {
    const segments = th.computeTradingHourSegments(day0, day0 + 86400, { start: 8, end: 24 }, 0);
    assert.equal(segments.length, 1);
    assert.equal(iso(segments[0][0]), '2026-08-30T08:00:00.000Z');
    assert.equal(iso(segments[0][1]), '2026-08-31T00:00:00.000Z');
});

test('22-06 跨午夜窗口：北京一整日内两段', () => {
    const from = day0 - 8 * 3600; // 北京 08-30 00:00
    const to = day0 + 16 * 3600;  // 北京 08-31 00:00
    const segments = th.computeTradingHourSegments(from, to, { start: 22, end: 6 });
    assert.equal(segments.length, 2);
    // 北京 00:00-06:00 = 16:00Z-22:00Z（前一日）
    assert.equal(iso(segments[0][0]), '2026-08-29T16:00:00.000Z');
    assert.equal(iso(segments[0][1]), '2026-08-29T22:00:00.000Z');
    // 北京 22:00-24:00 = 14:00Z-16:00Z
    assert.equal(iso(segments[1][0]), '2026-08-30T14:00:00.000Z');
    assert.equal(iso(segments[1][1]), '2026-08-30T16:00:00.000Z');
});

test('子窗口精确裁剪到可视范围', () => {
    const from = day0 + 9 * 3600;  // 北京 17:00，在 08-24 窗口内
    const to = day0 + 10 * 3600;   // 北京 18:00
    const segments = th.computeTradingHourSegments(from, to, { start: 8, end: 24 });
    assert.deepEqual(segments, [[from, to]]);
});

test('跨天可视返回多段', () => {
    const segments = th.computeTradingHourSegments(day0 + 6 * 3600, day0 + 42 * 3600, { start: 8, end: 24 });
    assert.equal(segments.length, 2);
    assert.equal(iso(segments[0][0]), '2026-08-30T06:00:00.000Z');
    assert.equal(iso(segments[1][0]), '2026-08-31T00:00:00.000Z');
});

test('起止相等视为关闭，无分段', () => {
    assert.deepEqual(th.computeTradingHourSegments(day0, day0 + 86400, { start: 8, end: 8 }), []);
});

test('非法输入返回空', () => {
    assert.deepEqual(th.computeTradingHourSegments(NaN, day0, { start: 8, end: 24 }), []);
    assert.deepEqual(th.computeTradingHourSegments(day0, day0, { start: 8, end: 24 }), []);
    assert.deepEqual(th.computeTradingHourSegments(day0 + 1, day0, { start: 8, end: 24 }), []);
});

test('时段设置读写与钳制', () => {
    const before = th.getTradingHours();
    assert.equal(th.setTradingHours(9, 23).start, 9);
    assert.equal(th.getTradingHours().end, 23);
    // 非法值被忽略
    th.setTradingHours(-1, 99);
    assert.equal(th.getTradingHours().start, 9);
    assert.equal(th.getTradingHours().end, 23);
    th.setTradingHours(before.start, before.end);
});
