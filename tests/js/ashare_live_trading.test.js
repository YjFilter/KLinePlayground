'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const ashare = require('../../frontend/js/modules/ashare_trading.js');

test('computeAshareFloatingPnl 计算持仓浮动盈亏金额', () => {
    // 成本 100，现价 110，持仓 1000 股 -> 盈利 10,000 元
    assert.equal(ashare.computeAshareFloatingPnl(100, 110, 1000), 10000);
    // 成本 100，现价 95，持仓 1000 股 -> 亏损 5,000 元
    assert.equal(ashare.computeAshareFloatingPnl(100, 95, 1000), -5000);
    // 无持仓或价格为0 -> 0
    assert.equal(ashare.computeAshareFloatingPnl(0, 100, 1000), 0);
    assert.equal(ashare.computeAshareFloatingPnl(100, 0, 1000), 0);
    assert.equal(ashare.computeAshareFloatingPnl(100, 110, 0), 0);
});

test('computeAsharePnlRate 计算盈亏百分比', () => {
    // 成本 50，现价 55 -> +10%
    assert.equal(ashare.computeAsharePnlRate(50, 55), 10);
    // 成本 50，现价 45 -> -10%
    assert.equal(ashare.computeAsharePnlRate(50, 45), -10);
    // 成本为0 -> 0
    assert.equal(ashare.computeAsharePnlRate(0, 55), 0);
});

test('computeWeightedAvgCost 计算加权买入持仓均价', () => {
    // 原有 1000 股成本 10 元，新买入 1000 股价格 20 元 -> 均价 15 元
    assert.equal(ashare.computeWeightedAvgCost(1000, 10, 1000, 20), 15);
    // 初始买入 500 股价格 100 元 -> 均价 100 元
    assert.equal(ashare.computeWeightedAvgCost(0, 0, 500, 100), 100);
    // 原有 200 股成本 10 元，加仓 800 股价格 20 元 -> (2000 + 16000) / 1000 = 18 元
    assert.equal(ashare.computeWeightedAvgCost(200, 10, 800, 20), 18);
});

test('calculateMaxBuyLots 计算最大可买手数（100股整倍数）', () => {
    // 现金 100,000 元，现价 18.50 元 -> 1手成本 1850 元 -> 100000 / 1850 = 54.05 -> 54 手
    assert.equal(ashare.calculateMaxBuyLots(100000, 18.5), 54);
    // 现金 1,000 元，现价 18.50 元 (一手 1850 元) -> 0 手
    assert.equal(ashare.calculateMaxBuyLots(1000, 18.5), 0);
    // 价格为 0 或现金为 0
    assert.equal(ashare.calculateMaxBuyLots(100000, 0), 0);
    assert.equal(ashare.calculateMaxBuyLots(0, 18.5), 0);
});

test('calculateMaxSellLots 计算最大可卖手数', () => {
    // 可用持仓 580 股 -> 5 手
    assert.equal(ashare.calculateMaxSellLots(580), 5);
    // 可用持仓 99 股 -> 0 手
    assert.equal(ashare.calculateMaxSellLots(99), 0);
});

test('calculateAshareFractionLots 按比例计算手数并整手向下取整', () => {
    const maxLots = 54;
    // 25% -> 54 * 0.25 = 13.5 -> 13 手
    assert.equal(ashare.calculateAshareFractionLots(maxLots, 0.25), 13);
    // 50% -> 54 * 0.5 = 27 手
    assert.equal(ashare.calculateAshareFractionLots(maxLots, 0.5), 27);
    // 75% -> 54 * 0.75 = 40.5 -> 40 手
    assert.equal(ashare.calculateAshareFractionLots(maxLots, 0.75), 40);
    // 100% / 全仓 -> 54 手
    assert.equal(ashare.calculateAshareFractionLots(maxLots, 1), 54);
});

test('validateAshareBuy 校验买入输入与可用现金', () => {
    // 正常买入 2 手，单价 50 元，需要 10,000 元，现金 50,000 元
    const res1 = ashare.validateAshareBuy(2, 50000, 50);
    assert.equal(res1.valid, true);
    assert.equal(res1.shares, 200);
    assert.equal(res1.cost, 10000);

    // 现金不足
    const res2 = ashare.validateAshareBuy(2, 5000, 50);
    assert.equal(res2.valid, false);
    assert.match(res2.error, /可用资金不足/);

    // 手数为 0 或负数
    const res3 = ashare.validateAshareBuy(0, 50000, 50);
    assert.equal(res3.valid, false);
    assert.match(res3.error, /最小单位为 1 手/);
});

