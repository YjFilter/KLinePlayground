/**
 * KLinePlayground - Chart Window Core Module
 * Pure (DOM-free) helpers for chart window state, K-line/volume/marker
 * normalization, timed-item merging, and replay period badge formatting.
 * Extracted from main_enhanced.js; consumed there via
 * `window.KLineChartWindowCore` and unit-testable via require().
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.KLineChartWindowCore = factory();
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
'use strict';


function createEmptyChartWindowState() {
    return {
        kline_data: [],
        volume_data: [],
        trade_markers: [],
        window_start: null,
        window_end: null,
        history_start: null,
        history_end: null,
        render_start: null,
        render_end: null,
        has_earlier_render: false,
        training_start: null,
        training_end: null,
        has_earlier: false,
        has_later: false,
        extended_history: false,
        read_only: false,
        period: 'daily',
    };
}
// 将周期值转换为可读的徽章文字。
function formatIntradayPeriodBadge(period) {
    switch (period) {
        case '1m': return '1m';
        case '3m': return '3m';
        case '5m': return '5m';
        case '15m': return '15m';
        case '30m': return '30m';
        case '1h': return '1h';
        case '2h': return '2h';
        case '3h': return '3h';
        case '4h': return '4h';
        case '6h': return '6h';
        case '8h': return '8h';
        case '12h': return '12h';
        case '4h_session': return '4h';
        case 'weekly': return '1W';
        case '1d': return '1D';
        case '2d': return '2D';
        case '3d': return '3D';
        case 'daily':
        default: return '1D';
    }
}
// start / data / period 返回顶层 snapshot；next / reset 把 snapshot 嵌在 response.snapshot。
// 此函数统一提取 snapshot 对象。
function extractIntradaySnapshot(response) {
    if (!response || typeof response !== 'object') return null;
    if (response.snapshot && typeof response.snapshot === 'object') {
        return response.snapshot;
    }
    return response;
}
// lightweight-charts 使用 UTC 字段绘制标签，因此这里用 Date.UTC 保留 10:00 等原始盘中时间，
// 不把北京时间换算成 02:00 UTC。
function intradayBarToTimestamp(bar) {
    if (!bar) return 0;
    const raw = bar.start_time || bar.end_time || bar.time || bar.datetime;
    if (typeof raw === 'number') return raw;
    if (!raw) return 0;
    const match = String(raw).match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
    if (!match) return 0;
    return Math.floor(Date.UTC(
        Number(match[1]),
        Number(match[2]) - 1,
        Number(match[3]),
        Number(match[4] || 0),
        Number(match[5] || 0),
        Number(match[6] || 0)
    ) / 1000);
}
// 把 intraday snapshot.kline_data 转成 lightweight-charts 所需的蜡烛数据格式。
function buildIntradayKlineChartData(klineData) {
    if (!Array.isArray(klineData)) return [];
    return klineData.map(function (bar) {
        return {
            time: intradayBarToTimestamp(bar),
            open: Number(bar.open),
            high: Number(bar.high),
            low: Number(bar.low),
            close: Number(bar.close),
            volume: Number(bar.volume) || 0,
        };
    });
}
function normalizeChartTime(item) {
    if (!item) return 0;
    if (typeof item.time === 'number') return item.time;
    const rawTime = item.time || item.timestamp || item.end_time || item.start_time || item.datetime;
    return intradayBarToTimestamp({ time: rawTime });
}
function normalizeChartCandle(item) {
    return {
        time: normalizeChartTime(item),
        open: Number(item.open),
        high: Number(item.high),
        low: Number(item.low),
        close: Number(item.close),
        volume: Number(item.volume) || 0,
    };
}
function normalizeChartVolume(item) {
    return {
        time: normalizeChartTime(item),
        value: Number(item.value ?? item.volume) || 0,
        color: item.color || '#999999',
    };
}
function normalizeChartMarker(marker) {
    return {
        ...marker,
        time: normalizeChartTime(marker),
    };
}
function mergeTimedItems(existingItems, incomingItems, normalizer) {
    const merged = new Map();
    [...(existingItems || []), ...(incomingItems || [])].forEach((item) => {
        const normalized = normalizer(item);
        if (normalized.time) merged.set(normalized.time, normalized);
    });
    return Array.from(merged.values()).sort((left, right) => left.time - right.time);
}
function normalizeTradeMarkers(markers) {
    return (markers || [])
        .map(normalizeChartMarker)
        .filter((marker) => marker.time)
        .sort((left, right) => left.time - right.time);
}
function mergeChartWindow(existing, incoming) {
    const base = existing || createEmptyChartWindowState();
    const next = incoming || {};
    const normalizeCandle = (item) => ({ ...normalizeChartCandle(item), time: normalizeChartTime(item) });
    const normalizeVolume = (item) => ({ ...normalizeChartVolume(item), time: normalizeChartTime(item) });
    return {
        ...base,
        ...next,
        kline_data: mergeTimedItems(base.kline_data, next.kline_data, normalizeCandle),
        volume_data: mergeTimedItems(base.volume_data, next.volume_data, normalizeVolume),
        trade_markers: next.trade_markers !== undefined
            ? normalizeTradeMarkers(next.trade_markers)
            : normalizeTradeMarkers(base.trade_markers),
    };
}
function parseChartWindowTimestamp(value) {
    if (value instanceof Date) {
        return Number.isFinite(value.getTime()) ? new Date(value.getTime()) : null;
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
        return new Date(value < 1e12 ? value * 1000 : value);
    }
    if (!value) return null;
    const numericValue = Number(value);
    if (/^\d+(?:\.\d+)?$/.test(String(value)) && Number.isFinite(numericValue)) {
        return new Date(numericValue < 1e12 ? numericValue * 1000 : numericValue);
    }
    const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
    if (!match) return null;
    return new Date(Date.UTC(
        Number(match[1]), Number(match[2]) - 1, Number(match[3]),
        Number(match[4] || 0), Number(match[5] || 0), Number(match[6] || 0)
    ));
}
function formatChartWindowTimestamp(date) {
    const pad = (value) => String(value).padStart(2, '0');
    return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}`;
}
function shiftChartWindowYear(value, yearDelta) {
    const date = parseChartWindowTimestamp(value);
    if (!date) return value;
    const originalMonth = date.getUTCMonth();
    date.setUTCFullYear(date.getUTCFullYear() + yearDelta);
    if (date.getUTCMonth() !== originalMonth) date.setUTCDate(0);
    return formatChartWindowTimestamp(date);
}
function earlierChartWindowTimestamp(left, right) {
    if (!left) return right || null;
    if (!right) return left;
    return parseChartWindowTimestamp(left) <= parseChartWindowTimestamp(right) ? left : right;
}
function laterChartWindowTimestamp(left, right) {
    if (!left) return right || null;
    if (!right) return left;
    return parseChartWindowTimestamp(left) >= parseChartWindowTimestamp(right) ? left : right;
}



    return {
        createEmptyChartWindowState,
        formatIntradayPeriodBadge,
        extractIntradaySnapshot,
        intradayBarToTimestamp,
        buildIntradayKlineChartData,
        normalizeChartTime,
        normalizeChartCandle,
        normalizeChartVolume,
        normalizeChartMarker,
        mergeTimedItems,
        normalizeTradeMarkers,
        mergeChartWindow,
        parseChartWindowTimestamp,
        formatChartWindowTimestamp,
        shiftChartWindowYear,
        earlierChartWindowTimestamp,
        laterChartWindowTimestamp
    };
}));
