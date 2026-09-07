'use strict';

// trading_hours.js 单测。
// 运行：node --test tests/js/

const { test } = require('node:test');
const assert = require('node:assert/strict');
const th = require('../../frontend/js/modules/trading_hours.js');

// 图表 X 轴时间戳直接对应墙上时间（如 08:00 即 08:00:00 UTC）
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

test('8-24 全天窗口：整日可视返回单段（精确对齐 08:00~24:00）', () => {
    const segments = th.computeTradingHourSegments(day0, day0 + 86400, { start: 8, end: 24 });
    assert.equal(segments.length, 1);
    assert.equal(iso(segments[0][0]), '2026-08-30T08:00:00.000Z'); // 08:00
    assert.equal(iso(segments[0][1]), '2026-08-31T00:00:00.000Z'); // 24:00
});

test('22-06 跨午夜窗口：可视日内两段', () => {
    const segments = th.computeTradingHourSegments(day0, day0 + 86400, { start: 22, end: 6 });
    assert.equal(segments.length, 2);
    // 00:00-06:00（前夜窗口的尾段）
    assert.equal(iso(segments[0][0]), '2026-08-30T00:00:00.000Z');
    assert.equal(iso(segments[0][1]), '2026-08-30T06:00:00.000Z');
    // 22:00-24:00
    assert.equal(iso(segments[1][0]), '2026-08-30T22:00:00.000Z');
    assert.equal(iso(segments[1][1]), '2026-08-31T00:00:00.000Z');
});

test('子窗口精确裁剪到可视范围', () => {
    const from = day0 + 9 * 3600;
    const to = day0 + 10 * 3600;
    const segments = th.computeTradingHourSegments(from, to, { start: 8, end: 24 });
    assert.deepEqual(segments, [[from, to]]);
});

test('跨天可视返回多段', () => {
    const segments = th.computeTradingHourSegments(day0 + 6 * 3600, day0 + 42 * 3600, { start: 8, end: 24 });
    assert.equal(segments.length, 2);
    assert.equal(iso(segments[0][0]), '2026-08-30T08:00:00.000Z');
    assert.equal(iso(segments[1][0]), '2026-08-31T08:00:00.000Z');
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
