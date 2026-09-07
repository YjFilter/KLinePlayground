/**
 * KLinePlayground - Trading Hours Band Module
 * 在小于 4H 的币圈周期上，用极淡的背景色带标出用户的做单时间段
 * （如 08:00–24:00 UTC+8），让回放/做单时一眼识别"当前 K 线是否在
 * 我的做单时段"。时段跨午夜（如 22:00–06:00）同样支持。
 *
 * 纯时间投影：色带只依赖可视时间范围与固定日内规律，不依赖 K 线数据，
 * 因此数据刷新无需额外触发。绘制用可视区间两端两个锚点做线性映射，
 * 规避 timeToCoordinate 对非数据时间的空值问题。
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.KLineTradingHoursModule = factory();
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    // 4H 及以下的币圈周期才显示时段色带（更大周期日内时间失去意义）。
    const CRYPTO_INTRADAY_PERIODS = new Set(['1m', '3m', '5m', '15m', '30m', '1h', '2h', '3h', '4h']);

    const DAY_SECONDS = 86400;
    const DEFAULT_START_HOUR = 8;
    const DEFAULT_END_HOUR = 24;

    let startHour = DEFAULT_START_HOUR;
    let endHour = DEFAULT_END_HOUR;

    function isIntradayCryptoPeriod(period) {
        return CRYPTO_INTRADAY_PERIODS.has(String(period || ''));
    }

    function getTradingHours() {
        return { start: startHour, end: endHour };
    }

    function setTradingHours(nextStart, nextEnd) {
        const s = Number(nextStart);
        const e = Number(nextEnd);
        if (Number.isInteger(s) && s >= 0 && s <= 23) startHour = s;
        if (Number.isInteger(e) && e >= 1 && e <= 24) endHour = e;
        return getTradingHours();
    }

    /**
     * 计算可视时间范围内的做单时段分段（图表时间秒）。
     * 图表 X 轴以 Date.UTC 保留市场墙上时间（08:00 即 08:00:00 UTC），
     * 默认 tzOffsetMinutes 为 0 以与图表时间坐标 100% 对齐。
     * @returns {Array<[number, number]>} 有序且互不重叠的 [startSec, endSec]
     */
    function computeTradingHourSegments(fromSec, toSec, hours, tzOffsetMinutes) {
        const hoursInput = hours || getTradingHours();
        const tz = (tzOffsetMinutes === undefined ? 0 : tzOffsetMinutes) * 60;
        const from = Number(fromSec);
        const to = Number(toSec);
        if (!Number.isFinite(from) || !Number.isFinite(to) || to <= from) return [];
        const s0 = Number.isInteger(hoursInput.start) ? hoursInput.start : startHour;
        const e0 = Number.isInteger(hoursInput.end) ? hoursInput.end : endHour;
        if (s0 === e0) return [];

        const segments = [];
        // 本地墙上时间 = UTC + tzOffset（东八区 +480）。本地午夜对应的 UTC 时刻要"减"偏移。
        // 前后各多扫一天，覆盖跨午夜窗口从"前一天"开始的情况。
        const firstDay = Math.floor((from + tz) / DAY_SECONDS) - 1;
        const lastDay = Math.floor((to + tz) / DAY_SECONDS) + 1;
        for (let day = firstDay; day <= lastDay; day++) {
            const dayStartUtc = day * DAY_SECONDS - tz;
            let segStart = dayStartUtc + s0 * 3600;
            let segEnd = dayStartUtc + e0 * 3600;
            if (e0 <= s0) segEnd += DAY_SECONDS; // 跨午夜窗口（如 22:00–06:00）
            const clippedStart = Math.max(segStart, from);
            const clippedEnd = Math.min(segEnd, to);
            if (clippedEnd > clippedStart) segments.push([clippedStart, clippedEnd]);
        }
        return segments;
    }

    function ensureTradingHoursCanvas(container) {
        let canvas = container.querySelector('.trading-hours-overlay');
        if (!canvas) {
            canvas = document.createElement('canvas');
            canvas.className = 'trading-hours-overlay';
            container.appendChild(canvas);
        }
        return canvas;
    }

    function clearTradingHoursBands(container) {
        const canvas = container && container.querySelector('.trading-hours-overlay');
        if (canvas) {
            const context = canvas.getContext('2d');
            context.clearRect(0, 0, canvas.width, canvas.height);
        }
    }

    /**
     * 绘制时段色带。时段不在作用内时由调用方负责清屏（clearTradingHoursBands）。
     * @param {object} opts { chart, container, color, tzOffsetMinutes }
     */
    function drawTradingHoursBands(opts) {
        const { chart, container, color, tzOffsetMinutes } = opts || {};
        if (!chart || !container) return;
        const timeScale = chart.timeScale();
        const visibleRange = timeScale.getVisibleRange?.();
        if (!visibleRange) {
            clearTradingHoursBands(container);
            return;
        }
        const from = Number(visibleRange.from);
        const to = Number(visibleRange.to);
        const anchorFrom = timeScale.timeToCoordinate?.(visibleRange.from);
        const anchorTo = timeScale.timeToCoordinate?.(visibleRange.to);
        if (!Number.isFinite(from) || !Number.isFinite(to) || to <= from) return;
        if (!Number.isFinite(anchorFrom) || !Number.isFinite(anchorTo) || anchorFrom === anchorTo) {
            clearTradingHoursBands(container);
            return;
        }

        const canvas = ensureTradingHoursCanvas(container);
        const dpr = (typeof window !== 'undefined' && window.devicePixelRatio) || 1;
        const width = container.clientWidth;
        const height = container.clientHeight;
        if (width <= 0 || height <= 0) return;
        if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
            canvas.width = Math.round(width * dpr);
            canvas.height = Math.round(height * dpr);
            canvas.style.width = `${width}px`;
            canvas.style.height = `${height}px`;
        }
        const context = canvas.getContext('2d');
        context.setTransform(dpr, 0, 0, dpr, 0, 0);
        context.clearRect(0, 0, width, height);

        const pxPerSecond = (anchorTo - anchorFrom) / (to - from);
        const xForTime = (time) => anchorFrom + (time - from) * pxPerSecond;
        const rightPad = Number(opts.rightPad) || 0;

        context.fillStyle = color || 'rgba(127, 127, 127, 0.05)';
        for (const [segStart, segEnd] of computeTradingHourSegments(from, to, opts.hours, tzOffsetMinutes)) {
            const xStart = Math.max(0, xForTime(segStart));
            const xEnd = Math.min(width - rightPad, xForTime(segEnd));
            if (xEnd - xStart >= 0.5) {
                context.fillRect(xStart, 0, xEnd - xStart, height);
            }
        }
    }

    return {
        CRYPTO_INTRADAY_PERIODS,
        DEFAULT_START_HOUR,
        DEFAULT_END_HOUR,
        isIntradayCryptoPeriod,
        getTradingHours,
        setTradingHours,
        computeTradingHourSegments,
        ensureTradingHoursCanvas,
        clearTradingHoursBands,
        drawTradingHoursBands
    };
}));
