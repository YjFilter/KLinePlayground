/**
 * KLinePlayground - 图表主题、配色与十字光标样式模块
 */

const THEME_PALETTES = {
    light: {
        chartBg: '#ffffff',
        text: '#1f2d3d',
        grid: 'rgba(0, 0, 0, 0.06)',
        border: 'rgba(0, 0, 0, 0.12)',
        overlay: 'rgba(255, 255, 255, 0.82)',
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

function getThemePalette() {
    if (typeof isCryptoMode === 'function' && isCryptoMode()) {
        return currentCryptoTheme === 'light' ? THEME_PALETTES.crypto_light : THEME_PALETTES.crypto_dark;
    }
    return THEME_PALETTES[currentTheme] || THEME_PALETTES.light;
}

function getCandleStyleOptions(palette) {
    if (typeof isCryptoMode === 'function' && isCryptoMode()) {
        return {
            upColor: palette.positive,
            downColor: palette.negative,
            borderUpColor: palette.positive,
            borderDownColor: palette.negative,
            wickUpColor: palette.positive,
            wickDownColor: palette.negative,
            borderVisible: false,
        };
    }
    return {
        upColor: 'rgba(255, 77, 79, 0)',
        downColor: palette.negative,
        borderUpColor: palette.positive,
        borderDownColor: palette.negative,
        wickUpColor: palette.positive,
        wickDownColor: palette.negative,
        borderVisible: true,
    };
}

function getCrosshairOptions(palette) {
    const options = { mode: (typeof LightweightCharts !== 'undefined' && LightweightCharts?.CrosshairMode?.Normal != null) ? LightweightCharts.CrosshairMode.Normal : 1 };
    if ((typeof isCryptoMode === 'function' && !isCryptoMode()) || !palette.crosshair) return options;
    const line = {
        color: palette.crosshair,
        width: 1,
        style: (typeof LightweightCharts !== 'undefined' && LightweightCharts?.LineStyle?.Dashed != null) ? LightweightCharts.LineStyle.Dashed : 2,
        labelBackgroundColor: palette.crosshairLabel,
    };
    options.vertLine = { ...line };
    options.horzLine = { ...line };
    return options;
}

function isChartDarkTheme() {
    return (typeof isCryptoMode === 'function' && isCryptoMode()) ? currentCryptoTheme === 'dark' : currentTheme === 'dark';
}

function getDrawingAxisLabelColors() {
    return isChartDarkTheme()
        ? { background: '#eaecef', text: '#181a1e' }
        : { background: '#363a45', text: '#eaecef' };
}

function getDrawingDefaultColor() {
    return isChartDarkTheme() ? 'rgba(234, 236, 239, 0.92)' : '#4a5160';
}
