'use strict';

// price_alerts.js 单测。
// 运行：node --test tests/js/

const { test } = require('node:test');
const assert = require('node:assert/strict');
const alerts = require('../../frontend/js/modules/price_alerts.js');

test('价格归一：按 A股 0.01 元最小变动单位取整', () => {
    assert.equal(alerts.normalizeAlertPrice(87.723), 87.72);
    assert.equal(alerts.normalizeAlertPrice(87.726), 87.73);
    assert.equal(alerts.normalizeAlertPrice('90'), 90);
});

test('价格归一：非法值与非正数一律判为无效', () => {
    for (const bad of [0, -1, NaN, Infinity, null, undefined, '', 'abc', {}]) {
        assert.equal(alerts.normalizeAlertPrice(bad), null, String(bad));
    }
});

test('方向推导：高于现价 = 涨至，低于现价 = 跌至', () => {
    assert.equal(alerts.deriveAlertDirection(95, 88), 'up');
    assert.equal(alerts.deriveAlertDirection(87.72, 88), 'down');
});

test('方向推导：与现价相等归为跌至（避免刚创建就报涨至）', () => {
    assert.equal(alerts.deriveAlertDirection(88, 88), 'down');
});

test('方向推导：现价无效时退化为跌至，不抛异常', () => {
    assert.equal(alerts.deriveAlertDirection(88, 0), 'down');
    assert.equal(alerts.deriveAlertDirection(88, NaN), 'down');
});

test('穿越判定·跌至：价格下穿阈值时触发', () => {
    const alert = { price: 90, direction: 'down', enabled: true, triggeredAt: null };
    assert.equal(alerts.evaluateAlertCrossing(alert, 91, 89.9), true);
});

test('穿越判定·跌至：价格恰好停在阈值上也算触发（prev > 阈值 >= now）', () => {
    const alert = { price: 90, direction: 'down', enabled: true, triggeredAt: null };
    assert.equal(alerts.evaluateAlertCrossing(alert, 90.5, 90), true);
});

test('穿越判定·跌至：已在阈值下方但未发生穿越，不触发', () => {
    const alert = { price: 90, direction: 'down', enabled: true, triggeredAt: null };
    assert.equal(alerts.evaluateAlertCrossing(alert, 88, 87), false);
    assert.equal(alerts.evaluateAlertCrossing(alert, 90, 90), false);
});

test('穿越判定·涨至：价格上穿阈值时触发', () => {
    const alert = { price: 95, direction: 'up', enabled: true, triggeredAt: null };
    assert.equal(alerts.evaluateAlertCrossing(alert, 94.5, 95.2), true);
    assert.equal(alerts.evaluateAlertCrossing(alert, 95, 95), false);
    assert.equal(alerts.evaluateAlertCrossing(alert, 96, 97), false);
});

test('穿越判定：3 秒轮询之间的跳空穿越不能漏报', () => {
    const down = { price: 90, direction: 'down', enabled: true, triggeredAt: null };
    const up = { price: 90, direction: 'up', enabled: true, triggeredAt: null };
    assert.equal(alerts.evaluateAlertCrossing(down, 92, 87), true);
    assert.equal(alerts.evaluateAlertCrossing(up, 87, 92), true);
});

test('穿越判定：已触发/已禁用/价格无效时不触发', () => {
    const base = { price: 90, direction: 'down', enabled: true, triggeredAt: null };
    assert.equal(alerts.evaluateAlertCrossing({ ...base, triggeredAt: 1 }, 91, 89), false);
    assert.equal(alerts.evaluateAlertCrossing({ ...base, enabled: false }, 91, 89), false);
    assert.equal(alerts.evaluateAlertCrossing(base, NaN, 89), false);
    assert.equal(alerts.evaluateAlertCrossing(base, 91, 0), false);
    assert.equal(alerts.evaluateAlertCrossing(null, 91, 89), false);
});

test('批量判定：一次轮询可同时命中多个预警', () => {
    const list = [
        { id: 'a', price: 90, direction: 'down', enabled: true, triggeredAt: null },
        { id: 'b', price: 92, direction: 'down', enabled: true, triggeredAt: null },
        { id: 'c', price: 85, direction: 'up', enabled: true, triggeredAt: null },
    ];
    const hit = alerts.findTriggeredAlerts(list, 95, 89);
    assert.deepEqual(hit.map((item) => item.id), ['a', 'b']);
});

test('规范化：缺方向时按参考现价推导，并补齐 id/时间戳', () => {
    const alert = alerts.normalizeAlert({ price: 87.72, symbol: '600519' }, { referencePrice: 88 });
    assert.equal(alert.direction, 'down');
    assert.equal(alert.price, 87.72);
    assert.equal(alert.enabled, true);
    assert.equal(alert.triggeredAt, null);
    assert.ok(alert.id.startsWith('alert-'));
    assert.ok(Number.isFinite(alert.createdAt));
});

test('规范化：价格无效返回 null', () => {
    assert.equal(alerts.normalizeAlert({ price: 0 }), null);
    assert.equal(alerts.normalizeAlert(null), null);
});

test('列表规范化：剔除无效项、按 id 去重、可按标的过滤', () => {
    const list = [
        { id: 'dup', price: 90, direction: 'down', symbol: '600519' },
        { id: 'dup', price: 91, direction: 'down', symbol: '600519' },
        { price: 0 },
        { id: 'other', price: 92, direction: 'down', symbol: '000858' },
        { id: 'keep', price: 93, direction: 'up', symbol: '600519' },
    ];
    const result = alerts.normalizeAlertList(list, { symbol: '600519' });
    assert.deepEqual(result.map((item) => item.id), ['dup', 'keep']);
});

test('持久化筛选：只保留仍生效且未触发的预警', () => {
    const list = [
        { id: 'active', enabled: true, triggeredAt: null },
        { id: 'fired', enabled: false, triggeredAt: 123 },
        { id: 'muted', enabled: false, triggeredAt: null },
        null,
    ];
    assert.deepEqual(alerts.selectPersistableAlerts(list).map((item) => item.id), ['active']);
});

test('文案：标签与触发时间格式化', () => {
    assert.equal(alerts.formatAlertLabel({ price: 87.72, direction: 'down' }), '价格跌至: 87.72');
    assert.equal(alerts.formatAlertLabel({ price: 98.5, direction: 'up' }), '价格涨至: 98.50');
    assert.equal(alerts.formatAlertLabel(null), '');
    assert.equal(alerts.formatAlertTriggeredAt(0), '--:--:--');
    assert.match(alerts.formatAlertTriggeredAt(Date.now()), /^\d{2}:\d{2}:\d{2}$/);
});

test('存储键：按标的隔离且带默认前缀', () => {
    assert.equal(alerts.alertStorageKey('600519'), 'kline-ashare-live-alerts-v1::600519');
    assert.equal(alerts.alertStorageKey(''), 'kline-ashare-live-alerts-v1::default');
    assert.equal(alerts.alertStorageKey('X', 'custom::'), 'custom::X');
});
