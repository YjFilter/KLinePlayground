(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.KLineBarReplayModule = factory();
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    /**
     * 规范化时间戳（统一为秒级 Unix 时间戳）。
     */
    function normalizeTimestamp(time) {
        if (time === null || time === undefined) return null;
        if (typeof time === 'number') {
            return time > 1e11 ? Math.floor(time / 1000) : Math.floor(time);
        }
        if (typeof time === 'string') {
            var n = Number(time);
            if (!Number.isNaN(n) && n > 0) {
                return n > 1e11 ? Math.floor(n / 1000) : Math.floor(n);
            }
            var d = new Date(time);
            if (!Number.isNaN(d.getTime())) {
                return Math.floor(d.getTime() / 1000);
            }
        }
        if (typeof time === 'object' && time.year && time.month && time.day) {
            var date = new Date(Date.UTC(time.year, time.month - 1, time.day));
            return Math.floor(date.getTime() / 1000);
        }
        return null;
    }

    /**
     * 在 K 线数组中二分查找与给定时间戳最匹配（小于或等于 targetTime）的 bar 索引。
     * @param {Array} klines - K 线数组，需按时间递增排序
     * @param {number|string|object} targetTime - 目标时间
     * @returns {number} 匹配到的 bar 索引，找不到有效 bar 时返回 -1
     */
    function findBarIndexByTimestamp(klines, targetTime) {
        if (!Array.isArray(klines) || klines.length === 0) return -1;
        var ts = normalizeTimestamp(targetTime);
        if (ts === null) return -1;

        var firstTs = normalizeTimestamp(klines[0].time);
        if (firstTs !== null && ts <= firstTs) return 0;

        var lastTs = normalizeTimestamp(klines[klines.length - 1].time);
        if (lastTs !== null && ts >= lastTs) return klines.length - 1;

        var low = 0;
        var high = klines.length - 1;
        var bestIndex = 0;

        while (low <= high) {
            var mid = Math.floor((low + high) / 2);
            var midTs = normalizeTimestamp(klines[mid].time);
            if (midTs === null) {
                low = mid + 1;
                continue;
            }

            if (midTs === ts) {
                return mid;
            } else if (midTs < ts) {
                bestIndex = mid;
                low = mid + 1;
            } else {
                high = mid - 1;
            }
        }

        return bestIndex;
    }

    /**
     * 根据截断索引对 K 线或成交量数组进行切片（包含 cutIndex 所在 bar）。
     * @param {Array} list - 原始数组
     * @param {number} cutIndex - 截断索引
     * @returns {Array} 切片后的新数组（浅拷贝元素）
     */
    function sliceKlineData(list, cutIndex) {
        if (!Array.isArray(list) || list.length === 0) return [];
        if (cutIndex < 0) return [];
        var end = Math.min(list.length, cutIndex + 1);
        return list.slice(0, end);
    }

    /**
     * 计算下一前进单步的位置与是否到达终点。
     * @param {number} currentIndex - 当前复盘所在索引
     * @param {number} maxIndex - 全量数据最大索引（list.length - 1）
     * @returns {{ nextIndex: number, isFinished: boolean }}
     */
    function getNextReplayStep(currentIndex, maxIndex) {
        if (currentIndex < 0) {
            return { nextIndex: 0, isFinished: maxIndex <= 0 };
        }
        var next = currentIndex + 1;
        if (next >= maxIndex) {
            return { nextIndex: maxIndex, isFinished: true };
        }
        return { nextIndex: next, isFinished: false };
    }

    /**
     * 格式化复盘时间显示（东八区 UTC+8）。
     * @param {number|string|object} time
     * @returns {string} e.g. "2026-08-15 14:00" 或 "2026-08-15"
     */
    function formatReplayTime(time) {
        var ts = normalizeTimestamp(time);
        if (ts === null) return '--';
        var d = new Date(ts * 1000 + 8 * 3600 * 1000); // 偏移至 UTC+8
        var y = d.getUTCFullYear();
        var m = String(d.getUTCMonth() + 1).padStart(2, '0');
        var day = String(d.getUTCDate()).padStart(2, '0');
        var hh = String(d.getUTCHours()).padStart(2, '0');
        var mm = String(d.getUTCMinutes()).padStart(2, '0');

        if (hh === '00' && mm === '00') {
            return y + '-' + m + '-' + day;
        }
        return y + '-' + m + '-' + day + ' ' + hh + ':' + mm;
    }

    /**
     * 将原复盘时间点映射到新周期 K 线数组的最佳截断索引。
     * 若原时间为日级别（时分秒为0），在新分钟周期中优先对齐到该日收盘 bar。
     * @param {number|string|object} originalTime - 原复盘时间戳
     * @param {Array} newKlines - 新周期的全量 K 线数组
     * @returns {number} 在新周期中的截断索引
     */
    function mapReplayCutToNewPeriod(originalTime, newKlines) {
        if (!Array.isArray(newKlines) || newKlines.length === 0) return -1;
        var ts = normalizeTimestamp(originalTime);
        if (ts === null) return 0;

        // 检查原时间是否为午夜 00:00:00（如日K/周K时间戳）
        var d = new Date(ts * 1000);
        var isMidnight = (d.getUTCHours() === 0 && d.getUTCMinutes() === 0 && d.getUTCSeconds() === 0);

        // 检查新周期是否为日内细粒度（有非午夜的分钟/小时 bar）
        var hasIntradayBars = false;
        for (var i = 0; i < Math.min(10, newKlines.length); i++) {
            var kts = normalizeTimestamp(newKlines[i].time);
            if (kts !== null) {
                var kd = new Date(kts * 1000);
                if (kd.getUTCHours() !== 0 || kd.getUTCMinutes() !== 0) {
                    hasIntradayBars = true;
                    break;
                }
            }
        }

        var searchTarget = ts;
        // 如果原时间是日线午夜，而新数据是日内分钟线，则查找该自然日/交易日最后一根分钟线（+86399秒）
        if (isMidnight && hasIntradayBars) {
            searchTarget = ts + 86399;
        }

        var idx = findBarIndexByTimestamp(newKlines, searchTarget);
        if (idx < 0) idx = 0;
        return idx;
    }

    /**
     * 创建干净的复盘初始状态对象。
     */
    function createBarReplayState() {
        return {
            active: false,
            isSelectingCutPoint: false,
            cutTimestamp: null,
            cutIndex: -1,
            fullKlineData: [],
            fullVolumeData: [],
            isPlaying: false,
            timerId: null,
            playbackSpeed: 1000,
            originalSymbol: null,
            originalPeriod: null,
        };
    }

    return {
        normalizeTimestamp: normalizeTimestamp,
        findBarIndexByTimestamp: findBarIndexByTimestamp,
        sliceKlineData: sliceKlineData,
        getNextReplayStep: getNextReplayStep,
        formatReplayTime: formatReplayTime,
        mapReplayCutToNewPeriod: mapReplayCutToNewPeriod,
        createBarReplayState: createBarReplayState
    };
}));