test('validateAshareSell 严格遵守 T+1 规则阻断当日冻结股票', () => {
    // 总持仓 1000 股，今日买入冻结 600 股，可用 400 股 (4手)
    // 尝试卖出 4 手 -> 允许
    const res1 = ashare.validateAshareSell(4, 1000, 600, 50);
    assert.equal(res1.valid, true);
    assert.equal(res1.shares, 400);
    assert.equal(res1.revenue, 20000);

    // 尝试卖出 5 手 (500 股 > 可用 400 股) -> 必须阻断并报错 T+1 限制
    const res2 = ashare.validateAshareSell(5, 1000, 600, 50);
    assert.equal(res2.valid, false);
    assert.match(res2.error, /【T\+1 卖出限制】可用持仓不足/);
    assert.match(res2.error, /今日买入冻结 600 股/);
});

test('autoUnfreezeT1Holdings 跨日自动解冻持仓', () => {
    const positions = {
        '600519': { total_shares: 1000, frozen_today: 400 },
        '000001': { total_shares: 500, frozen_today: 500 }
    };
    // 同一天不解冻
    const resSameDay = ashare.autoUnfreezeT1Holdings(positions, '2026-09-08', '2026-09-08');
    assert.equal(resSameDay.thawed, false);
    assert.equal(positions['600519'].frozen_today, 400);

    // 跨日自动解冻
    const resNextDay = ashare.autoUnfreezeT1Holdings(positions, '2026-09-08', '2026-09-09');
    assert.equal(resNextDay.thawed, true);
    assert.equal(resNextDay.count, 900);
    assert.equal(positions['600519'].frozen_today, 0);
    assert.equal(positions['000001'].frozen_today, 0);
});

test('getAshareMarketTag 正确识别股票市场与指数徽章', () => {
    assert.deepEqual(ashare.getAshareMarketTag('600519', false), { text: '沪', cls: 'sh' });
    assert.deepEqual(ashare.getAshareMarketTag('sh600519', false), { text: '沪', cls: 'sh' });
    assert.deepEqual(ashare.getAshareMarketTag('688001', false), { text: '科', cls: 'kcb' });
    assert.deepEqual(ashare.getAshareMarketTag('000001', false), { text: '深', cls: 'sz' });
    assert.deepEqual(ashare.getAshareMarketTag('300750', false), { text: '创', cls: 'cyb' });
    assert.deepEqual(ashare.getAshareMarketTag('830001', false), { text: '北', cls: 'sz' });
    assert.deepEqual(ashare.getAshareMarketTag('000001', true), { text: '指', cls: 'idx' });
});

test('normalizeAshareWatchlistCode 规范化代码', () => {
    assert.equal(ashare.normalizeAshareWatchlistCode('sh600519'), '600519');
    assert.equal(ashare.normalizeAshareWatchlistCode('SZ300750'), '300750');
    assert.equal(ashare.normalizeAshareWatchlistCode('002594'), '002594');
});

test('sortWatchlistStocks 支持按最新价或涨跌幅升降序排序', () => {
    const stocks = [
        { code: '600519', name: '茅台' },
        { code: '300750', name: '宁德' },
        { code: '002594', name: '比亚迪' }
    ];
    const quotes = {
        '600519': { price: 1400, change_percent: -1.2 },
        '300750': { price: 330, change_percent: 2.5 },
        '002594': { price: 280, change_percent: 0.8 }
    };

    // 按价格降序
    const byPriceDesc = ashare.sortWatchlistStocks(stocks, quotes, 'price', 'desc');
    assert.deepEqual(byPriceDesc.map(s => s.code), ['600519', '300750', '002594']);

    // 按价格升序
    const byPriceAsc = ashare.sortWatchlistStocks(stocks, quotes, 'price', 'asc');
    assert.deepEqual(byPriceAsc.map(s => s.code), ['002594', '300750', '600519']);

    // 按涨幅降序
    const byChangeDesc = ashare.sortWatchlistStocks(stocks, quotes, 'change', 'desc');
    assert.deepEqual(byChangeDesc.map(s => s.code), ['300750', '002594', '600519']);

    // 按涨幅升序
    const byChangeAsc = ashare.sortWatchlistStocks(stocks, quotes, 'change', 'asc');
    assert.deepEqual(byChangeAsc.map(s => s.code), ['600519', '002594', '300750']);
});


// ========== 限价挂单（当日有效、撮合、冻结） ==========

test('normalizeAshareAccount 补齐挂单字段并兼容旧数据', () => {
    const acc = ashare.normalizeAshareAccount({ cash: 50000, positions: { '600519': { total_shares: 200, frozen_today: 100 } } });
    assert.equal(acc.cash_frozen, 0);
    assert.deepEqual(acc.pending_orders, []);
    assert.deepEqual(acc.last_prices, {});
    assert.equal(acc.positions['600519'].frozen_sell, 0);
    assert.equal(acc.positions['600519'].avg_cost, 0);
    // 非法输入返回全新账户
    const fresh = ashare.normalizeAshareAccount(null);
    assert.equal(fresh.cash, 100000);
});

test('computeAvailableShares 扣除 T+1 冻结与挂卖冻结', () => {
    assert.equal(ashare.computeAvailableShares({ total_shares: 1000, frozen_today: 200, frozen_sell: 300 }), 500);
    assert.equal(ashare.computeAvailableShares({ total_shares: 100, frozen_today: 200, frozen_sell: 0 }), 0);
    assert.equal(ashare.computeAvailableShares(null), 0);
});

