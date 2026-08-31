/**
 * KLinePlayground - Crypto Order Console Module
 * Handles order direction, order types (market/limit/breakout), leverage, fraction grids, and margin previews.
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.KLineCryptoOrderModule = factory();
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function calculateOrderPreview({ markPrice, margin, leverage, action, orderType, targetPrice }) {
        const price = (orderType === 'limit' || orderType === 'breakout') && Number(targetPrice) > 0 ? Number(targetPrice) : Number(markPrice);
        const lev = Math.max(1, Number(leverage) || 1);
        const marg = Math.max(0, Number(margin) || 0);
        if (!price || price <= 0 || marg <= 0) {
            return { quantity: 0, nominal: 0, requiredMargin: marg };
        }
        const nominal = marg * lev;
        const quantity = nominal / price;
        return {
            quantity,
            nominal,
            requiredMargin: marg
        };
    }

    function calculateFractionMargin(availableBalance, fraction) {
        const bal = Math.max(0, Number(availableBalance) || 0);
        const frac = Math.min(1, Math.max(0, Number(fraction) || 0));
        return Number((bal * frac).toFixed(2));
    }

    return {
        calculateOrderPreview,
        calculateFractionMargin
    };
}));
