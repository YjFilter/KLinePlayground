'use strict';

// period_snapshot_cache.js 单测。
// 运行：node --test tests/js/

const { test } = require('node:test');
const assert = require('node:assert/strict');
const cache = require('../../frontend/js/modules/period_snapshot_cache.js');

test('buildCryptoPeriodSnapshotCacheKey 生成稳定窗口键', () => {
    const key = cache.buildCryptoPeriodSnapshotCacheKey(
        7, '1d', '2026-08-30 10:00:00',
        { history_start: '2024-09-01 00:00:00', history_end: '2026-08-30 00:00:00' }
    );
    const parts = key.split('|');
    assert.equal(parts[0], '7');
    assert.equal(parts[1], '1d');
    assert.equal(parts[2], 'default_window');
    assert.equal(parts[5], String(Math.floor(Date.UTC(2024, 8, 1) / 1000)));
    assert.equal(parts[9], String(Math.floor(Date.UTC(2026, 7, 30, 10, 0, 0) / 1000)));
});

test('extended_history 窗口进入键且包含 window 边界', () => {
    const key = cache.buildCryptoPeriodSnapshotCacheKey(7, '1d', null, {
        extended_history: true,
        window_start: '2024-01-01 00:00:00',
        window_end: '2026-08-30 00:00:00',
    });
    assert.ok(key.includes('extended_history'));
    assert.ok(key.includes(String(Math.floor(Date.UTC(2024, 0, 1) / 1000))));
});

test('快照缓存命中与未命中', () => {
    cache.setCryptoPeriodSnapshotCache('k1', { kline_data: [1] });
    assert.deepEqual(cache.getCryptoPeriodSnapshotCache('k1'), { kline_data: [1] });
    assert.equal(cache.getCryptoPeriodSnapshotCache('missing'), null);
    // 无效入参不写入
    cache.setCryptoPeriodSnapshotCache('', { kline_data: [] });
    cache.setCryptoPeriodSnapshotCache('k2', null);
    assert.equal(cache.getCryptoPeriodSnapshotCache('k2'), null);
});

test('LRU 淘汰最旧键', () => {
    for (let i = 0; i < 20; i++) {
        cache.setCryptoPeriodSnapshotCache(`lru-${i}`, { i });
    }
    assert.equal(cache.getCryptoPeriodSnapshotCache('lru-0'), null, '最旧键应被淘汰');
    assert.deepEqual(cache.getCryptoPeriodSnapshotCache('lru-19'), { i: 19 }, '最新键应保留');
});

test('syncCryptoPeriodSnapshotCacheTraining 换会话清空缓存', () => {
    globalThis.currentTraining = { id: 'a' };
    cache.syncCryptoPeriodSnapshotCacheTraining('a');
    cache.setCryptoPeriodSnapshotCache('sess-a', { v: 1 });
    cache.syncCryptoPeriodSnapshotCacheTraining('b');
    assert.equal(cache.getCryptoPeriodSnapshotCache('sess-a'), null);
});

test('clearCryptoPeriodSnapshotCacheForPeriod 只清指定周期', () => {
    globalThis.currentTraining = { id: 'x' };
    cache.syncCryptoPeriodSnapshotCacheTraining('x');
    cache.setCryptoPeriodSnapshotCache('x|1d|t1', { p: '1d' });
    cache.setCryptoPeriodSnapshotCache('x|15m|t2', { p: '15m' });
    cache.clearCryptoPeriodSnapshotCacheForPeriod('1d');
    assert.equal(cache.getCryptoPeriodSnapshotCache('x|1d|t1'), null);
    assert.deepEqual(cache.getCryptoPeriodSnapshotCache('x|15m|t2'), { p: '15m' });
});

test('getCryptoReplayCacheTime 读取当前回放时间', () => {
    globalThis.currentTraining = { id: 'x', current_time: '2026-08-30 11:00:00' };
    assert.equal(cache.getCryptoReplayCacheTime(), '2026-08-30 11:00:00');
    globalThis.currentTraining = { id: 'x', latestProgress: { current_time: 'fallback' } };
    assert.equal(cache.getCryptoReplayCacheTime(), 'fallback');
});
