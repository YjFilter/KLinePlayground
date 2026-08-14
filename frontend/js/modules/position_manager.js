/**
 * KLinePlayground - 账户资产、持仓卡片、强平爆仓与历史交易记录管理模块
 */

function formatCryptoPnL(value, decimals = 2) {
    const num = Number(value) || 0;
    const sign = num > 0 ? '+' : '';
    const formatted = typeof formatCryptoValue === 'function' ? formatCryptoValue(num, decimals) : num.toFixed(decimals);
    return `${sign}${formatted}`;
}

function escapeHtml(text) {
    if (text == null) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;',
    };
    return String(text).replace(/[&<>"']/g, (m) => map[m]);
}
