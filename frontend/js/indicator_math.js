(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root) root.KLineIndicatorMath = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function positiveInteger(value, fallback) {
        const parsed = Number.parseInt(value, 10);
        return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
    }

    function finiteNumber(value, fallback) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function normalizeBars(bars) {
        if (!Array.isArray(bars)) return [];
        return bars.map((bar) => ({
            time: bar.time,
            open: Number(bar.open),
            high: Number(bar.high),
            low: Number(bar.low),
            close: Number(bar.close),
        })).filter((bar) => bar.time !== undefined
            && Number.isFinite(bar.open)
            && Number.isFinite(bar.high)
            && Number.isFinite(bar.low)
            && Number.isFinite(bar.close));
    }

    function ema(values, period) {
        if (values.length === 0) return [];
        const smoothing = 2 / (period + 1);
        const output = [values[0]];
        for (let index = 1; index < values.length; index += 1) {
            output.push(values[index] * smoothing + output[index - 1] * (1 - smoothing));
        }
        return output;
    }

    function calculateMacd(bars, config) {
        const fast = positiveInteger(config.fast, 12);
        const slow = Math.max(positiveInteger(config.slow, 26), fast + 1);
        const signal = positiveInteger(config.signal, 9);
        const closes = bars.map((bar) => bar.close);
        const fastValues = ema(closes, fast);
        const slowValues = ema(closes, slow);
        const difValues = closes.map((_, index) => fastValues[index] - slowValues[index]);
        const deaValues = ema(difValues, signal);
        return {
            type: 'MACD',
            data: bars.map((bar, index) => ({
                time: bar.time,
                dif: difValues[index],
                dea: deaValues[index],
                histogram: (difValues[index] - deaValues[index]) * 2,
            })),
        };
    }

    function calculateKdj(bars, config) {
        const period = positiveInteger(config.n, 9);
        const kSmoothing = positiveInteger(config.m1, 3);
        const dSmoothing = positiveInteger(config.m2, 3);
        let previousK = 50;
        let previousD = 50;
        const data = bars.map((bar, index) => {
            const start = Math.max(0, index - period + 1);
            const windowBars = bars.slice(start, index + 1);
            const highest = Math.max(...windowBars.map((item) => item.high));
            const lowest = Math.min(...windowBars.map((item) => item.low));
            const rsv = highest === lowest ? 50 : ((bar.close - lowest) / (highest - lowest)) * 100;
            const k = ((kSmoothing - 1) * previousK + rsv) / kSmoothing;
            const d = ((dSmoothing - 1) * previousD + k) / dSmoothing;
            const j = 3 * k - 2 * d;
            previousK = k;
            previousD = d;
            return { time: bar.time, k, d, j };
        });
        return { type: 'KDJ', data };
    }

    function calculateRsi(bars, config) {
        const requested = Array.isArray(config.periods) ? config.periods : [6, 12, 24];
        const periods = requested.map((period) => positiveInteger(period, 0)).filter((period) => period > 0);
        const uniquePeriods = [...new Set(periods.length ? periods : [6, 12, 24])];
        const maxPeriod = Math.max(...uniquePeriods);
        const gains = [];
        const losses = [];
        for (let index = 1; index < bars.length; index += 1) {
            const change = bars[index].close - bars[index - 1].close;
            gains.push(Math.max(change, 0));
            losses.push(Math.max(-change, 0));
        }
        const data = [];
        for (let index = maxPeriod; index < bars.length; index += 1) {
            const point = { time: bars[index].time };
            uniquePeriods.forEach((period) => {
                const start = index - period;
                const gainSum = gains.slice(start, index).reduce((sum, value) => sum + value, 0);
                const lossSum = losses.slice(start, index).reduce((sum, value) => sum + value, 0);
                point[`rsi${period}`] = gainSum + lossSum === 0 ? 50 : (gainSum / (gainSum + lossSum)) * 100;
            });
            data.push(point);
        }
        return { type: 'RSI', periods: uniquePeriods, data };
    }

    function calculateBoll(bars, config) {
        const period = positiveInteger(config.period, 20);
        const stdDevMultiplier = finiteNumber(config.stdDev, finiteNumber(config.std_dev, 2));
        const data = [];
        for (let index = period - 1; index < bars.length; index += 1) {
            const windowBars = bars.slice(index - period + 1, index + 1);
            const closes = windowBars.map((bar) => bar.close);
            const middle = closes.reduce((sum, value) => sum + value, 0) / period;
            const variance = closes.reduce((sum, value) => sum + ((value - middle) ** 2), 0) / period;
            const deviation = Math.sqrt(variance) * stdDevMultiplier;
            data.push({
                time: bars[index].time,
                upper: middle + deviation,
                middle,
                lower: middle - deviation,
            });
        }
        return { type: 'BOLL', data };
    }

    function calculate(type, inputBars, config) {
        const bars = normalizeBars(inputBars);
        const normalizedType = String(type || 'MACD').toUpperCase();
        const safeConfig = config || {};
        if (bars.length === 0) return { type: normalizedType, data: [] };
        if (normalizedType === 'MACD') return calculateMacd(bars, safeConfig);
        if (normalizedType === 'KDJ') return calculateKdj(bars, safeConfig);
        if (normalizedType === 'RSI') return calculateRsi(bars, safeConfig);
        if (normalizedType === 'BOLL') return calculateBoll(bars, safeConfig);
        throw new Error(`不支持的技术指标: ${normalizedType}`);
    }

    return { calculate };
}));
