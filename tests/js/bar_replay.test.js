const test = require('node:test');
const assert = require('node:assert/strict');
const barReplay = require('../../frontend/js/modules/bar_replay');

test('normalizeTimestamp 正常解析不同格式时间戳', () => {
    // 秒级
    assert.equal(barReplay.normalizeTimestamp(1726000000), 1726000000);
    // 毫秒级
    assert.equal(barReplay.normalizeTimestamp(1726000000000), 1726000000);
    // 数字字符串
    assert.equal(barReplay.normalizeTimestamp('1726000000'), 1726000000);
    // 日期对象
    assert.equal(barReplay.normalizeTimestamp({ year: 2026, month: 9, day: 15 }), Math.floor(Date.UTC(2026, 8, 15) / 1000));
    // 无效输入
    assert.equal(barReplay.normalizeTimestamp(null), null);
    assert.equal(barReplay.normalizeTimestamp(undefined), null);
    assert.equal(barReplay.normalizeTimestamp('invalid'), null);
});

test('findBarIndexByTimestamp 二分查找最匹配的 K 线索引', () => {
    const klines = [
        { time: 1000, close: 10 },
        { time: 2000, close: 20 },
        { time: 3000, close: 30 },
        { time: 4000, close: 40 },
        { time: 5000, close: 50 },
    ];

    // 精确匹配
    assert.equal(barReplay.findBarIndexByTimestamp(klines, 3000), 2);
    assert.equal(barReplay.findBarIndexByTimestamp(klines, 1000), 0);
    assert.equal(barReplay.findBarIndexByTimestamp(klines, 5000), 4);

    // 介于两根 bar 之间，向下匹配至前一根 bar
    assert.equal(barReplay.findBarIndexByTimestamp(klines, 2500), 1);
    assert.equal(barReplay.findBarIndexByTimestamp(klines, 3999), 2);

    // 小于第一根 bar，返回 0
    assert.equal(barReplay.findBarIndexByTimestamp(klines, 500), 0);
    // 大于最后一根 bar，返回最后一根索引
    assert.equal(barReplay.findBarIndexByTimestamp(klines, 8888), 4);

    // 空数组或非法输入
    assert.equal(barReplay.findBarIndexByTimestamp([], 3000), -1);
    assert.equal(barReplay.findBarIndexByTimestamp(null, 3000), -1);
    assert.equal(barReplay.findBarIndexByTimestamp(klines, null), -1);
});

test('sliceKlineData 截断数组', () => {
    const list = [1, 2, 3, 4, 5];
    assert.deepEqual(barReplay.sliceKlineData(list, 2), [1, 2, 3]);
    assert.deepEqual(barReplay.sliceKlineData(list, 0), [1]);
    assert.deepEqual(barReplay.sliceKlineData(list, 4), [1, 2, 3, 4, 5]);
    assert.deepEqual(barReplay.sliceKlineData(list, 10), [1, 2, 3, 4, 5]);
    assert.deepEqual(barReplay.sliceKlineData(list, -1), []);
    assert.deepEqual(barReplay.sliceKlineData([], 2), []);
});

test('getNextReplayStep 计算步进与完成状态', () => {
    assert.deepEqual(barReplay.getNextReplayStep(0, 5), { nextIndex: 1, isFinished: false });
    assert.deepEqual(barReplay.getNextReplayStep(3, 5), { nextIndex: 4, isFinished: false });
    assert.deepEqual(barReplay.getNextReplayStep(4, 5), { nextIndex: 5, isFinished: true });
    assert.deepEqual(barReplay.getNextReplayStep(5, 5), { nextIndex: 5, isFinished: true });
    assert.deepEqual(barReplay.getNextReplayStep(-1, 5), { nextIndex: 0, isFinished: false });
});

test('formatReplayTime 正确格式化 UTC+8 时间', () => {
    // 2026-09-15 00:00:00 UTC = 2026-09-15 08:00:00 UTC+8
    const ts = Date.UTC(2026, 8, 15, 0, 0, 0) / 1000;
    assert.equal(barReplay.formatReplayTime(ts), '2026-09-15 08:00');

    // 2026-09-15 16:00:00 UTC = 2026-09-16 00:00:00 UTC+8 (整日)
    const dayTs = Date.UTC(2026, 8, 15, 16, 0, 0) / 1000;
    assert.equal(barReplay.formatReplayTime(dayTs), '2026-09-16');

    assert.equal(barReplay.formatReplayTime(null), '--');
});

test('createBarReplayState 返回标准初始状态', () => {
    const state = barReplay.createBarReplayState();
    assert.equal(state.active, false);
    assert.equal(state.isSelectingCutPoint, false);
    assert.equal(state.cutIndex, -1);
    assert.deepEqual(state.fullKlineData, []);
    assert.equal(state.playbackSpeed, 1000);
});

test('mapReplayCutToNewPeriod 跨周期精准映射截断索引', () => {
    // 假设从日K (2026-08-10 00:00:00 UTC) 切换到 60m
    const dayTs = Math.floor(Date.UTC(2026, 7, 10, 0, 0, 0) / 1000);
    const minuteKlines = [
        { time: Math.floor(Date.UTC(2026, 7, 9, 14, 0, 0) / 1000) },
        { time: Math.floor(Date.UTC(2026, 7, 9, 15, 0, 0) / 1000) },
        { time: Math.floor(Date.UTC(2026, 7, 10, 10, 30, 0) / 1000) },
        { time: Math.floor(Date.UTC(2026, 7, 10, 11, 30, 0) / 1000) },
        { time: Math.floor(Date.UTC(2026, 7, 10, 14, 0, 0) / 1000) },
        { time: Math.floor(Date.UTC(2026, 7, 10, 15, 0, 0) / 1000) },
        { time: Math.floor(Date.UTC(2026, 7, 11, 10, 30, 0) / 1000) },
    ];

    // 日K映射到分钟K线，自动对齐到该日收盘 bar (15:00, 索引 5)
    const cutIdx = barReplay.mapReplayCutToNewPeriod(dayTs, minuteKlines);
    assert.equal(cutIdx, 5);

    // 从分钟K (2026-08-10 11:30) 切换到 15m
    const minTs = Math.floor(Date.UTC(2026, 7, 10, 11, 30, 0) / 1000);
    const idx15m = barReplay.mapReplayCutToNewPeriod(minTs, minuteKlines);
    assert.equal(idx15m, 3);
});

