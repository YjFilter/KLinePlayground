/**
 * KLinePlayground - Extreme Price Tags Module (AICoin style)
 * Tracks and renders the visible-range High / Low extreme markers on the chart.
 * Living implementation extracted from main_enhanced.js (2026-08-30); the chart,
 * series and rendered bars are injected by the caller to avoid global coupling.
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.KLineExtremeTagsModule = factory();
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function formatExtremePriceValue(value) {
        const numericValue = Number(value);
        if (!Number.isFinite(numericValue)) return '--';
        const absoluteValue = Math.abs(numericValue);
        const maximumFractionDigits = absoluteValue >= 100 ? 2 : absoluteValue >= 1 ? 4 : 8;
        return numericValue.toLocaleString(undefined, { maximumFractionDigits });
    }

    function createExtremePriceTag(id) {
        let tag = document.getElementById(id);
        if (!tag) {
            tag = document.createElement('div');
            tag.id = id;
            tag.className = 'chart-extreme-price-tag';
            const chartEl = document.getElementById('chart');
            if (chartEl) chartEl.appendChild(tag);
        }
        return tag;
    }

    function hideTags(highTag, lowTag) {
        if (highTag) highTag.style.display = 'none';
        if (lowTag) lowTag.style.display = 'none';
    }

    function updateVisibleExtremePriceTags(chart, candlestickSeries, klineData) {
        const highTag = document.getElementById('chart-high-tag') || createExtremePriceTag('chart-high-tag');
        const lowTag = document.getElementById('chart-low-tag') || createExtremePriceTag('chart-low-tag');
        if (!chart || !candlestickSeries || !Array.isArray(klineData) || klineData.length === 0) {
            hideTags(highTag, lowTag);
            return;
        }

        const trainingInterface = document.getElementById('training-interface');
        if (trainingInterface && trainingInterface.classList.contains('hidden')) {
            hideTags(highTag, lowTag);
            return;
        }

        const range = chart.timeScale().getVisibleLogicalRange?.();
        if (!range) {
            hideTags(highTag, lowTag);
            return;
        }

        const fromIdx = Math.max(0, Math.floor(range.from));
        const toIdx = Math.min(klineData.length - 1, Math.ceil(range.to));
        if (fromIdx > toIdx || fromIdx >= klineData.length || toIdx < 0) {
            hideTags(highTag, lowTag);
            return;
        }

        let highestBar = null;
        let lowestBar = null;
        let maxHigh = -Infinity;
        let minLow = Infinity;

        for (let i = fromIdx; i <= toIdx; i++) {
            const bar = klineData[i];
            if (!bar) continue;
            const high = Number(bar.high ?? bar.close);
            const low = Number(bar.low ?? bar.close);
            if (Number.isFinite(high) && high > maxHigh) {
                maxHigh = high;
                highestBar = bar;
            }
            if (Number.isFinite(low) && low < minLow) {
                minLow = low;
                lowestBar = bar;
            }
        }

        const chartEl = document.getElementById('chart');
        const chartWidth = chartEl ? chartEl.clientWidth : 800;
        const chartHeight = chartEl ? chartEl.clientHeight : 400;

        // 渲染可见区间最高价标签
        if (highestBar && Number.isFinite(maxHigh) && maxHigh > -Infinity) {
            const highY = candlestickSeries.priceToCoordinate(maxHigh);
            let highX = chart.timeScale().timeToCoordinate(highestBar.time);
            if (highX == null && chart.timeScale().logicalToCoordinate) {
                const idx = klineData.indexOf(highestBar);
                if (idx >= 0) highX = chart.timeScale().logicalToCoordinate(idx);
            }

            if (highX != null && highY != null && highX >= 0 && highX <= chartWidth && highY >= 0 && highY <= chartHeight) {
                const formatted = formatExtremePriceValue(maxHigh);
                if (highX < chartWidth / 2) {
                    highTag.textContent = '← ' + formatted;
                    highTag.className = 'chart-extreme-price-tag point-left high';
                    highTag.style.left = `${Math.round(highX + 6)}px`;
                } else {
                    highTag.textContent = formatted + ' →';
                    highTag.className = 'chart-extreme-price-tag point-right high';
                    highTag.style.left = `${Math.round(highX - 6)}px`;
                }
                const clampedY = Math.max(12, Math.min(chartHeight - 12, highY));
                highTag.style.top = `${Math.round(clampedY)}px`;
                highTag.style.display = 'flex';
            } else {
                highTag.style.display = 'none';
            }
        } else {
            highTag.style.display = 'none';
        }

        // 渲染可见区间最低价标签
        if (lowestBar && Number.isFinite(minLow) && minLow < Infinity) {
            const lowY = candlestickSeries.priceToCoordinate(minLow);
            let lowX = chart.timeScale().timeToCoordinate(lowestBar.time);
            if (lowX == null && chart.timeScale().logicalToCoordinate) {
                const idx = klineData.indexOf(lowestBar);
                if (idx >= 0) lowX = chart.timeScale().logicalToCoordinate(idx);
            }

            if (lowX != null && lowY != null && lowX >= 0 && lowX <= chartWidth && lowY >= 0 && lowY <= chartHeight) {
                const formatted = formatExtremePriceValue(minLow);
                if (lowX < chartWidth / 2) {
                    lowTag.textContent = '← ' + formatted;
                    lowTag.className = 'chart-extreme-price-tag point-left low';
                    lowTag.style.left = `${Math.round(lowX + 6)}px`;
                } else {
                    lowTag.textContent = formatted + ' →';
                    lowTag.className = 'chart-extreme-price-tag point-right low';
                    lowTag.style.left = `${Math.round(lowX - 6)}px`;
                }
                const clampedY = Math.max(12, Math.min(chartHeight - 12, lowY));
                lowTag.style.top = `${Math.round(clampedY)}px`;
                lowTag.style.display = 'flex';
            } else {
                lowTag.style.display = 'none';
            }
        } else {
            lowTag.style.display = 'none';
        }
    }

    return {
        formatExtremePriceValue,
        createExtremePriceTag,
        updateVisibleExtremePriceTags
    };
}));
