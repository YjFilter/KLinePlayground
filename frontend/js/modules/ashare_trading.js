/**
 * KLinePlayground - A-Share Live Paper Trading Module
 * Pure calculation functions for A-share spot trading, T+1 rules, weighted average cost, and PnL.
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.KLineAshareTradingModule = factory();
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    /**
     * 计算浮动盈亏金额
     */
    function computeAshareFloatingPnl(avgCost, currentPrice, totalShares) {
        const cost = Number(avgCost) || 0;
        const price = Number(currentPrice) || 0;
        const shares = Number(totalShares) || 0;
        if (cost <= 0 || price <= 0 || shares <= 0) return 0;
        return (price - cost) * shares;
    }

    /**
     * 计算浮动盈亏率 (%)
     */
    function computeAsharePnlRate(avgCost, currentPrice) {
        const cost = Number(avgCost) || 0;
        const price = Number(currentPrice) || 0;
        if (cost <= 0 || price <= 0) return 0;
        return ((price - cost) / cost) * 100;
    }

    /**
     * 计算加权买入成本均价
     */
    function computeWeightedAvgCost(oldShares, oldAvgCost, newShares, newPrice) {
        const oShares = Math.max(0, Number(oldShares) || 0);
        const oCost = Math.max(0, Number(oldAvgCost) || 0);
        const nShares = Math.max(0, Number(newShares) || 0);
        const nPrice = Math.max(0, Number(newPrice) || 0);
        const totalShares = oShares + nShares;
        if (totalShares <= 0) return 0;
        const totalCapital = (oShares * oCost) + (nShares * nPrice);
        return totalCapital / totalShares;
    }

    /**
     * 计算最大可买手数 (1手=100股)
     */
    function calculateMaxBuyLots(availableCash, currentPrice) {
        const cash = Math.max(0, Number(availableCash) || 0);
        const price = Math.max(0, Number(currentPrice) || 0);
        if (price <= 0 || cash <= 0) return 0;
        return Math.floor(cash / (price * 100));
    }

    /**
     * 计算最大可卖手数 (1手=100股)
     */
    function calculateMaxSellLots(availableShares) {
        const avail = Math.max(0, Number(availableShares) || 0);
        return Math.floor(avail / 100);
    }

    /**
     * 按快捷比例计算手数 (向下取整到整数手)
     */
    function calculateAshareFractionLots(maxLots, fraction) {
        const max = Math.max(0, Math.floor(Number(maxLots) || 0));
        const frac = Number(fraction) || 1;
        if (max <= 0) return 0;
        if (frac >= 1) return max;
        return Math.floor(max * frac);
    }

    /**
     * 校验买入合法性
     */
    function validateAshareBuy(lots, cash, currentPrice) {
        const l = parseInt(lots, 10);
        if (isNaN(l) || l <= 0) {
            return { valid: false, error: '买入最小单位为 1 手（100 股），请输入有效整数手！' };
        }
        const price = Number(currentPrice) || 0;
        if (price <= 0) {
            return { valid: false, error: '未获取到当前有效标的价格！' };
        }
        const shares = l * 100;
        const cost = shares * price;
        const availCash = Number(cash) || 0;
        if (availCash < cost) {
            return {
                valid: false,
                error: `可用资金不足！买入 ${l} 手 (${shares} 股) 需要 ¥${cost.toFixed(2)}，当前仅有 ¥${availCash.toFixed(2)}。`
            };
        }
        return { valid: true, lots: l, shares, cost };
    }

    /**
     * 校验卖出合法性 (严格校验 T+1 可卖持仓)
     */
    function validateAshareSell(lots, totalShares, frozenToday, currentPrice) {
        const l = parseInt(lots, 10);
        if (isNaN(l) || l <= 0) {
            return { valid: false, error: '卖出最小单位为 1 手（100 股），请输入有效手数！' };
        }
        const price = Number(currentPrice) || 0;
        if (price <= 0) {
            return { valid: false, error: '未获取到当前有效标的价格！' };
        }
        const total = Math.max(0, Number(totalShares) || 0);
        const frozen = Math.max(0, Number(frozenToday) || 0);
        const avail = Math.max(0, total - frozen);
        const sharesToSell = l * 100;

        if (sharesToSell > avail) {
            return {
                valid: false,
                error: `【T+1 卖出限制】可用持仓不足！当前总持仓 ${total} 股，今日买入冻结 ${frozen} 股 (T+1 不可卖)，当前可卖持仓仅有 ${avail} 股 (${Math.floor(avail / 100)} 手)。`
            };
        }

        const revenue = sharesToSell * price;
        return { valid: true, lots: l, shares: sharesToSell, revenue };
    }

    /**
     * T+1 跨日自动解冻逻辑
     */
    function autoUnfreezeT1Holdings(positions, lastDate, currentDate) {
        if (!positions || typeof positions !== 'object') return { thawed: false, count: 0 };
        if (!lastDate || lastDate === currentDate) return { thawed: false, count: 0 };

        let thawedCount = 0;
        for (const sym in positions) {
            const pos = positions[sym];
            if (pos && pos.frozen_today > 0) {
                thawedCount += pos.frozen_today;
                pos.frozen_today = 0;
            }
        }
        return { thawed: thawedCount > 0, count: thawedCount };
    }

    /**
     * 获取股票市场徽章类型与文本 (沪/深/创/科/北/指)
     */
    function getAshareMarketTag(code, isIndex) {
        if (isIndex) return { text: '指', cls: 'idx' };
        const c = String(code || '').replace(/^(sh|sz|bj)/i, '');
        if (c.startsWith('688')) return { text: '科', cls: 'kcb' };
        if (c.startsWith('6')) return { text: '沪', cls: 'sh' };
        if (c.startsWith('30')) return { text: '创', cls: 'cyb' };
        if (c.startsWith('00')) return { text: '深', cls: 'sz' };
        if (c.startsWith('8') || c.startsWith('4') || c.startsWith('92')) return { text: '北', cls: 'sz' };
        return { text: 'A', cls: 'sh' };
    }

    /**
     * 规范化自选股代码
     */
    function normalizeAshareWatchlistCode(code) {
        return String(code || '').replace(/^(sh|sz|bj)/i, '').trim();
    }

    /**
     * 自选股列表排序
     */
    function sortWatchlistStocks(stocks, quotes, sortField, sortOrder) {
        if (!Array.isArray(stocks) || !sortField) return stocks ? [...stocks] : [];
        const qMap = quotes || {};
        return [...stocks].sort((a, b) => {
            const qA = qMap[a.code] || qMap[a.symbol] || {};
            const qB = qMap[b.code] || qMap[b.symbol] || {};
            let valA = 0;
            let valB = 0;
            if (sortField === 'price') {
                valA = Number(qA.price) || 0;
                valB = Number(qB.price) || 0;
            } else if (sortField === 'change') {
                valA = Number(qA.change_percent) || 0;
                valB = Number(qB.change_percent) || 0;
            }
            if (sortOrder === 'asc') return valA - valB;
            return valB - valA;
        });
    }

    /**
     * 归一化 A 股实时模拟账户：补齐限价挂单相关默认字段（向后兼容旧 localStorage 数据）。
     * cash 语义 = 立即可用资金；cash_frozen = 买入挂单冻结；positions[code].frozen_sell = 卖出挂单冻结。
     */
    function normalizeAshareAccount(raw) {
        const acc = (raw && typeof raw === 'object') ? raw : {};
        if (!Number.isFinite(acc.cash)) acc.cash = 100000;
        if (!Number.isFinite(acc.cash_frozen)) acc.cash_frozen = 0;
        if (!acc.positions || typeof acc.positions !== 'object') acc.positions = {};
        if (!Array.isArray(acc.pending_orders)) acc.pending_orders = [];
        if (!acc.last_prices || typeof acc.last_prices !== 'object') acc.last_prices = {};
        if (!Array.isArray(acc.trade_history)) acc.trade_history = [];
        Object.keys(acc.positions).forEach((code) => {
            const pos = acc.positions[code] || {};
            pos.total_shares = Number(pos.total_shares) || 0;
            pos.frozen_today = Number(pos.frozen_today) || 0;
            pos.frozen_sell = Number(pos.frozen_sell) || 0;
            pos.avg_cost = Number(pos.avg_cost) || 0;
            acc.positions[code] = pos;
        });
        return acc;
    }

    /**
     * 可卖出股数 = 总持仓 - 今日买入冻结(T+1) - 卖出挂单冻结。
     */
    function computeAvailableShares(pos) {
        const p = pos || {};
        return Math.max(0, (Number(p.total_shares) || 0) - (Number(p.frozen_today) || 0) - (Number(p.frozen_sell) || 0));
    }

    /**
     * 撮合限价挂单（单标的一次快照）。
     * 买入：限价 >= 最新价 成交；卖出：限价 <= 最新价 成交；挂单当日有效，跨日自动失效。
     * @returns {{fills: Array<{order: object}>, expired: Array<{order: object}>}}
     */
    function matchLimitOrders(orders, price, dateStr) {
        const fills = [];
        const expired = [];
        const px = Number(price);
        if (!Array.isArray(orders) || !Number.isFinite(px) || px <= 0) return { fills, expired };
        orders.forEach((order) => {
            if (!order || order.status !== 'open') return;
            if (order.created_date && order.created_date !== dateStr) {
                expired.push({ order });
                return;
            }
            const op = Number(order.price);
            if (!Number.isFinite(op) || op <= 0) return;
            if (order.side === 'buy' && op >= px) fills.push({ order });
            else if (order.side === 'sell' && op <= px) fills.push({ order });
        });
        return { fills, expired };
    }

    /**
     * 限价买入校验：资金按限价全额冻结，cash 语义即立即可用。
     */
    function validateLimitBuy(cash, price, shares) {
        const px = Number(price);
        const sh = Number(shares);
        if (!Number.isFinite(px) || px <= 0) return { valid: false, error: '限价必须大于 0！' };
        if (!Number.isInteger(sh) || sh <= 0 || sh % 100 !== 0) return { valid: false, error: '买入数量必须为 100 股（1手）的整数倍！' };
        const cost = px * sh;
        const avail = Math.max(0, Number(cash) || 0);
        if (avail < cost - 1e-9) {
            return { valid: false, error: `可用资金不足！限价买入 ${sh} 股需冻结 ¥${cost.toFixed(2)}，可用 ¥${avail.toFixed(2)}。` };
        }
        return { valid: true, cost };
    }

    /**
     * 限价卖出校验：可卖 = 总持仓 - T+1 冻结 - 挂卖冻结。
     */
    function validateLimitSell(pos, price, shares) {
        const px = Number(price);
        const sh = Number(shares);
        if (!Number.isFinite(px) || px <= 0) return { valid: false, error: '限价必须大于 0！' };
        if (!Number.isInteger(sh) || sh <= 0 || sh % 100 !== 0) return { valid: false, error: '卖出数量必须为 100 股（1手）的整数倍！' };
        const avail = computeAvailableShares(pos);
        if (sh > avail) {
            const p = pos || {};
            return { valid: false, error: `可用持仓不足！可卖 ${avail} 股（总持仓 ${Number(p.total_shares) || 0}、T+1 冻结 ${Number(p.frozen_today) || 0}、挂卖冻结 ${Number(p.frozen_sell) || 0}）。` };
        }
        return { valid: true };
    }

    /**
     * A 股模拟交易费用（简化口径）：
     * - 佣金：成交金额的 0.025%，单笔最低 5 元，买卖双边收取；
     * - 印花税：成交金额的 0.05%，仅卖出收取；
     * - 过户费暂不计。
     */
    const COMMISSION_RATE = 0.00025;
    const COMMISSION_MIN = 5;
    const STAMP_TAX_RATE = 0.0005;

    function computeAshareCommission(amount) {
        const amt = Math.max(0, Number(amount) || 0);
        if (amt <= 0) return 0;
        return Math.max(COMMISSION_MIN, amt * COMMISSION_RATE);
    }

    function computeAshareTradeFees(side, amount) {
        const commission = computeAshareCommission(amount);
        if (side === 'sell') {
            const stampTax = (Math.max(0, Number(amount) || 0)) * STAMP_TAX_RATE;
            return { commission, stampTax, total: commission + stampTax };
        }
        return { commission, stampTax: 0, total: commission };
    }

    return {
        computeAshareFloatingPnl,
        computeAsharePnlRate,
        computeWeightedAvgCost,
        calculateMaxBuyLots,
        calculateMaxSellLots,
        calculateAshareFractionLots,
        validateAshareBuy,
        validateAshareSell,
        autoUnfreezeT1Holdings,
        getAshareMarketTag,
        normalizeAshareWatchlistCode,
        sortWatchlistStocks,
        normalizeAshareAccount,
        computeAvailableShares,
        matchLimitOrders,
        validateLimitBuy,
        validateLimitSell,
        computeAshareTradeFees
    };
}));
