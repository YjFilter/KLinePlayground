/**
 * KLinePlayground - Position Manager Module
 * Computes position unrealized PnL, margin ratio, liquidation risks, and formats position metrics.
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.KLinePositionModule = factory();
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function computeUnrealizedPnl(side, quantity, entryPrice, markPrice) {
        const qty = Number(quantity) || 0;
        const entry = Number(entryPrice) || 0;
        const mark = Number(markPrice) || 0;
        if (qty <= 0 || entry <= 0 || mark <= 0) return 0;
        if (side === 'long') {
            return (mark - entry) * qty;
        } else if (side === 'short') {
            return (entry - mark) * qty;
        }
        return 0;
    }

    function computePnlPercentage(unrealizedPnl, margin) {
        const pnl = Number(unrealizedPnl) || 0;
        const m = Number(margin) || 0;
        if (m <= 0) return null;
        return (pnl / m) * 100;
    }

    return {
        computeUnrealizedPnl,
        computePnlPercentage
    };
}));
