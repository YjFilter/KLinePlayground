/**
 * KLinePlayground - Crypto Period Snapshot Cache Module
 * Per-period replay snapshot cache with LRU eviction and training-id scoping,
 * so switching periods replays instantly and returning to a period restores
 * its cached window.
 *
 * Extracted from main_enhanced.js (2026-08-30). Classic-script shared bindings
 * `currentTraining` and `chartWindowState` are declared read-only globals for
 * lint purposes; in node tests set `globalThis.currentTraining` explicitly.
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory(require('./chart_window_core.js'));
    } else {
        root.KLinePeriodSnapshotCache = factory(root.KLineChartWindowCore || {});
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (chartWindowCore) {
    'use strict';

    const parseChartWindowTimestamp = chartWindowCore.parseChartWindowTimestamp;

    const CRYPTO_PERIOD_SNAPSHOT_CACHE_LIMIT = 16;
    const cryptoPeriodSnapshotCache = new Map();
    let cryptoPeriodSnapshotCacheTrainingId = null;

    function clearCryptoPeriodSnapshotCache() {
        cryptoPeriodSnapshotCache.clear();
        cryptoPeriodSnapshotCacheTrainingId = currentTraining?.id === undefined || currentTraining?.id === null
            ? null
            : String(currentTraining.id);
    }

    // 只清指定周期的快照缓存（回放推进/分段加载时保留其他周期缓存，回切秒回）。
    function clearCryptoPeriodSnapshotCacheForPeriod(period) {
        if (!period) return;
        const prefix = String(currentTraining?.id || '') + '|' + String(period) + '|';
        for (const cacheKey of Array.from(cryptoPeriodSnapshotCache.keys())) {
            if (cacheKey.startsWith(prefix)) cryptoPeriodSnapshotCache.delete(cacheKey);
        }
    }

    function syncCryptoPeriodSnapshotCacheTraining(trainingId) {
        const normalizedTrainingId = trainingId === undefined || trainingId === null
            ? null
            : String(trainingId);
        if (cryptoPeriodSnapshotCacheTrainingId === normalizedTrainingId) return;
        cryptoPeriodSnapshotCache.clear();
        cryptoPeriodSnapshotCacheTrainingId = normalizedTrainingId;
    }

    function cryptoPeriodSnapshotCacheTimestamp(value) {
        const parsed = parseChartWindowTimestamp(value);
        return parsed ? String(Math.floor(parsed.getTime() / 1000)) : String(value || '');
    }

    function buildCryptoPeriodSnapshotCacheKey(trainingId, period, replayTime, windowState) {
        const state = windowState !== undefined ? windowState
            : (typeof chartWindowState !== 'undefined' ? chartWindowState : null);
        const expandedWindow = Boolean(state?.extended_history);
        const windowStart = expandedWindow ? cryptoPeriodSnapshotCacheTimestamp(state.window_start) : '';
        const windowEnd = expandedWindow ? cryptoPeriodSnapshotCacheTimestamp(state.window_end) : '';
        const historyStart = cryptoPeriodSnapshotCacheTimestamp(state?.history_start);
        const historyEnd = cryptoPeriodSnapshotCacheTimestamp(state?.history_end);
        const renderStart = cryptoPeriodSnapshotCacheTimestamp(state?.render_start);
        const renderEnd = cryptoPeriodSnapshotCacheTimestamp(state?.render_end);
        return [
            String(trainingId || ''),
            String(period || ''),
            expandedWindow ? 'extended_history' : 'default_window',
            windowStart,
            windowEnd,
            historyStart,
            historyEnd,
            renderStart,
            renderEnd,
            cryptoPeriodSnapshotCacheTimestamp(replayTime),
        ].join('|');
    }

    function getCryptoReplayCacheTime() {
        return currentTraining?.current_time || currentTraining?.latestProgress?.current_time || null;
    }

    function getCryptoPeriodSnapshotCache(cacheKey) {
        if (!cryptoPeriodSnapshotCache.has(cacheKey)) return null;
        const snapshot = cryptoPeriodSnapshotCache.get(cacheKey);
        cryptoPeriodSnapshotCache.delete(cacheKey);
        cryptoPeriodSnapshotCache.set(cacheKey, snapshot);
        return snapshot;
    }

    function setCryptoPeriodSnapshotCache(cacheKey, snapshot) {
        if (!cacheKey || !snapshot) return;
        cryptoPeriodSnapshotCache.delete(cacheKey);
        cryptoPeriodSnapshotCache.set(cacheKey, snapshot);
        while (cryptoPeriodSnapshotCache.size > CRYPTO_PERIOD_SNAPSHOT_CACHE_LIMIT) {
            const oldestKey = cryptoPeriodSnapshotCache.keys().next().value;
            cryptoPeriodSnapshotCache.delete(oldestKey);
        }
    }

    return {
        buildCryptoPeriodSnapshotCacheKey,
        clearCryptoPeriodSnapshotCache,
        clearCryptoPeriodSnapshotCacheForPeriod,
        getCryptoPeriodSnapshotCache,
        getCryptoReplayCacheTime,
        setCryptoPeriodSnapshotCache,
        syncCryptoPeriodSnapshotCacheTraining
    };
}));
