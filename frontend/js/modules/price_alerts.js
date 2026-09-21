/**
 * KLinePlayground - Price Alerts Module (AICoin style)
 * Pure logic for A-share live-watch price alerts: normalization, direction
 * derivation, crossing evaluation and persistence selection.
 * Chart/DOM wiring stays in main_enhanced.js (this module must stay pure so it
 * can run under `node --test`).
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.KLinePriceAlertsModule = factory();
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    const ALERT_DIRECTION_UP = 'up';
    const ALERT_DIRECTION_DOWN = 'down';
    const ALERT_STORAGE_PREFIX = 'kline-ashare-live-alerts-v1::';
    const ALERT_DIRECTION_LABELS = { up: '价格涨至', down: '价格跌至' };
    // A股最小变动单位 0.01 元，价格一律按此归一，避免浮点噪声影响穿越判定
    const ALERT_PRICE_SCALE = 100;

    function normalizeAlertPrice(value) {
        const price = Number(value);
        if (!Number.isFinite(price) || price <= 0) return null;
        return Math.round(price * ALERT_PRICE_SCALE) / ALERT_PRICE_SCALE;
    }

    function normalizeAlertDirection(value) {
        const raw = String(value === undefined || value === null ? '' : value).trim().toLowerCase();
        if (raw === 'up' || raw === 'rise' || raw === 'above') return ALERT_DIRECTION_UP;
        if (raw === 'down' || raw === 'fall' || raw === 'below') return ALERT_DIRECTION_DOWN;
        return null;
    }

    function buildAlertId(seed) {
        const numeric = Number(seed);
        const base = Number.isFinite(numeric) && numeric > 0 ? numeric : Date.now();
        return 'alert-' + base.toString(36) + '-' + Math.random().toString(36).slice(2, 8);
    }

    /**
     * 按参考现价推导方向：高于现价 = 涨至，否则 = 跌至。
     * 价格与现价相等时归为"跌至"（回踩确认），避免创建瞬间就报"涨至"。
     */
    function deriveAlertDirection(price, referencePrice) {
        const alertPrice = normalizeAlertPrice(price);
        const reference = Number(referencePrice);
        if (alertPrice === null || !Number.isFinite(reference) || reference <= 0) {
            return ALERT_DIRECTION_DOWN;
        }
        return alertPrice > reference ? ALERT_DIRECTION_UP : ALERT_DIRECTION_DOWN;
    }

    function normalizeAlert(candidate, options) {
        const opts = options || {};
        if (!candidate || typeof candidate !== 'object') return null;
        const price = normalizeAlertPrice(candidate.price);
        if (price === null) return null;
        const direction = normalizeAlertDirection(candidate.direction)
            || deriveAlertDirection(price, opts.referencePrice);
        const createdAt = Number(candidate.createdAt);
        const triggeredAt = Number(candidate.triggeredAt);
        const symbol = String(candidate.symbol || opts.symbol || '').trim();
        return {
            id: typeof candidate.id === 'string' && candidate.id ? candidate.id : buildAlertId(createdAt),
            symbol: symbol,
            price: price,
            direction: direction,
            enabled: candidate.enabled === undefined ? true : Boolean(candidate.enabled),
            createdAt: Number.isFinite(createdAt) && createdAt > 0 ? createdAt : Date.now(),
            triggeredAt: Number.isFinite(triggeredAt) && triggeredAt > 0 ? triggeredAt : null,
        };
    }

    function normalizeAlertList(list, options) {
        if (!Array.isArray(list)) return [];
        const opts = options || {};
        const seen = new Set();
        const result = [];
        list.forEach(function (item) {
            const alert = normalizeAlert(item, opts);
            if (!alert) return;
            if (opts.symbol && alert.symbol && alert.symbol !== opts.symbol) return;
            if (seen.has(alert.id)) return;
            seen.add(alert.id);
            result.push(alert);
        });
        return result;
    }

    /**
     * 只在价格"穿越"阈值时触发：涨至 = 上穿（prev < target <= now），
     * 跌至 = 下穿（prev > target >= now）。
     * 用上一价做严格比较，既避免价格停在阈值上反复触发，也保证 3 秒轮询
     * 之间的跳空不会漏报（跳空时 prev/now 跨过阈值，条件依然成立）。
     */
    function evaluateAlertCrossing(alert, previousPrice, currentPrice) {
        if (!alert || alert.enabled === false || alert.triggeredAt) return false;
        const target = Number(alert.price);
        const previous = Number(previousPrice);
        const current = Number(currentPrice);
        if (!Number.isFinite(target) || target <= 0) return false;
        if (!Number.isFinite(previous) || previous <= 0) return false;
        if (!Number.isFinite(current) || current <= 0) return false;
        if (alert.direction === ALERT_DIRECTION_UP) return previous < target && current >= target;
        return previous > target && current <= target;
    }

    function findTriggeredAlerts(alerts, previousPrice, currentPrice) {
        if (!Array.isArray(alerts)) return [];
        return alerts.filter(function (alert) {
            return evaluateAlertCrossing(alert, previousPrice, currentPrice);
        });
    }

    function formatAlertPrice(price) {
        const normalized = normalizeAlertPrice(price);
        if (normalized === null) return '--';
        return normalized.toFixed(2);
    }

    function formatAlertLabel(alert) {
        if (!alert) return '';
        const prefix = ALERT_DIRECTION_LABELS[alert.direction] || ALERT_DIRECTION_LABELS[ALERT_DIRECTION_DOWN];
        return prefix + ': ' + formatAlertPrice(alert.price);
    }

    function formatAlertTriggeredAt(timestamp) {
        const value = Number(timestamp);
        if (!Number.isFinite(value) || value <= 0) return '--:--:--';
        const date = new Date(value);
        const pad = function (n) { return String(n).padStart(2, '0'); };
        return pad(date.getHours()) + ':' + pad(date.getMinutes()) + ':' + pad(date.getSeconds());
    }

    function alertStorageKey(symbol, prefix) {
        const base = typeof prefix === 'string' && prefix ? prefix : ALERT_STORAGE_PREFIX;
        return base + String(symbol || 'default');
    }

    /** 只持久化"仍生效且未触发"的预警；已触发的留在当前会话作留痕，刷新后自然清掉。 */
    function selectPersistableAlerts(alerts) {
        if (!Array.isArray(alerts)) return [];
        return alerts.filter(function (alert) {
            return Boolean(alert) && alert.enabled !== false && !alert.triggeredAt;
        });
    }

    return {
        ALERT_DIRECTION_UP: ALERT_DIRECTION_UP,
        ALERT_DIRECTION_DOWN: ALERT_DIRECTION_DOWN,
        ALERT_STORAGE_PREFIX: ALERT_STORAGE_PREFIX,
        ALERT_DIRECTION_LABELS: ALERT_DIRECTION_LABELS,
        normalizeAlertPrice: normalizeAlertPrice,
        normalizeAlertDirection: normalizeAlertDirection,
        buildAlertId: buildAlertId,
        deriveAlertDirection: deriveAlertDirection,
        normalizeAlert: normalizeAlert,
        normalizeAlertList: normalizeAlertList,
        evaluateAlertCrossing: evaluateAlertCrossing,
        findTriggeredAlerts: findTriggeredAlerts,
        formatAlertPrice: formatAlertPrice,
        formatAlertLabel: formatAlertLabel,
        formatAlertTriggeredAt: formatAlertTriggeredAt,
        alertStorageKey: alertStorageKey,
        selectPersistableAlerts: selectPersistableAlerts,
    };
}));
