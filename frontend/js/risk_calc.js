(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root) root.RiskCalc = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function toPositiveNumber(value) {
        const num = Number(value);
        return Number.isFinite(num) && num > 0 ? num : 0;
    }

    /**
     * 以损定仓：根据开仓价、止损价、最大亏损额反推开仓数量。
     * quantity = maxLoss / |entry - stop|（杠杆不影响数量，只影响所需保证金）
     * margin = quantity * entry / leverage
     * @param {object} params { entryPrice, stopPrice, maxLoss, leverage, action }
     * @returns {object} { valid, reason, quantity, notional, margin, stopRate, marginLossRate, directionOk, ... }
     */
    function computeRiskPosition(params) {
        const source = params || {};
        const entry = toPositiveNumber(source.entryPrice);
        const stop = toPositiveNumber(source.stopPrice);
        const maxLoss = toPositiveNumber(source.maxLoss);
        const leverage = Math.min(100, Math.max(1, Math.floor(toPositiveNumber(source.leverage) || 1)));
        const action = source.action === 'open_short' ? 'open_short' : 'open_long';
        const base = {
            valid: false,
            reason: '',
            action,
            directionOk: true,
            leverage,
            entryPrice: entry,
            stopPrice: stop,
            maxLoss,
            quantity: 0,
            notional: 0,
            margin: 0,
            stopRate: 0,
            marginLossRate: 0,
        };
        if (!entry || !stop || !maxLoss) {
            base.reason = 'missing-inputs';
            return base;
        }
        const distance = Math.abs(entry - stop);
        if (!Number.isFinite(distance) || distance <= 0) {
            base.reason = 'stop-too-close';
            return base;
        }
        const quantity = maxLoss / distance;
        const notional = quantity * entry;
        const stopRate = distance / entry;
        base.valid = true;
        base.quantity = quantity;
        base.notional = notional;
        base.margin = notional / leverage;
        base.stopRate = stopRate;
        base.marginLossRate = stopRate * leverage;
        base.directionOk = action === 'open_short' ? stop > entry : stop < entry;
        return base;
    }

    return { computeRiskPosition };
}));
