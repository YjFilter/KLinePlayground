/**
 * KLinePlayground - Theme Module
 * Holds the live UI theme palettes (light / dark / AiCoin crypto variants).
 * Extracted from main_enhanced.js; consumed there via `window.KLineThemeModule`.
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.KLineThemeModule = factory();
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    const PALETTES = {
        light: {
            chartBg: '#fdfefe',
            text: '#172033',
            grid: 'rgba(23, 32, 51, 0.08)',
            border: 'rgba(23, 32, 51, 0.12)',
            overlay: 'rgba(255, 255, 255, 0.84)',
            positive: '#e25555',
            negative: '#0f8a52',
            neutral: '#5d6b82',
            chip: 'linear-gradient(90deg, transparent, rgba(15, 111, 255, 0.28))',
            crosshair: '#758696',
            crosshairLabel: '#758696',
        },
        dark: {
            chartBg: '#121d31',
            text: '#ecf2ff',
            grid: 'rgba(255, 255, 255, 0.08)',
            border: 'rgba(255, 255, 255, 0.12)',
            overlay: 'rgba(9, 17, 31, 0.84)',
            positive: '#ff7a74',
            negative: '#4fd096',
            neutral: '#9daccc',
            chip: 'linear-gradient(90deg, transparent, rgba(103, 165, 255, 0.28))',
            crosshair: '#9598a1',
            crosshairLabel: '#363a45',
        },
        // AiCoin/Binance 风格加密货币配色：绿涨红跌、近黑背景、淡化网格。
        crypto_dark: {
            chartBg: '#0b0e11',
            text: '#eaecef',
            grid: 'rgba(255, 255, 255, 0.045)',
            border: 'rgba(255, 255, 255, 0.08)',
            overlay: 'rgba(11, 14, 17, 0.85)',
            positive: '#0ecb81',
            negative: '#f6465d',
            neutral: '#848e9c',
            chip: 'linear-gradient(90deg, transparent, rgba(240, 185, 11, 0.22))',
            crosshair: 'rgba(132, 142, 156, 0.6)',
            crosshairLabel: '#2b3141',
        },
        crypto_light: {
            chartBg: '#ffffff',
            text: '#1e2329',
            grid: 'rgba(23, 32, 51, 0.05)',
            border: 'rgba(23, 32, 51, 0.1)',
            overlay: 'rgba(255, 255, 255, 0.88)',
            positive: '#0ecb81',
            negative: '#f6465d',
            neutral: '#68778a',
            chip: 'linear-gradient(90deg, transparent, rgba(240, 185, 11, 0.18))',
            crosshair: 'rgba(104, 119, 138, 0.55)',
            crosshairLabel: '#474d57',
        }
    };

    function getPalette(themeName = 'dark') {
        return PALETTES[themeName] || PALETTES.light;
    }

    return {
        PALETTES,
        getPalette
    };
}));
