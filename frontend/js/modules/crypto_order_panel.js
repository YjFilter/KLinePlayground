/**
 * KLinePlayground - 币圈合约下单控制台、杠杆与仓位风险计算模块
 */

function selectCryptoOrderAction(action) {
    const valid = ['open_long', 'open_short', 'close'].includes(action) ? action : 'open_long';
    const select = document.getElementById('crypto-order-action');
    if (select) select.value = valid;
    document.querySelectorAll('[data-crypto-action]').forEach((button) => {
        const active = button.dataset.cryptoAction === valid;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
    });
    const submitBtn = document.getElementById('crypto-submit-order-btn');
    if (submitBtn) {
        submitBtn.textContent = valid === 'close' ? '提交平仓订单' : valid === 'open_short' ? '提交开空订单' : '提交开多订单';
        submitBtn.className = 'btn-crypto-submit ' + valid;
    }
    const tpslSection = document.querySelector('.crypto-tpsl-section');
    if (tpslSection) {
        tpslSection.classList.toggle('hidden', valid === 'close');
    }
    if (typeof refreshCryptoMarginFraction === 'function') refreshCryptoMarginFraction();
    if (typeof refreshCryptoOrderPreview === 'function') refreshCryptoOrderPreview();
    if (typeof refreshCryptoTpSlPnl === 'function') refreshCryptoTpSlPnl();
}

function setCryptoOrderStatus(message, type = 'ready') {
    const statusEl = document.getElementById('crypto-order-status');
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.className = 'crypto-order-status ' + type;
}

function calculateRiskPositionSize(riskAmount, entryPrice, stopLossPrice, leverage = 1, minQty = 0.001, step = 0.001) {
    if (!riskAmount || !entryPrice || !stopLossPrice || entryPrice <= 0 || stopLossPrice <= 0) return null;
    const priceDiff = Math.abs(entryPrice - stopLossPrice);
    if (priceDiff <= 0) return null;
    const rawQty = riskAmount / priceDiff;
    const steppedQty = Math.floor(rawQty / step) * step;
    const finalQty = Math.max(minQty, Number(steppedQty.toFixed(4)));
    const requiredMargin = (finalQty * entryPrice) / leverage;
    return {
        quantity: finalQty,
        requiredMargin: Number(requiredMargin.toFixed(2)),
        actualRisk: Number((finalQty * priceDiff).toFixed(2)),
    };
}