test('matchLimitOrders 买入限价 >= 现价成交、卖出限价 <= 现价成交', () => {
    const orders = [
        { id: 'b1', side: 'buy', price: 10.00, status: 'open', created_date: '2026-09-10' },
        { id: 'b2', side: 'buy', price: 9.99, status: 'open', created_date: '2026-09-10' },
        { id: 's1', side: 'sell', price: 9.50, status: 'open', created_date: '2026-09-10' },
        { id: 's2', side: 'sell', price: 10.01, status: 'open', created_date: '2026-09-10' }
    ];
    const { fills, expired } = ashare.matchLimitOrders(orders, 10.00, '2026-09-10');
    assert.deepEqual(fills.map(f => f.order.id), ['b1', 's1']);
    assert.equal(expired.length, 0);
});

test('matchLimitOrders 跨日挂单自动失效', () => {
    const orders = [{ id: 'b1', side: 'buy', price: 10.00, status: 'open', created_date: '2026-09-09' }];
    const { fills, expired } = ashare.matchLimitOrders(orders, 10.00, '2026-09-10');
    assert.equal(fills.length, 0);
    assert.equal(expired.length, 1);
    assert.equal(expired[0].order.id, 'b1');
});

test('matchLimitOrders 忽略非法输入与非 open 状态', () => {
    assert.deepEqual(ashare.matchLimitOrders(null, 10, '2026-09-10'), { fills: [], expired: [] });
    const orders = [{ id: 'c1', side: 'buy', price: 10, status: 'canceled', created_date: '2026-09-10' }];
    assert.deepEqual(ashare.matchLimitOrders(orders, 10, '2026-09-10'), { fills: [], expired: [] });
});

test('validateLimitBuy 资金按限价全额校验', () => {
    assert.equal(ashare.validateLimitBuy(10000, 9.00, 1000).valid, true);
    assert.equal(ashare.validateLimitBuy(9999, 10.00, 1000).valid, false); // 资金差 1 元不足
    assert.equal(ashare.validateLimitBuy(10000, 10.00, 150).valid, false); // 非整百
    assert.equal(ashare.validateLimitBuy(10000, 0, 100).valid, false);
});

test('validateLimitSell 可卖扣除 T+1 与挂卖冻结', () => {
    const pos = { total_shares: 1000, frozen_today: 200, frozen_sell: 300 };
    assert.equal(ashare.validateLimitSell(pos, 10, 500).valid, true);
    assert.equal(ashare.validateLimitSell(pos, 10, 501).valid, false);
    assert.equal(ashare.validateLimitSell(pos, 10, 100).valid, true); // 100 < 可卖 500
    assert.equal(ashare.validateLimitSell(pos, 0, 100).valid, false);
});

// ========== 交易费用（佣金万2.5最低5元双边 + 卖出印花税0.05%） ==========

test('computeAshareTradeFees 买入仅佣金、小额触发最低5元', () => {
    // 10万元成交：佣金 25 元，无印花税
    const big = ashare.computeAshareTradeFees('buy', 100000);
    assert.equal(big.commission, 25);
    assert.equal(big.stampTax, 0);
    assert.equal(big.total, 25);
    // 8000 元成交：万2.5 = 2 元 < 5 元 -> 触发最低 5 元
    const small = ashare.computeAshareTradeFees('buy', 8000);
    assert.equal(small.commission, 5);
    assert.equal(small.total, 5);
});

test('computeAshareTradeFees 卖出含印花税', () => {
    const fees = ashare.computeAshareTradeFees('sell', 100000);
    assert.equal(fees.commission, 25);
    assert.equal(fees.stampTax, 50);
    assert.equal(fees.total, 75);
    // 零金额无费用
    const zero = ashare.computeAshareTradeFees('sell', 0);
    assert.equal(zero.total, 0);
});

// ========== 画图默认样式归一化（drawing_tools.js 样式记忆） ==========

const drawingTools = require('../../frontend/js/drawing_tools.js');

test('normalizeDrawingDefaultStyle 只保留四个合法通用字段', () => {
    const style = drawingTools.normalizeDrawingDefaultStyle({
        color: ' #ff5566 ',
        lineWidth: 4.5,
        lineStyle: 'dashed',
        labelVisible: false,
        fillColor: 'should-be-dropped',
        fontSize: 99,
    });
    assert.deepEqual(style, { color: '#ff5566', lineWidth: 4.5, lineStyle: 'dashed', labelVisible: false });
});

test('normalizeDrawingDefaultStyle 非法输入全部丢弃', () => {
    assert.deepEqual(drawingTools.normalizeDrawingDefaultStyle({
        color: '',
        lineWidth: -1,
        lineStyle: 'wavy',
        labelVisible: 'yes',
    }), {});
    assert.deepEqual(drawingTools.normalizeDrawingDefaultStyle(null), {});
});
