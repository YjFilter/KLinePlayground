const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const drawingTools = require(path.resolve(__dirname, '../../frontend/js/drawing_tools.js'));
const { getBarDateString, anchorToCoordinate } = drawingTools;

test('getBarDateString 提取正确 UTC 日期字符串', () => {
    // 2026-03-10 00:00:00 UTC = 1773100800
    assert.equal(getBarDateString(1773100800), '2026-03-10');
    // 2026-03-10 11:30:00 UTC = 1773142200
    assert.equal(getBarDateString(1773142200), '2026-03-10');
    // 2026-03-10 15:00:00 UTC = 1773154800
    assert.equal(getBarDateString(1773154800), '2026-03-10');
    assert.equal(getBarDateString({ year: 2026, month: 3, day: 10 }), '2026-03-10');
    assert.equal(getBarDateString(null), null);
});

test('anchorToCoordinate: 直连精确时间命中优先返回', () => {
    const timeScale = {
        timeToCoordinate(t) {
            return t === 1000 ? 150 : null;
        }
    };
    const x = anchorToCoordinate(timeScale, { time: 1000, price: 20 }, [{ time: 1000 }]);
    assert.equal(x, 150);
});

test('anchorToCoordinate: 日K锚点切换到120分时精确吸附至同日峰值K线', () => {
    // 模拟日K画线：2026-03-10 00:00:00, 价格 44.06（高点）
    const anchor = { time: 1773100800, price: 44.06 };
    // 120分K线数据：2026-03-10 有两根 (11:30 与 15:00)
    // 11:30 high 为 42.7, 15:00 high 为 44.03（最接近 44.06）
    const m120Bars = [
        { time: 1773055800, time_str: '2026-03-09 15:00', open: 39, high: 41, low: 38, close: 40 },
        { time: 1773142200, time_str: '2026-03-10 11:30', open: 41, high: 42.7, low: 40.74, close: 42 },
        { time: 1773154800, time_str: '2026-03-10 15:00', open: 42, high: 44.03, low: 41.64, close: 43.5 },
        { time: 1773228600, time_str: '2026-03-11 11:30', open: 43, high: 43.8, low: 42, close: 42.5 },
    ];

    const timeScale = {
        timeToCoordinate(t) {
            if (t === 1773142200) return 200;
            if (t === 1773154800) return 260; // 15:00 对应坐标
            return null;
        }
    };

    const x = anchorToCoordinate(timeScale, anchor, m120Bars);
    assert.equal(x, 260, '应精确吸附到同日高点所在的 15:00 K线坐标');
});

test('anchorToCoordinate: 120分画线切换回日K精准对齐到同日日K', () => {
    // 120分锚点：2026-03-10 15:00:00 (1773154800)
    const anchor = { time: 1773154800, price: 44.06 };
    const dailyBars = [
        { time: 1773014400, time_str: '2026-03-09' },
        { time: 1773100800, time_str: '2026-03-10' },
        { time: 1773187200, time_str: '2026-03-11' },
    ];

    const timeScale = {
        timeToCoordinate(t) {
            if (t === 1773100800) return 320; // 2026-03-10 日K
            return null;
        }
    };

    const x = anchorToCoordinate(timeScale, anchor, dailyBars);
    assert.equal(x, 320, '应准确映射到 2026-03-10 的日K线坐标');
});

test('anchorToCoordinate: 远早于当前数据首根的历史锚点返回 null 阻止跨屏乱线', () => {
    // 锚点为 6 个月前 (2026-03-10)
    const anchor = { time: 1773100800, price: 44.06 };
    // 当前图表只有最近 3 天数据 (首根为 2026-09-14)
    const recentBars = [
        { time: 1789383180, time_str: '2026-09-14 10:53' },
        { time: 1789568400, time_str: '2026-09-16 15:00' },
    ];

    const timeScale = {
        timeToCoordinate() { return null; },
        coordinateToLogical() { return 0; },
        logicalToCoordinate(l) { return l * 10; }
    };

    const x = anchorToCoordinate(timeScale, anchor, recentBars);
    assert.equal(x, null, '超出历史深度数月的锚点应返回 null，杜绝虚假负坐标连线乱飞');
});

test('anchorToCoordinate: 最新K线右侧未来预测区支持线性外推', () => {
    const bars = [
        { time: 1000 },
        { time: 2000 }
    ];
    const anchor = { time: 2500, price: 50 }; // 大于最新 2000
    const timeScale = {
        timeToCoordinate(t) { return t === 2000 ? 200 : (t === 1000 ? 100 : null); },
        coordinateToLogical(coord) { return coord / 10; },
        logicalToCoordinate(logical) { return logical * 10; }
    };
    const timeProjection = {
        firstTime: 1000,
        lastTime: 2000,
        interval: 100
    };
    const x = anchorToCoordinate(timeScale, anchor, bars, timeProjection);
    assert.ok(Number.isFinite(x), '未来投影区应返回有效坐标');
});
