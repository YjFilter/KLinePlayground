// 全局变量
let currentUser = null;
let chart = null;
let volumeChart = null;
let indicatorChart = null;
let candlestickSeries = null;
let volumeSeries = null;
let maSeries = {}; // 存储移动平均线系列
let indicatorSeries = null;
let tradeMarkerSeries = null;
let activeChartTradePriceLines = [];
// AICoin 风格的价格线药丸（DOM 覆盖层，贴在价格轴左侧）
let activeTradeLinePills = [];
// 用户点 ✕ 关掉的占位止盈/止损线（按训练会话重置）
let suppressedProtectivePlaceholders = new Set();
let suppressedPlaceholderContext = null;
let isPlaying = false;
let playbackInterval = null;
let currentTraining = null;
let currentIndicatorType = 'MACD';
let currentIndicatorSeries = [];
let bollSeries = {}; // 用于存储BOLL指标线
let bollVisible = false;
let activeSubcharts = ['macd'];
try {
    const savedSubs = localStorage.getItem('kline-active-subcharts');
    if (savedSubs) {
        const parsed = JSON.parse(savedSubs);
        if (Array.isArray(parsed) && parsed.length) {
            activeSubcharts = parsed.filter(id => ['macd', 'macd2', 'kdj', 'rsi'].includes(id));
            if (!activeSubcharts.length) activeSubcharts = ['macd'];
        }
    }
} catch (e) {}
let subchartInstances = {}; // { [id]: { id, chart, primarySeries, difSeries, deaSeries, histSeries, seriesList: [], canvas, header, valuesEl } }
let lastSubchartDataMap = {};
let isSyncingRange = false;

function saveActiveSubcharts() {
    try {
        localStorage.setItem('kline-active-subcharts', JSON.stringify(activeSubcharts));
    } catch (e) {}
}
let autoSyncInterval = null;
let lastKnownBarId = null;
let lastKnownTradeCount = null;
let maPeriods = [10, 20, 40, 80, 160]; // 默认MA周期
let isShiftClicked = false;
let isShiftKeyPressed = false;
let currentTheme = localStorage.getItem('uiTheme') || 'light';
let currentCryptoTheme = localStorage.getItem('cryptoUiTheme') || 'dark';
let currentPeriod = 'daily';
let currentOrderType = 'market';
let availableDataSources = [];
let latestRenderedKlineData = [];
let latestRenderedVolumeData = [];
let trainingSetupReturnScreen = 'main';
let currentReportData = null;
let currentHistoryFilter = 'all';
let isViewOnlyMode = false;
let skipTradeReasonPrompt = false;
let pendingTradeReasonAction = null;
let barReplayState = (typeof window !== 'undefined' && window.KLineBarReplayModule && typeof window.KLineBarReplayModule.createBarReplayState === 'function')
    ? window.KLineBarReplayModule.createBarReplayState()
    : {
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
// 图表窗口/周期格式化等纯逻辑已抽取到 modules/chart_window_core.js。
const {
    createEmptyChartWindowState,
    formatIntradayPeriodBadge,
    extractIntradaySnapshot,
    intradayBarToTimestamp,
    buildIntradayKlineChartData,
    normalizeChartTime,
    normalizeChartCandle,
    normalizeChartVolume,
    normalizeChartMarker,
    normalizeTradeMarkers,
    mergeTimedItems,
    mergeChartWindow,
    parseChartWindowTimestamp,
    formatChartWindowTimestamp,
    shiftChartWindowYear,
    earlierChartWindowTimestamp,
    laterChartWindowTimestamp,
} = window.KLineChartWindowCore || {};
const {
    clearTradingHoursBands,
    drawTradingHoursBands,
    getTradingHours,
    isIntradayCryptoPeriod,
    setTradingHours,
} = window.KLineTradingHoursModule || {};
const {
    normalizeAshareAccount: normalizeAshareAccountFields,
    computeAvailableShares: computeAshareAvailShares,
    matchLimitOrders: matchAshareLimitOrders,
    validateLimitBuy: validateAshareLimitBuy,
    validateLimitSell: validateAshareLimitSell,
    computeAshareTradeFees: computeAshareTradeFees,
} = window.KLineAshareTradingModule || {};
const {
    normalizeAlert: normalizePriceAlert,
    normalizeAlertList: normalizePriceAlertList,
    normalizeAlertPrice: normalizePriceAlertPrice,
    deriveAlertDirection: derivePriceAlertDirection,
    evaluateAlertCrossing: evaluatePriceAlertCrossing,
    findTriggeredAlerts: findTriggeredPriceAlerts,
    formatAlertLabel: formatPriceAlertLabel,
    formatAlertPrice: formatPriceAlertPrice,
    formatAlertTriggeredAt: formatPriceAlertTriggeredAt,
    buildAlertId: buildPriceAlertId,
    alertStorageKey: priceAlertStorageKey,
    selectPersistableAlerts: selectPersistablePriceAlerts,
} = window.KLinePriceAlertsModule || {};
let chartWindowState = createEmptyChartWindowState();
let chartWindowRequestChain = Promise.resolve();
let chartWindowRequestGeneration = 0;
let chartWindowLoadingDirection = null;
let chartPanelResizeObserver = null;
let chartPanelResizeFrame = null;
let chartPanelResizing = false;
let activeChartPanelSplitter = null;
let chartPanelRatios = null;
// chartPanelRatios 当前对应的存储键（模式切换后键不同需重读）
let chartPanelRatiosKey = null;
let drawingController = null;
let drawingUiAbortController = null;
let selectedTrainingMarketType = 'a_share';
let selectedCryptoInstrument = null;
let cryptoInstrumentSearchTimer = null;
let periodSwitchAbortController = null;
let periodSwitchGeneration = 0;
let periodSwitchFeedbackTimer = null;
let cryptoOrderConstraints = null;
let currentCryptoSummary = null;
let cryptoOrderSubmitting = false;
let cryptoNextInFlight = false;
let cryptoFeeSubmitting = false;
let cryptoHistoryPrepareJobId = null;
let cryptoHistoryPrepareAbortController = null;
let cryptoHistoryPrepareRetryConfig = null;
let cryptoEarlierSegmentLoading = false;
let cryptoEarlierSegmentGeneration = 0;
const PERIOD_LOADING_DELAY_MS = 150;
const CHART_PANEL_STORAGE_KEY = 'kline-chart-panel-heights-v2';
// A股实时看盘与回放训练的面板高度比例分键存储，避免两种模式互相污染面板高度
// （历史 bug：在看盘模式拖拽/重排后回到币圈训练，MACD 副图高度被压到只剩图例行）。
const CHART_PANEL_STORAGE_KEY_ASHARE = 'kline-chart-panel-heights-v2-ashare';
const CHART_PANEL_DEFAULT_RATIOS = { chart: 0.72, 'volume-chart': 0.11, 'indicator-chart': 0.17 };
const CHART_PANEL_MIN_HEIGHTS = { chart: 160, 'volume-chart': 32, 'indicator-chart': 52 };

// 币圈周期快照缓存已抽取到 modules/period_snapshot_cache.js（LRU + 训练会话隔离）。
const {
    buildCryptoPeriodSnapshotCacheKey,
    clearCryptoPeriodSnapshotCache,
    clearCryptoPeriodSnapshotCacheForPeriod,
    getCryptoPeriodSnapshotCache,
    getCryptoReplayCacheTime,
    setCryptoPeriodSnapshotCache,
    syncCryptoPeriodSnapshotCacheTraining,
} = window.KLinePeriodSnapshotCache || {};

function resetChartWindowState() {
    clearCryptoPeriodSnapshotCache();
    cryptoEarlierSegmentGeneration += 1;
    cryptoEarlierSegmentLoading = false;
    chartWindowRequestGeneration += 1;
    chartWindowRequestChain = Promise.resolve();
    chartWindowLoadingDirection = null;
    chartWindowState = createEmptyChartWindowState();
    updateChartWindowControls();
}

// === Intraday 多周期回放 (TASK-013) ===
// data_mode 标识: 来自 /api/training/start 响应的 currentTraining.data_mode。
// 仅当 data_mode === INTRADAY_DATA_MODE 时走新的 intraday 路径，
// 其余情况一律沿用原 legacy_daily JavaScript 路径。
const INTRADAY_DATA_MODE = 'intraday_30m';
const INTRADAY_PERIODS = ['30m', '4h_session', 'daily', 'weekly'];
const CRYPTO_MARKET_TYPE = 'crypto_perpetual';
const CRYPTO_DATA_MODE = 'crypto_5m';
const CRYPTO_PERIODS = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '3h', '4h', '6h', '8h', '12h', 'daily', '2d', '3d', 'weekly'];

function isCryptoMode() {
    return !!(currentTraining && (
        currentTraining.market_type === CRYPTO_MARKET_TYPE
        || currentTraining.data_mode === CRYPTO_DATA_MODE
    ));
}

function isIntradayMode() {
    return !!(currentTraining && (
        currentTraining.data_mode === INTRADAY_DATA_MODE
        || currentTraining.data_mode === CRYPTO_DATA_MODE
    ));
}

function supportedReplayPeriods() {
    return isAshareLiveMode || isCryptoMode() || selectedTrainingMarketType === CRYPTO_MARKET_TYPE
        ? CRYPTO_PERIODS
        : INTRADAY_PERIODS;
}

// 从 #kline-period 下拉读取用户选择的周期。
// 始终返回 INTRADAY_PERIODS 之一，默认 'daily'。
function getSelectedKlinePeriod() {
    const select = document.getElementById('kline-period');
    if (!select) return 'daily';
    const value = select.value;
    return supportedReplayPeriods().indexOf(value) >= 0 ? value : 'daily';
}


// 把市场墙上时间转换为 lightweight-charts 的 UTCTimestamp。


// intraday snapshot 没有独立的 volume_data，从每根 K 线的 volume 字段构造。
function buildIntradayVolumeData(klineData) {
    if (!Array.isArray(klineData)) return [];
    const palette = getThemePalette();
    return klineData.map(function (bar) {
        const isUp = Number(bar.close) >= Number(bar.open);
        return {
            time: intradayBarToTimestamp(bar),
            value: Number(bar.volume) || 0,
            color: isUp ? palette.positive : palette.negative,
        };
    });
}

// 根据 snapshot.current_bar_complete 切换 K 线状态样式与文案。
function updateIntradayReplayStatus(snapshot) {
    const replayTimeEl = document.getElementById('current-replay-time');
    const boundaryEl = document.getElementById('next-boundary-time');
    const statusEl = document.getElementById('current-bar-status');

    if (!snapshot) return;
    if (replayTimeEl) replayTimeEl.textContent = snapshot.current_time || '--';
    if (boundaryEl) boundaryEl.textContent = snapshot.next_boundary || '--';

    if (statusEl) {
        const complete = !!snapshot.current_bar_complete;
        statusEl.classList.toggle('incomplete-candle', !complete);
        statusEl.classList.toggle('bar-status-incomplete', !complete);
        statusEl.classList.toggle('bar-status-complete', complete);
        statusEl.textContent = complete ? '已收盘' : '未收盘';
    }
}

// 把 active_period 同步到 currentPeriod 和顶部徽章。
function syncIntradayActivePeriod(period) {
    const next = supportedReplayPeriods().indexOf(period) >= 0 ? period : 'daily';
    currentPeriod = next;
    updatePeriodBadge(next);
}

// 渲染 intraday snapshot 到主图、成交量图、回放状态、当前价格/进度信息。
// 不会调用任何 legacy-only 接口（chip_distribution / adjustment / indicators / full_data）。
function applyIntradaySnapshot(snapshot, options) {
    const opts = options || {};
    if (!snapshot) {
        throw new Error('intraday snapshot 为空');
    }
    const klineData = snapshot.kline_data || [];
    if (klineData.length === 0) {
        throw new Error('intraday 训练数据为空');
    }

    const chartData = buildIntradayKlineChartData(klineData);
    const volumeData = buildIntradayVolumeData(klineData);

    if (currentTraining) {
        currentTraining.latestProgress = null;
        currentTraining.current_time = snapshot.current_time || currentTraining.current_time;
        currentTraining.next_boundary = snapshot.next_boundary || currentTraining.next_boundary;
    }

    if (typeof barReplayState !== 'undefined' && barReplayState && barReplayState.active) {
        handleBarReplayPeriodSwitch(chartData, volumeData, currentPeriod || currentTraining?.period);
        updateTradeMarkers(currentTraining?.tradeMarkers || chartWindowState.trade_markers || []);
        return;
    }

    candlestickSeries.setData(chartData);
    volumeSeries.setData(volumeData);
    replaceRenderedKlineData(chartData);
    loadTechnicalIndicator(currentIndicatorType);

    // 加密模式用已揭示K线本地计算 MA（replaceRenderedKlineData 中刷新）；其余 intraday 保持清空
    if (!(isCryptoMode() && maVisible)) {
        maPeriods.forEach(function (p) {
            if (maSeries[p]) maSeries[p].setData([]);
        });
    }
    updateTradeMarkers(currentTraining?.tradeMarkers || chartWindowState.trade_markers || []);

    const lastBar = klineData[klineData.length - 1];
    const lastChartBar = chartData[chartData.length - 1];
    if (lastChartBar) {
        // intraday 没有 progress/bar_id 概念；用最后一条聚合 K 线更新基础价格/日期信息
        updateCurrentInfo({
            time: lastChartBar.time,
            open: Number(lastBar.open),
            high: Number(lastBar.high),
            low: Number(lastBar.low),
            close: Number(lastBar.close),
            volume: Number(lastBar.volume) || 0,
        }, null);
    }

    const instrumentLabel = snapshot.symbol || currentTraining?.symbol || currentTraining?.stock_code;
    if (instrumentLabel) document.getElementById('stock-name').textContent = instrumentLabel;
    updateIntradayReplayStatus(snapshot);
    syncIntradayActivePeriod(snapshot.active_period);

    if (opts.fitContent && chart) {
        chart.timeScale().fitContent();
    }
}

// 主题色盘表已抽取到 modules/theme.js（由 applyChartTheme 等 AICoin 主题逻辑消费）。
const THEME_PALETTES = (window.KLineThemeModule || {}).PALETTES;

function getThemePalette() {
    if (isAshareLiveMode) {
        const darkPal = (THEME_PALETTES && THEME_PALETTES.ashare_dark) || {
            ...(THEME_PALETTES && THEME_PALETTES.crypto_dark ? THEME_PALETTES.crypto_dark : {}),
            positive: '#f6465d',
            negative: '#0ecb81',
        };
        const lightPal = (THEME_PALETTES && THEME_PALETTES.ashare_light) || {
            ...(THEME_PALETTES && THEME_PALETTES.crypto_light ? THEME_PALETTES.crypto_light : {}),
            positive: '#f6465d',
            negative: '#0ecb81',
        };
        return (currentCryptoTheme || 'dark') === 'light' ? lightPal : darkPal;
    }
    if (isCryptoMode()) {
        return currentCryptoTheme === 'light' ? THEME_PALETTES.crypto_light : THEME_PALETTES.crypto_dark;
    }
    return THEME_PALETTES[currentTheme] || THEME_PALETTES.light;
}

// AiCoin 风格加密货币与 A 股实时模式使用实心涨跌色；历史股票复盘模式保留原有空心阳线风格。
function getCandleStyleOptions(palette) {
    if (isCryptoMode() || isAshareLiveMode) {
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

// 加密货币与 A 股实时模式使用 AiCoin 风格的虚线十字光标与深色标签。
function getCrosshairOptions(palette) {
    const options = { mode: LightweightCharts.CrosshairMode.Normal };
    if ((!isCryptoMode() && !isAshareLiveMode) || !palette.crosshair) return options;
    const line = {
        color: palette.crosshair,
        width: 1,
        style: LightweightCharts.LineStyle.Dashed,
        labelBackgroundColor: palette.crosshairLabel,
    };
    options.vertLine = { ...line };
    options.horzLine = { ...line };
    return options;
}

// AiCoin 风格：选中/悬停图形时，右侧价格轴用高亮标签显示锚点价格。
// 深色主题用浅底深字（与截图一致），浅色主题用深底浅字。
function isChartDarkTheme() {
    if (isAshareLiveMode) return (currentCryptoTheme || 'dark') === 'dark';
    return isCryptoMode() ? currentCryptoTheme === 'dark' : currentTheme === 'dark';
}

function getDrawingAxisLabelColors() {
    return isChartDarkTheme()
        ? { background: '#eaecef', text: '#181a1e' }
        : { background: '#363a45', text: '#eaecef' };
}

// AiCoin 风格：画线默认颜色深色主题近白、浅色主题深灰，替代之前的固定蓝色。
function getDrawingDefaultColor() {
    return isChartDarkTheme() ? 'rgba(234, 236, 239, 0.92)' : '#4a5160';
}

function updateThemeButton() {
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
        themeBtn.textContent = currentTheme === 'dark' ? '浅色主题' : '深色主题';
    }
    const themeSelect = document.getElementById('theme-select');
    if (themeSelect) {
        themeSelect.value = currentTheme;
    }
    const cryptoThemeBtn = document.getElementById('crypto-theme-toggle-btn');
    if (cryptoThemeBtn) {
        const isDark = currentCryptoTheme === 'dark';
        const actionLabel = isDark ? '切换为浅色主题' : '切换为暗色主题';
        cryptoThemeBtn.textContent = isDark ? '☀' : '☾';
        cryptoThemeBtn.title = actionLabel;
        cryptoThemeBtn.setAttribute('aria-label', actionLabel);
        cryptoThemeBtn.setAttribute('aria-pressed', String(!isDark));
    }
}

function applyCryptoTheme(theme, persist = true, syncUser = false) {
    currentCryptoTheme = theme === 'light' ? 'light' : 'dark';
    const mainApp = document.getElementById('main-app');
    if (mainApp) {
        mainApp.dataset.cryptoTheme = currentCryptoTheme;
    }
    if (persist) {
        localStorage.setItem('cryptoUiTheme', currentCryptoTheme);
    }
    if (syncUser) {
        persistUserSettings({ crypto_theme: currentCryptoTheme });
    }
    updateThemeButton();
    updatePriceMode();
    applyChartTheme();
}

function toggleCryptoTheme() {
    applyCryptoTheme(currentCryptoTheme === 'dark' ? 'light' : 'dark', true, true);
}

function updatePeriodBadge(period) {
    currentPeriod = period || 'daily';
    const badge = document.getElementById('current-period');
    if (badge) {
        if (typeof isAshareLiveMode !== 'undefined' && isAshareLiveMode) {
            const map = {
                'daily': '日K', '1d': '日K', '1D': '日K',
                'weekly': '周K', '1w': '周K', '1W': '周K',
                'monthly': '月K', '1M': '月K', 'month': '月K',
                '1m': '1分', '5m': '5分', '15m': '15分', '30m': '30分',
                '60m': '60分', '1h': '60分',
                '120m': '120分', '2h': '120分',
                '240m': '240分', '4h': '240分', '4h_session': '240分'
            };
            badge.textContent = map[currentPeriod] || (typeof formatIntradayPeriodBadge === 'function' ? formatIntradayPeriodBadge(currentPeriod) : currentPeriod);
        } else {
            badge.textContent = typeof formatIntradayPeriodBadge === 'function' ? formatIntradayPeriodBadge(currentPeriod) : currentPeriod;
        }
    }
    document.querySelectorAll('.view-period-btn').forEach((button) => {
        const btnP = (typeof isAshareLiveMode !== 'undefined' && isAshareLiveMode && typeof normalizeAshareLivePeriod === 'function')
            ? normalizeAshareLivePeriod(button.dataset.period)
            : button.dataset.period;
        const curP = (typeof isAshareLiveMode !== 'undefined' && isAshareLiveMode && typeof normalizeAshareLivePeriod === 'function')
            ? normalizeAshareLivePeriod(currentPeriod)
            : currentPeriod;
        button.classList.toggle('active', btnP === curP || button.dataset.period === currentPeriod);
    });
    scheduleTradingHoursBandsUpdate();
}

async function persistUserSettings(partialSettings) {
    if (!currentUser) return;
    try {
        await fetch(`${API_BASE}/users/${currentUser}/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(partialSettings)
        });
    } catch (error) {
        console.error('保存用户设置失败:', error);
    }
}

function applyTheme(theme, persist = true, syncUser = false) {
    currentTheme = theme === 'dark' ? 'dark' : 'light';
    document.body.dataset.theme = currentTheme;
    if (persist) {
        localStorage.setItem('uiTheme', currentTheme);
    }
    if (syncUser) {
        persistUserSettings({ theme: currentTheme });
    }
    updateThemeButton();
    updatePriceMode();
    applyChartTheme();
}

function getViewPeriodQuery() {
    return `view_period=${currentPeriod}`;
}

function showLoading(title = '正在加载', detail = '') {
    const overlay = document.getElementById('loading-overlay');
    if (!overlay) return;
    const titleEl = document.getElementById('loading-title');
    const detailEl = document.getElementById('loading-detail');
    if (titleEl) titleEl.textContent = title;
    if (detailEl) detailEl.textContent = detail || '请稍候...';
    overlay.classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading-overlay')?.classList.add('hidden');
}

function beginPeriodSwitchFeedback(period) {
    if (periodSwitchFeedbackTimer) clearTimeout(periodSwitchFeedbackTimer);
    periodSwitchFeedbackTimer = setTimeout(() => {
        document.querySelectorAll('.view-period-btn').forEach((button) => {
            button.classList.toggle('is-loading', button.dataset.period === period);
        });
        setChartWindowStatus('正在切换 ' + formatIntradayPeriodBadge(period) + ' 视图...', 'loading');
    }, PERIOD_LOADING_DELAY_MS);
}

function endPeriodSwitchFeedback() {
    if (periodSwitchFeedbackTimer) clearTimeout(periodSwitchFeedbackTimer);
    periodSwitchFeedbackTimer = null;
    document.querySelectorAll('.view-period-btn').forEach((button) => button.classList.remove('is-loading'));
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function applyChartTheme() {
    scheduleTradingHoursBandsUpdate();
    const palette = getThemePalette();
    const infoDisplay = document.getElementById('chart-info-display');
    if (infoDisplay) {
        infoDisplay.style.background = palette.overlay;
        infoDisplay.style.color = palette.text;
        infoDisplay.style.borderColor = palette.border;
    }
    const indicatorInfoDisplay = document.getElementById('indicator-info-display');
    if (indicatorInfoDisplay) {
        indicatorInfoDisplay.style.background = palette.overlay;
        indicatorInfoDisplay.style.color = palette.text;
        indicatorInfoDisplay.style.borderColor = palette.border;
    }

    document.querySelectorAll('.chip-bar').forEach((bar) => {
        bar.style.background = palette.chip;
    });

    if (!chart) return;

    chart.applyOptions({
        layout: {
            background: { type: 'solid', color: palette.chartBg },
            textColor: palette.text,
        },
        grid: {
            vertLines: { color: palette.grid },
            horzLines: { color: palette.grid },
        },
        rightPriceScale: { borderColor: palette.border },
        timeScale: { borderColor: palette.border },
    });

    if (volumeChart) {
        volumeChart.applyOptions({
            layout: {
                background: { type: 'solid', color: palette.chartBg },
                textColor: palette.text,
            },
            grid: {
                vertLines: { color: palette.grid },
                horzLines: { color: palette.grid },
            },
            rightPriceScale: { borderColor: palette.border },
            timeScale: { borderColor: palette.border },
        });
    }

    if (indicatorChart) {
        indicatorChart.applyOptions({
            layout: {
                background: { type: 'solid', color: palette.chartBg },
                textColor: palette.text,
            },
            grid: {
                vertLines: { color: palette.grid },
                horzLines: { color: palette.grid },
            },
            rightPriceScale: { borderColor: palette.border },
            timeScale: { borderColor: palette.border },
        });
    }

    if (candlestickSeries) {
        candlestickSeries.applyOptions({
            ...getCandleStyleOptions(palette),
            lastValueVisible: isCryptoMode() || isAshareLiveMode,
        });
        applyLastPriceTagColor();
    }

    // MACD 自动色（AiCoin 风格）跟随主题切换重绘
    if (currentIndicatorType === 'MACD' && indicatorPanelVisible && macdColorsAreAuto()
        && latestRenderedKlineData && latestRenderedKlineData.length > 0) {
        loadTechnicalIndicator('MACD');
    }
}

// 加密货币与 A 股实时模式下为价格轴上的当前价标签块着色（AiCoin 风格）。
function applyLastPriceTagColor() {
    if (!candlestickSeries || (!isCryptoMode() && !isAshareLiveMode)) return;
    const bars = latestRenderedKlineData;
    if (!bars || bars.length === 0) return;
    const palette = getThemePalette();
    const last = bars[bars.length - 1];
    const prev = bars.length > 1 ? bars[bars.length - 2] : null;
    const isUp = prev
        ? Number(last.close) >= Number(prev.close)
        : Number(last.close) >= Number(last.open);
    candlestickSeries.applyOptions({
        priceLineColor: isUp ? palette.positive : palette.negative,
    });
}

// AiCoin 风格主图左上角图例：加密货币模式下常驻显示最新一根K线的
// OHLC 与 MA/BOLL 彩色数值（跟随当前 bar，十字线移动时改由十字线数据驱动）。
function showLatestChartInfo() {
    const infoEl = document.getElementById('chart-info-display');
    if (!infoEl) return;
    if (!isCryptoMode() && !isAshareLiveMode) return;
    const bars = latestRenderedKlineData;
    if (!bars || bars.length === 0) {
        infoEl.style.display = 'none';
        return;
    }
    const palette = getThemePalette();
    const last = bars[bars.length - 1];
    const prev = bars.length > 1 ? bars[bars.length - 2] : null;
    const fmt = (value) => Number(value).toFixed(2);
    const colorOf = (value, base) => {
        if (value > base) return palette.positive;
        if (value < base) return palette.negative;
        return palette.neutral;
    };
    const base = prev ? Number(prev.close) : Number(last.open);
    let html = '<div>'
        + '<strong>开:</strong> <span style="color: ' + colorOf(Number(last.open), base) + ';">' + fmt(last.open) + '</span> '
        + '<strong>高:</strong> <span style="color: ' + colorOf(Number(last.high), base) + ';">' + fmt(last.high) + '</span> '
        + '<strong>低:</strong> <span style="color: ' + colorOf(Number(last.low), base) + ';">' + fmt(last.low) + '</span> '
        + '<strong>收:</strong> <span style="color: ' + colorOf(Number(last.close), Number(last.open)) + ';">' + fmt(last.close) + '</span>'
        + '</div>';

    const maParts = [];
    maPeriods.forEach((p) => {
        const series = maSeries[p];
        if (!series || !isMaLineVisible(p)) return;
        let lastValue = null;
        try {
            const seriesData = typeof series.data === 'function' ? series.data() : [];
            if (seriesData.length > 0) lastValue = seriesData[seriesData.length - 1].value;
        } catch (error) {
            lastValue = null;
        }
        if (lastValue === null || lastValue === undefined) return;
        maParts.push('<span style="color: ' + series.options().color + ';">MA' + p + ':' + fmt(lastValue) + '</span>');
    });
    if (maParts.length > 0) html += '<div>' + maParts.join(' ') + '</div>';

    if (currentIndicatorType === 'BOLL' && bollSeries.upper && bollSeries.middle && bollSeries.lower) {
        const bollParts = [];
        [['UP', bollSeries.upper], ['MID', bollSeries.middle], ['LOW', bollSeries.lower]].forEach(([label, series]) => {
            let lastValue = null;
            try {
                const seriesData = typeof series.data === 'function' ? series.data() : [];
                if (seriesData.length > 0) lastValue = seriesData[seriesData.length - 1].value;
            } catch (error) {
                lastValue = null;
            }
            if (lastValue === null || lastValue === undefined) return;
            bollParts.push('<span style="color: ' + series.options().color + ';">' + label + ':' + fmt(lastValue) + '</span>');
        });
        if (bollParts.length > 0) html += '<div>' + bollParts.join(' ') + '</div>';
    }

    infoEl.innerHTML = html;
    infoEl.style.display = 'block';
}

function updatePriceMode() {
    const isModeOpen = isShiftClicked || isShiftKeyPressed;
    const shiftBtn = document.getElementById('shift-toggle-btn');
    const buyBtn = document.getElementById('buy-btn');
    const sellBtn = document.getElementById('sell-btn');
    const palette = getThemePalette();
    
    if (!shiftBtn || !buyBtn || !sellBtn) return;
    
    if (isModeOpen) {
        shiftBtn.style.backgroundColor = palette.positive;
        shiftBtn.style.color = 'white';
        shiftBtn.style.borderColor = 'transparent';
        buyBtn.textContent = '买(开盘)';
        sellBtn.textContent = '卖(开盘)';
    } else {
        shiftBtn.style.backgroundColor = '';
        shiftBtn.style.color = '';
        shiftBtn.style.borderColor = '';
        buyBtn.textContent = '买(收盘)';
        sellBtn.textContent = '卖(收盘)';
    }
}
const maColors = ['#1d2140', '#2816cf', '#ff8103', '#e02424', '#8b5cf6', '#059669']; // 6个预设颜色

// --- 筹码分布开始 ---
let chipDistributionData = null;

function scheduleChipDistributionRender() {
    if (typeof window === 'undefined') {
        renderChipDistribution();
        return;
    }

    window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
            renderChipDistribution();
        });
    });
}

function getChipPriceCoordinate(price, containerHeight) {
    if (!Number.isFinite(price) || !containerHeight) {
        return null;
    }

    const directCoordinate = candlestickSeries?.priceToCoordinate?.(price);
    if (Number.isFinite(directCoordinate)) {
        return directCoordinate;
    }

    if (!Array.isArray(latestRenderedKlineData) || latestRenderedKlineData.length === 0) {
        return null;
    }

    let minPrice = Number.POSITIVE_INFINITY;
    let maxPrice = Number.NEGATIVE_INFINITY;
    latestRenderedKlineData.forEach((bar) => {
        if (Number.isFinite(bar?.low)) minPrice = Math.min(minPrice, bar.low);
        if (Number.isFinite(bar?.high)) maxPrice = Math.max(maxPrice, bar.high);
    });

    if (!Number.isFinite(minPrice) || !Number.isFinite(maxPrice)) {
        return null;
    }

    if (maxPrice === minPrice) {
        return containerHeight / 2;
    }

    const clampedPrice = Math.min(maxPrice, Math.max(minPrice, price));
    return ((maxPrice - clampedPrice) / (maxPrice - minPrice)) * containerHeight;
}

async function updateChipDistribution() {
    const toggleCb = document.getElementById('toggle-chip-distribution');
    const profitRatioContainer = document.getElementById('profit-ratio-container');

    if (!toggleCb || !toggleCb.checked) {
        const container = getOrCreateVolumeProfileContainer();
        if (container) container.style.display = 'none';
        if (profitRatioContainer) {
            profitRatioContainer.classList.add('hidden');
            profitRatioContainer.style.display = 'none';
        }
        return;
    }

    if (profitRatioContainer) {
        profitRatioContainer.classList.remove('hidden');
        profitRatioContainer.style.display = 'flex';
    }

    if (!currentTraining || !currentTraining.id) return;

    // === intraday_30m 分支: 筹码分布接口由 legacy kline_processor 支持，
    // intraday 模式不具备该后端依赖，因此隐藏面板并直接返回 ===
    if (isIntradayMode()) {
        const container = getOrCreateVolumeProfileContainer();
        if (container) container.style.display = 'none';
        if (profitRatioContainer) {
            profitRatioContainer.classList.add('hidden');
            profitRatioContainer.style.display = 'none';
        }
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/chip_distribution?bins=80&${getViewPeriodQuery()}`);
        if (response.ok) {
            chipDistributionData = await response.json();
            scheduleChipDistributionRender();
        } else {
            chipDistributionData = null;
            const container = getOrCreateVolumeProfileContainer();
            if (container) container.innerHTML = '';
        }
    } catch (e) {
        console.error("Failed to load chip distribution", e);
    }
}

function renderChipDistribution() {
    try {
        const toggleCb = document.getElementById('toggle-chip-distribution');
        if (!toggleCb || !toggleCb.checked) {
            return;
        }
        const container = getOrCreateVolumeProfileContainer();
        container.style.display = 'block';
        
        if (!chipDistributionData || !chipDistributionData.data || !candlestickSeries || !chart) {
            container.innerHTML = '';
            return;
        }

        const data = chipDistributionData.data;
        if (data.length === 0) {
            container.innerHTML = '';
            return;
        }

        const currentData = latestRenderedKlineData;
        let currentPrice = null;
        if (currentData.length > 0) {
            currentPrice = currentData[currentData.length - 1].close;
            let profitVolume = 0;
            let totalVolume = 0;
            data.forEach(bin => {
                totalVolume += bin.volume;
                if (bin.price <= currentPrice) profitVolume += bin.volume;
            });
            const profitRatioEl = document.getElementById('profit-ratio');
            if (profitRatioEl) {
                const palette = getThemePalette();
                const profitRatio = totalVolume > 0 ? ((profitVolume / totalVolume) * 100).toFixed(2) : 0;
                profitRatioEl.textContent = `${profitRatio}%`;
                profitRatioEl.style.color = profitRatio > 50 ? palette.positive : palette.negative;
            }
        }

        const maxVolume = Math.max(...data.map(d => d.volume), 0);
        if (!maxVolume) {
            container.innerHTML = '';
            return;
        }

        const containerHeight = container.clientHeight || document.getElementById('chart')?.clientHeight || 0;
        const fragment = document.createDocumentFragment();
        let renderedCount = 0;

        if (Number.isFinite(currentPrice)) {
            const currentLineY = getChipPriceCoordinate(currentPrice, containerHeight);
            if (currentLineY !== null) {
                const currentLine = document.createElement('div');
                currentLine.className = 'chip-current-line';
                currentLine.style.top = `${currentLineY}px`;
                fragment.appendChild(currentLine);
            }
        }
        
        data.forEach((bin, i) => {
            const y = getChipPriceCoordinate(bin.price, containerHeight);
            if (y === null || y < -50 || y > containerHeight + 50) {
                return; 
            }
            
            let nextY = null;
            if (i < data.length - 1) {
                nextY = getChipPriceCoordinate(data[i + 1].price, containerHeight);
            } else if (i > 0) {
                const prevY = getChipPriceCoordinate(data[i - 1].price, containerHeight);
                if (y !== null && prevY !== null) {
                    nextY = y - (prevY - y);
                }
            }
            
            let barHeight = 2;
            if (y !== null && nextY !== null) {
                barHeight = Math.abs(y - nextY);
            }
            if (barHeight < 1) barHeight = 1;
            
            const widthPercent = (bin.volume / maxVolume) * 100;
            
            const barDiv = document.createElement('div');
            const isProfitChip = Number.isFinite(currentPrice) ? bin.price <= currentPrice : true;
            barDiv.className = `chip-bar ${isProfitChip ? 'chip-profit' : 'chip-loss'}`;
            barDiv.style.top = `${y - barHeight/2}px`;
            barDiv.style.width = `${Math.max(widthPercent, 2)}%`;
            barDiv.style.height = `${barHeight * 0.9}px`;
            
            fragment.appendChild(barDiv);
            renderedCount += 1;
        });
        
        container.innerHTML = '';
        container.appendChild(fragment);
        container.dataset.renderedCount = String(renderedCount);
    } catch (error) {
        console.error('渲染筹码分布失败:', error);
    }
}

function getOrCreateVolumeProfileContainer() {
    let container = document.getElementById('volume-profile-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'volume-profile-container';
        const chartDiv = document.getElementById('chart');
        if (chartDiv) {
             if (window.getComputedStyle(chartDiv).position === 'static') {
                 chartDiv.style.position = 'relative';
             }
             chartDiv.appendChild(container);
        }
    }
    return container;
}

function ensureBackToReportButton() {
    let backBtn = document.getElementById('back-to-report-btn');
    if (backBtn) {
        return backBtn;
    }

    const controlsSection = document.querySelector('.training-controls');
    if (!controlsSection) {
        return null;
    }

    backBtn = document.createElement('button');
    backBtn.id = 'back-to-report-btn';
    backBtn.className = 'btn btn-primary hidden';
    backBtn.style.width = '100%';
    backBtn.style.marginTop = '10px';
    backBtn.textContent = '返回复盘报告';
    backBtn.onclick = () => {
        setTrainingViewOnlyMode(false, { showBackToReport: false });
        document.getElementById('training-interface').classList.add('hidden');
    const reportInterface = document.getElementById('report-interface');
    reportInterface.classList.remove('hidden');
    reportInterface.scrollTop = 0;
        toggleToolbarForTraining(false);
    };
    controlsSection.appendChild(backBtn);
    return backBtn;
}

function setTrainingViewOnlyMode(viewOnly, options = {}) {
    const { showBackToReport = false } = options;
    const disabled = !!viewOnly;
    const opacity = disabled ? '0.5' : '1';
    const cursor = disabled ? 'not-allowed' : 'pointer';

    document.querySelectorAll('.trade-controls button').forEach((btn) => {
        btn.disabled = disabled;
        btn.style.opacity = opacity;
        btn.style.cursor = cursor;
    });

    const tradeQuantityInput = document.getElementById('trade-quantity');
    if (tradeQuantityInput) {
        tradeQuantityInput.disabled = disabled;
    }

    const playbackSpeedSelect = document.getElementById('playback-speed');
    if (playbackSpeedSelect) {
        playbackSpeedSelect.disabled = disabled;
        playbackSpeedSelect.style.opacity = opacity;
    }

    document.querySelectorAll('input[name="adjustment"]').forEach((input) => {
        input.disabled = disabled;
    });
    const indicatorSelect = document.getElementById('indicator-select');
    if (indicatorSelect) {
        indicatorSelect.disabled = disabled;
        indicatorSelect.style.opacity = opacity;
    }
    const indicatorHeaderPicker = document.getElementById('indicator-header-picker');
    if (indicatorHeaderPicker) {
        indicatorHeaderPicker.disabled = disabled;
        indicatorHeaderPicker.style.opacity = opacity;
        indicatorHeaderPicker.style.cursor = cursor;
    }

    ['end-training-btn', 'reset-training-btn', 'next-bar-btn', 'play-pause-btn'].forEach((id) => {
        const element = document.getElementById(id);
        if (!element) return;
        element.disabled = disabled;
        element.style.opacity = opacity;
        element.style.cursor = cursor;
    });

    const backBtn = ensureBackToReportButton();
    if (backBtn) {
        backBtn.classList.toggle('hidden', !showBackToReport);
    }

    isViewOnlyMode = disabled;
}
// --- 筹码分布结束 ---

// API 基础URL - 改为相对路径适配动态端口
const API_BASE = '/api';

// 多端状态同步管理（支持桌面端与 Web 端双向实时一致）
let _statePushTimer = null;
let _pendingStatePayload = {};

function pushStateToBackend(payload) {
    if (!payload || typeof payload !== 'object') return;
    Object.assign(_pendingStatePayload, payload);

    if (_statePushTimer) clearTimeout(_statePushTimer);
    _statePushTimer = setTimeout(async () => {
        const toSend = { ..._pendingStatePayload };
        _pendingStatePayload = {};
        try {
            await fetch(`${API_BASE}/state/sync`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(toSend)
            });
        } catch (e) {
            // 静默失败，不阻塞用户本地体验
        }
    }, 200);
}

async function syncMultiPlatformState() {
    try {
        const resp = await fetch(`${API_BASE}/state/sync`);
        if (!resp.ok) return;
        const state = await resp.json();
        if (!state || state.status !== 'ok') return;

        // 1. 同步当前活动用户
        const localUser = localStorage.getItem('currentUser');
        if (state.active_user && !localUser) {
            // 本地未设用户（例如新启动的桌面端），直接继承全局活动用户
            localStorage.setItem('currentUser', state.active_user);
        } else if (localUser && !state.active_user) {
            // 本地有用户但全局未设置，将本地用户推向全局
            pushStateToBackend({ active_user: localUser });
        } else if (state.active_user && localUser && state.active_user !== localUser) {
            // 若全局有最新活动用户，与全局保持一致
            localStorage.setItem('currentUser', state.active_user);
        }

        // 2. 同步 A股 模拟账户持仓与资金
        if (state.ashare_account && typeof state.ashare_account === 'object') {
            const localAccRaw = localStorage.getItem('ashare_live_account_v1');
            let localAcc = null;
            if (localAccRaw) {
                try { localAcc = JSON.parse(localAccRaw); } catch (e) {}
            }
            const localHasPositions = !!(localAcc && localAcc.positions && Object.keys(localAcc.positions).length > 0);
            const backendHasPositions = !!(state.ashare_account.positions && Object.keys(state.ashare_account.positions).length > 0);

            if (!localAcc || (!localHasPositions && backendHasPositions) || (localAcc.cash === 100000 && !localHasPositions)) {
                // 本地无持仓或默认初始空账户，而后台有真实持仓/资金，同步至本地
                localStorage.setItem('ashare_live_account_v1', JSON.stringify(state.ashare_account));
            } else if (localHasPositions && !backendHasPositions) {
                // 本地持仓更完整，同步到后端
                pushStateToBackend({ ashare_account: localAcc });
            }
        }

        // 3. 同步自选股列表
        if (Array.isArray(state.ashare_watchlist) && state.ashare_watchlist.length > 0) {
            const localWlRaw = localStorage.getItem('ashare_live_watchlist_v1');
            if (!localWlRaw) {
                localStorage.setItem('ashare_live_watchlist_v1', JSON.stringify(state.ashare_watchlist));
            }
        }

        // 4. 同步画图数据
        if (state.drawings && typeof state.drawings === 'object') {
            for (const sym in state.drawings) {
                const drawingsList = state.drawings[sym];
                if (Array.isArray(drawingsList) && drawingsList.length > 0) {
                    const key = typeof ashareLiveDrawingsKey === 'function'
                        ? ashareLiveDrawingsKey(sym)
                        : `kline-ashare-live-drawings-v1::${sym}`;
                    if (!localStorage.getItem(key)) {
                        localStorage.setItem(key, JSON.stringify(drawingsList));
                    }
                }
            }
        }
    } catch (e) {
        console.warn('同步多端状态失败:', e);
    }
}

// 窗口重新获得焦点时同步多端状态，确保 Web 端与桌面端无缝协同
window.addEventListener('focus', function () {
    syncMultiPlatformState();
});

// 初始化应用
document.addEventListener('DOMContentLoaded', function () {
    initializeApp();
    setupEventListeners();
    setupKeyboardShortcuts();
});

// 初始化应用
async function initializeApp() {
    try {
        applyTheme(currentTheme, false, false);
        applyCryptoTheme(currentCryptoTheme, false, false);
        updatePeriodBadge('daily');
        await loadDataSources();

        // 优先从全局后台同步多端状态（活动用户、持仓、自选股）
        await syncMultiPlatformState();

        // 检查是否有保存的用户
        const savedUser = localStorage.getItem('currentUser');
        if (savedUser) {
            currentUser = savedUser;
            showMainApp();
            await loadUserStatistics();
        } else {
            showUserSelection();
        }

        // 加载用户列表
        await loadUsers();

        // 如果有保存的用户，初始化 AI API 状态
        if (currentUser) {
            fetch(`${API_BASE}/users/${currentUser}/settings`)
                .then(res => res.json())
                .then(settings => {
                    updateAIApiStatus(!!settings.enable_ai_api, currentUser);
                    if (settings.theme) {
                        applyTheme(settings.theme, true, false);
                    }
                    applyCryptoTheme(settings.crypto_theme || currentCryptoTheme, true, false);
                    applyTradingHoursFromSettings(settings);
                }).catch(e => console.error(e));
        }
    } catch (error) {
        console.error('初始化失败:', error);
        showUserSelection();
    }
}

async function updateAIApiStatus(enabled, username) {
    try {
        await fetch(`${API_BASE}/system/api_info`, {
            method: enabled ? 'POST' : 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user: username })
        });
    } catch (e) {
        console.error('Failed to update AI API status:', e);
    }
}

async function loadDataSources() {
    try {
        const response = await fetch(`${API_BASE}/data/sources`);
        if (!response.ok) return;
        const payload = await response.json();
        availableDataSources = payload.sources || [];
        hydrateDataSourceSelect('data-source', true);
        hydrateDataSourceSelect('sync-source', false);
    } catch (error) {
        console.error('加载数据源列表失败:', error);
    }
}

function hydrateDataSourceSelect(selectId, includeOffline = false) {
    const select = document.getElementById(selectId);
    if (!select) return;

    const currentValue = select.value;
    const options = availableDataSources.filter((item) => includeOffline || item.value !== 'offline');
    if (options.length === 0) return;

    select.innerHTML = '';
    options.forEach((item) => {
        const option = document.createElement('option');
        option.value = item.value;
        const disabledText = item.available ? '' : '（未安装）';
        option.textContent = `${item.label}${disabledText}`;
        option.disabled = !item.available;
        select.appendChild(option);
    });

    const hasCurrent = options.some((item) => item.value === currentValue && item.available);
    select.value = hasCurrent ? currentValue : options.find((item) => item.available)?.value || options[0].value;
}

function renderChartLegend() {
    const container = document.getElementById('chart-legend');
    if (!container) return;
    const items = [];
    maPeriods.forEach(p => {
        if (maSeries[p] && isMaLineVisible(p)) {
            items.push({ label: `MA${p}`, color: maSeries[p].options().color });
        }
    });
    if (bollSeries && bollSeries.upper && bollSeries.middle && bollSeries.lower) {
        items.push({ label: 'UP', color: bollSeries.upper.options().color });
        items.push({ label: 'MID', color: bollSeries.middle.options().color });
        items.push({ label: 'LOW', color: bollSeries.lower.options().color });
    }
    container.innerHTML = '';
    items.forEach(it => {
        const el = document.createElement('span');
        el.className = 'legend-chip';
        el.style.backgroundColor = it.color || '#999';
        el.textContent = it.label;
        container.appendChild(el);
    });
}

function renderIndicatorLegend() {
    const container = document.getElementById('indicator-legend');
    if (!container) return;
    container.innerHTML = '';
    const items = [];
    switch (currentIndicatorType) {
        case 'MACD':
            if (currentIndicatorSeries[0]) items.push({ label: 'DIF', color: currentIndicatorSeries[0].options().color });
            if (currentIndicatorSeries[1]) items.push({ label: 'DEA', color: currentIndicatorSeries[1].options().color });
            items.push({ label: 'MACD', color: '#999' });
            break;
        case 'KDJ':
            if (currentIndicatorSeries[0]) items.push({ label: 'K', color: currentIndicatorSeries[0].options().color });
            if (currentIndicatorSeries[1]) items.push({ label: 'D', color: currentIndicatorSeries[1].options().color });
            if (currentIndicatorSeries[2]) items.push({ label: 'J', color: currentIndicatorSeries[2].options().color });
            break;
        case 'RSI':
            currentIndicatorSeries.forEach(series => {
                items.push({ label: series.rsiTitle || series.options().title || 'RSI', color: series.options().color });
            });
            break;
        case 'BOLL':
            items.push({ label: 'UP', color: indicatorSettings.boll.upperColor });
            items.push({ label: 'MID', color: indicatorSettings.boll.middleColor });
            items.push({ label: 'LOW', color: indicatorSettings.boll.lowerColor });
            break;
    }
    items.forEach(it => {
        const el = document.createElement('span');
        el.className = 'legend-chip';
        el.style.backgroundColor = it.color || '#999';
        el.textContent = it.label;
        container.appendChild(el);
    });
}
// 设置事件监听器
function setupEventListeners() {
    // 用户选择相关
    document.getElementById('create-user-btn').addEventListener('click', createUser);
    document.getElementById('switch-user-btn').addEventListener('click', showUserSelection);
    document.getElementById('dashboard-new-training-btn')?.addEventListener('click', () => showTrainingSetup('main'));
    document.getElementById('refresh-history-btn')?.addEventListener('click', loadHistoryDashboard);
    document.querySelectorAll('.history-filter-btn').forEach((button) => {
        button.addEventListener('click', () => {
            currentHistoryFilter = button.dataset.historyFilter || 'all';
            document.querySelectorAll('.history-filter-btn').forEach((item) => item.classList.toggle('active', item === button));
            loadHistoryDashboard();
        });
    });
    document.getElementById('close-trade-reason-btn')?.addEventListener('click', closeTradeReasonModal);
    document.getElementById('cancel-trade-reason-btn')?.addEventListener('click', cancelTradeReasonPrompt);
    document.getElementById('save-trade-reason-btn')?.addEventListener('click', submitTradeReasonPrompt);
    document.getElementById('trade-reason-text')?.addEventListener('input', updateTradeReasonCount);

    // 训练设置与A股实时看盘相关
    document.getElementById('ashare-live-watch-btn')?.addEventListener('click', launchAshareLiveWatch);
    document.getElementById('ashare-live-search-btn')?.addEventListener('click', showAshareSearchModal);
    document.getElementById('ashare-live-exit-btn')?.addEventListener('click', exitAshareLiveWatch);
    // A股委托方式切换（市价/限价）——事件委托到两个切换组
    document.querySelectorAll('.ashare-order-type-switch').forEach((group) => {
        group.addEventListener('click', (event) => {
            const btn = event.target.closest('.ashare-order-type-btn');
            if (!btn) return;
            setAshareOrderType(group.dataset.target || 'buy', btn.dataset.otype || 'market');
        });
    });
    // 限价输入变化 -> 刷新买卖预览
    ['buy', 'sell'].forEach((side) => {
        document.getElementById(`ashare-${side}-limit-price`)?.addEventListener('input', updateAshareOrderPreview);
    });
    // 挂单撤单——事件委托到挂单列表容器
    document.getElementById('ashare-live-orders')?.addEventListener('click', (event) => {
        const btn = event.target.closest('.ashare-cancel-order-btn');
        if (btn && btn.dataset.orderId) cancelAsharePendingOrder(btn.dataset.orderId);
    });
    document.getElementById('close-ashare-search-btn')?.addEventListener('click', hideAshareSearchModal);
    // A股实时看盘自选股 (Watchlist) 交互绑定
    document.getElementById('ashare-wl-collapse-btn')?.addEventListener('click', () => collapseAshareWatchlist(true));
    document.getElementById('ashare-wl-expand-btn')?.addEventListener('click', () => collapseAshareWatchlist(false));
    document.getElementById('ashare-wl-add-btn')?.addEventListener('click', showAshareSearchModal);
    document.getElementById('ashare-wl-sort-price')?.addEventListener('click', () => toggleAshareWatchlistSort('price'));
    document.getElementById('ashare-wl-sort-change')?.addEventListener('click', () => toggleAshareWatchlistSort('change'));
    document.querySelectorAll('.ashare-wl-tab').forEach(tabBtn => {
        tabBtn.addEventListener('click', () => setAshareWatchlistTab(tabBtn.dataset.wlTab));
    });
    document.getElementById('ashare-adjust-balance-btn')?.addEventListener('click', showAshareBalanceModal);
    document.getElementById('ashare-live-adjust-btn')?.addEventListener('click', showAshareBalanceModal);
    document.getElementById('cancel-ashare-balance-btn')?.addEventListener('click', hideAshareBalanceModal);
    document.getElementById('save-ashare-balance-btn')?.addEventListener('click', saveAshareBalanceModal);
    document.getElementById('ashare-modal-unfreeze-btn')?.addEventListener('click', unfreezeAshareT1Holdings);
    document.getElementById('ashare-modal-reset-btn')?.addEventListener('click', resetAshareLiveAccount);
    document.getElementById('ashare-live-unfreeze-btn')?.addEventListener('click', unfreezeAshareT1Holdings);
    document.getElementById('ashare-tab-buy')?.addEventListener('click', () => selectAshareOrderAction('buy'));
    document.getElementById('ashare-tab-sell')?.addEventListener('click', () => selectAshareOrderAction('sell'));
    document.getElementById('ashare-submit-buy')?.addEventListener('click', executeAshareLiveBuy);
    document.getElementById('ashare-submit-sell')?.addEventListener('click', executeAshareLiveSell);
    document.getElementById('ashare-clear-history-btn')?.addEventListener('click', clearAshareTradeHistory);
    document.getElementById('ashare-buy-lots')?.addEventListener('input', updateAshareOrderPreview);
    document.getElementById('ashare-sell-lots')?.addEventListener('input', updateAshareOrderPreview);
    document.querySelectorAll('[data-ashare-fraction]').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.closest('.ashare-fraction-buttons')?.dataset.target || 'buy';
            applyAshareFraction(target, btn.dataset.ashareFraction);
        });
    });
    document.getElementById('quick-test-btc-btn')?.addEventListener('click', launchQuickTestBtc);
    document.getElementById('modal-quick-test-btc-btn')?.addEventListener('click', launchQuickTestBtc);
    document.getElementById('new-training-btn').addEventListener('click', showTrainingSetup);
    document.getElementById('cancel-setup-btn').addEventListener('click', hideTrainingSetup);
    document.getElementById('start-training-btn').addEventListener('click', startTraining);
    document.getElementById('cancel-crypto-history-prepare-btn')?.addEventListener('click', cancelCryptoHistoryPreparation);
    document.getElementById('retry-crypto-history-prepare-btn')?.addEventListener('click', retryCryptoHistoryPreparation);
    document.getElementById('load-earlier-year-btn')?.addEventListener('click', loadEarlierYear);
    document.getElementById('load-later-year-btn')?.addEventListener('click', loadLaterYear);

    // 设置按钮
    document.getElementById('settings-btn')?.addEventListener('click', showSettings);
    document.getElementById('save-settings-btn')?.addEventListener('click', saveSettings);
    document.getElementById('cancel-settings-btn')?.addEventListener('click', hideSettings);
    document.getElementById('refresh-offline-data-btn')?.addEventListener('click', loadCryptoOfflineStatus);
    document.getElementById('start-offline-download-btn')?.addEventListener('click', triggerCryptoOfflineDownload);
    document.getElementById('theme-toggle-btn')?.addEventListener('click', () => {
        applyTheme(currentTheme === 'dark' ? 'light' : 'dark', true, true);
    });
    document.getElementById('crypto-theme-toggle-btn')?.addEventListener('click', toggleCryptoTheme);
    initTradingHours();
    document.getElementById('data-sync-btn')?.addEventListener('click', showDataSyncModal);
    document.getElementById('confirm-sync-btn')?.addEventListener('click', syncOfflineData);
    document.getElementById('cancel-sync-btn')?.addEventListener('click', hideDataSyncModal);
    document.getElementById('sync-scope')?.addEventListener('change', updateSyncScopeUI);
    document.querySelectorAll('.view-period-btn').forEach((button) => {
        button.addEventListener('click', () => {
            switchViewPeriod(button.dataset.period || 'daily');
        });
    });

    // 标签页切换
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            switchTab(this.dataset.tab);
        });
    });

    document.querySelectorAll('.market-type-btn').forEach((button) => {
        button.addEventListener('click', () => setTrainingMarketType(button.dataset.marketType));
    });
    document.getElementById('crypto-symbol-search')?.addEventListener('input', (event) => {
        selectedCryptoInstrument = null;
        if (cryptoInstrumentSearchTimer) clearTimeout(cryptoInstrumentSearchTimer);
        cryptoInstrumentSearchTimer = setTimeout(() => {
            searchCryptoInstruments(event.target.value).catch((error) => {
                console.error('搜索币圈合约失败:', error);
                renderCryptoInstrumentResults([]);
            });
        }, 250);
    });
    document.getElementById('crypto-order-action')?.addEventListener('change', (event) => {
        selectCryptoOrderAction(event.target.value, false);
    });
    document.getElementById('crypto-order-type')?.addEventListener('change', (event) => {
        setCryptoOrderType(event.target.value);
    });
    document.querySelectorAll('[data-crypto-order-type]').forEach((button) => {
        button.addEventListener('click', () => setCryptoOrderType(button.dataset.cryptoOrderType || 'market'));
    });
    document.getElementById('crypto-order-leverage')?.addEventListener('change', () => {
        refreshCryptoMarginFraction();
        refreshCryptoOrderPreview();
        refreshCryptoRiskCalcResult();
    });
    document.getElementById('crypto-submit-order')?.addEventListener('click', submitCryptoOrder);
    document.getElementById('crypto-save-fee-rates')?.addEventListener('click', submitCryptoFeeRates);
    document.getElementById('crypto-limit-price')?.addEventListener('input', () => {
        refreshCryptoOrderPreview();
        refreshCryptoTpSlPnl();
    });
    document.querySelectorAll('[data-crypto-price-offset]').forEach((button) => {
        button.addEventListener('click', () => applyCryptoPriceOffset(button));
    });
    document.querySelectorAll('[data-crypto-margin-fraction]').forEach((button) => {
        button.addEventListener('click', () => applyCryptoMarginFraction(button));
    });
    document.getElementById('crypto-margin')?.addEventListener('input', () => {
        document.querySelectorAll('[data-crypto-margin-fraction]').forEach((button) => {
            button.classList.remove('active');
            button.setAttribute('aria-pressed', 'false');
        });
        refreshCryptoOrderPreview();
        refreshCryptoTpSlPnl();
    });

    // 止盈止损
    document.getElementById('crypto-tpsl-enabled')?.addEventListener('change', (event) => {
        document.getElementById('crypto-tpsl-fields')?.classList.toggle('hidden', !event.target.checked);
        if (!event.target.checked) {
            const tpInput = document.getElementById('crypto-tp-price');
            const slInput = document.getElementById('crypto-sl-price');
            if (tpInput) tpInput.value = '';
            if (slInput) slInput.value = '';
            refreshCryptoTpSlPnl();
        }
        refreshCryptoOrderPreview();
    });
    document.getElementById('crypto-tp-price')?.addEventListener('input', () => {
        refreshCryptoTpSlPnl();
        refreshCryptoOrderPreview();
    });
    document.getElementById('crypto-sl-price')?.addEventListener('input', () => {
        refreshCryptoTpSlPnl();
        refreshCryptoOrderPreview();
        refreshCryptoRiskCalcResult();
    });

    // 以损定仓
    document.getElementById('crypto-riskcalc-enabled')?.addEventListener('change', toggleCryptoRiskCalcFields);
    ['crypto-riskcalc-entry', 'crypto-riskcalc-stop', 'crypto-riskcalc-maxloss'].forEach((id) => {
        document.getElementById(id)?.addEventListener('input', refreshCryptoRiskCalcResult);
    });
    document.getElementById('crypto-riskcalc-apply')?.addEventListener('click', applyCryptoRiskCalc);

    // 回放控制
    document.getElementById('play-pause-btn').addEventListener('click', togglePlayback);
    document.getElementById('next-bar-btn').addEventListener('click', nextBar);
    document.getElementById('playback-speed').addEventListener('change', updatePlaybackSpeed);

    // 复权设置
    document.querySelectorAll('input[name="adjustment"]').forEach(radio => {
        radio.addEventListener('change', updateAdjustment);
    });

    // 交易操作
    document.getElementById('shift-toggle-btn')?.addEventListener('click', () => {
        isShiftClicked = !isShiftClicked;
        updatePriceMode();
    });

        document.getElementById('buy-btn')?.addEventListener('click', () => {
        requestTradeWithReason('buy', (isShiftClicked || isShiftKeyPressed) ? 'open' : 'close');
    });

    document.getElementById('sell-btn')?.addEventListener('click', () => {
        requestTradeWithReason('sell', (isShiftClicked || isShiftKeyPressed) ? 'open' : 'close');
    });

    // 交易数量输入限制
    document.getElementById('trade-quantity').addEventListener('input', limitTradeQuantity);
    document.getElementById('sell-quantity')?.addEventListener('input', limitSellQuantity);

    document.querySelectorAll('.order-type-btn').forEach(btn => {
        btn.addEventListener('click', () => setOrderType(btn.dataset.orderType || 'market'));
    });

    // 仓位比例按钮
    document.querySelectorAll('.btn-fraction').forEach(btn => {
        btn.addEventListener('click', () => {
            if (isAshareLiveMode) {
                applyAshareLiveFraction(btn);
                return;
            }
            const fraction = parseInt(btn.dataset.fraction);
            const target = btn.dataset.target || 'buy';
            const quantityInput = document.getElementById(target === 'sell' ? 'sell-quantity' : 'trade-quantity');
            const maxElement = document.getElementById(target === 'sell' ? 'max-sell-quantity' : 'max-buy-quantity');
            const maxQty = parseInt(maxElement?.textContent) || 0;
            // 根据当前是否有持仓来决定用买入还是卖出的最大值
            quantityInput.value = Math.max(Math.floor(maxQty / fraction), maxQty > 0 ? 1 : 0);
            quantityInput.dispatchEvent(new Event('input'));
            // 高亮选中的按钮
            document.querySelectorAll('.btn-fraction').forEach(b => {
                if ((b.dataset.target || 'buy') === target) b.classList.remove('active');
            });
            btn.classList.add('active');
        });
    });

    // 训练控制
    setOrderType('market');
    document.getElementById('end-training-btn').addEventListener('click', endTraining);
    document.getElementById('reset-training-btn').addEventListener('click', resetTraining);
    document.getElementById('crypto-end-training-btn')?.addEventListener('click', endTraining);
    document.getElementById('crypto-reset-training-btn')?.addEventListener('click', resetTraining);

    // 技术指标选择
    document.getElementById('indicator-select')?.addEventListener('change', changeIndicator);
    // 副图图例行：点击指标名/参数打开指标库切换（AiCoin 风格）
    document.getElementById('indicator-header-picker')?.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleIndicatorLibrary();
    });
    // 指标设置弹窗（AiCoin 风格）
    syncIndicatorHiddenInputsFromSettings();
    document.getElementById('ind-settings-close')?.addEventListener('click', closeIndicatorSettings);
    document.getElementById('ind-settings-overlay')?.addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeIndicatorSettings();
    });
    document.getElementById('ind-settings-apply')?.addEventListener('click', applyIndicatorSettingsFromForm);
    document.getElementById('ind-settings-reset')?.addEventListener('click', resetCurrentIndicatorSettings);
    document.getElementById('ind-settings-hide')?.addEventListener('click', toggleSettingsIndicatorDisplay);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !document.getElementById('ind-settings-overlay')?.classList.contains('hidden')) {
            closeIndicatorSettings();
        }
    });
    // 指标库面板
    document.getElementById('indicator-library-btn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleIndicatorLibrary();
    });
    document.getElementById('ind-lib-close')?.addEventListener('click', () => hideIndicatorLibrary());
    document.getElementById('indicator-library-panel')?.addEventListener('click', (e) => e.stopPropagation());
    document.addEventListener('click', () => hideIndicatorLibrary());
    document.querySelectorAll('[data-crypto-action]').forEach((button) => {
        button.addEventListener('click', () => selectCryptoOrderAction(button.dataset.cryptoAction));
    });
    document.getElementById('toggle-volume-panel-btn')?.addEventListener('click', () => toggleChartPanel('volume-chart'));
    document.getElementById('toggle-indicator-panel-btn')?.addEventListener('click', () => toggleChartPanel('indicator-chart'));
    document.getElementById('chart-fullscreen-btn')?.addEventListener('click', toggleChartFullscreen);
    document.getElementById('chart-focus-exit-btn')?.addEventListener('click', () => setChartFocusMode(false));
    initBarReplayToolbarEvents();

    // 筹码分布切换
    document.getElementById('toggle-chip-distribution')?.addEventListener('change', updateChipDistribution);

    // 复盘报告
    document.getElementById('view-full-chart-btn').addEventListener('click', viewFullChart);
    document.getElementById('ai-analyze-btn').addEventListener('click', requestAIAnalysis);
    // document.getElementById('new-training-from-report-btn').addEventListener('click', showTrainingSetup);
    document.getElementById('new-training-from-report-btn').addEventListener('click', () => {
        showTrainingSetup('report');
    });
    document.getElementById('return-main-menu-btn')?.addEventListener('click', resetToMainAppState);


    // 监听窗口大小变化和图表面板拖拽
    setupChartPanelResizers();
    setupCryptoConsoleResizer();
    window.addEventListener('resize', resizeCharts);
}

// 设置键盘快捷键
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Shift') {
            isShiftKeyPressed = true;
            updatePriceMode();
        }
        if (event.key === 'Escape' && document.getElementById('main-app')?.classList.contains('chart-focus-mode')) {
            event.preventDefault();
            setChartFocusMode(false);
            return;
        }
        // 只在训练界面激活快捷键
        if (document.getElementById('training-interface').classList.contains('hidden') || isViewOnlyMode) {
            return;
        }

        // 焦点在任意输入框/下拉框/文本域时，跳过所有快捷键，允许正常输入
        const activeTag = document.activeElement?.tagName;
        const isFormElementFocused = activeTag === 'INPUT' || activeTag === 'SELECT' || activeTag === 'TEXTAREA';
        if (isFormElementFocused) {
            return;
        }

        // 如果是由于按住按键导致的重复触发，则忽略
        if (event.repeat) {
            return;
        }

        // Alt+* 画图工具快捷键层（TradingView 惯例）：
        // 在交易/回放裸键之前拦截分发——Alt+S 做空与裸 S 卖出通过修饰键物理隔离，互不冲突。
        // 适用三种模式（币圈回放 / A股回放 / A股实时看盘），只读复盘模式下不生效。
        if (event.altKey && !event.ctrlKey && !event.metaKey) {
            const shortcutKey = event.key.toLowerCase();
            // Alt+A：A股实时看盘下切换「价格预警」落线模式（A 不在画图工具键位表中）
            if (shortcutKey === 'a' && isAshareLiveMode) {
                event.preventDefault();
                toggleAshareAlertAddMode();
                return;
            }
            // Alt+P / Alt+R：开启/退出 K线截断复盘模式
            if (shortcutKey === 'p' || shortcutKey === 'r') {
                event.preventDefault();
                toggleBarReplayCutSelection();
                return;
            }
            // Alt+T：切换明暗主题 (币圈训练与 A 股实时看盘均支持)
            if (shortcutKey === 't' && (isCryptoMode() || isAshareLiveMode)) {
                event.preventDefault();
                toggleCryptoTheme();
                return;
            }
            const drawingTool = DRAWING_TOOL_SHORTCUTS[shortcutKey];
            if (drawingTool) {
                event.preventDefault();
                activateDrawingTool(drawingTool);
                return;
            }
        }

        // Esc：取消截断复盘选点，或退出复盘回到最新
        if (event.key === 'Escape') {
            if (barReplayState.isSelectingCutPoint) {
                event.preventDefault();
                cancelBarReplayCutSelection();
                return;
            }
            if (barReplayState.active) {
                event.preventDefault();
                exitBarReplay();
                return;
            }
        }

        // Esc：退出价格预警落线模式（画线手势的 Esc 由 drawing_tools 自行 cancelGesture）
        if (event.key === 'Escape' && ashareAlertAdding) {
            event.preventDefault();
            setAshareAlertAddMode(false);
            return;
        }

        // 处于截断复盘模式下的键盘控制（空格播放/暂停、右方向键前进一根，全模式通用）
        if (barReplayState.active) {
            if (event.key === ' ') {
                event.preventDefault();
                toggleBarReplayPlayPause();
                return;
            }
            if (event.key === 'ArrowRight') {
                event.preventDefault();
                stepBarReplayForward();
                return;
            }
        }

        // A股实时看盘：跳过交易/回放裸键（B/S/空格/Enter/数字为币圈与回放推进专用，避免误触）；
        // 画图快捷键（Alt 层）不受影响。此守卫同时修复历史耦合：看盘模式按 B/S 误触币圈下单。
        if (isAshareLiveMode) {
            return;
        }

        const quantityInput = document.getElementById('trade-quantity');

        switch (event.key.toLowerCase()) {
            case 'b':
            case '+':
            case '=':
                event.preventDefault(); // 阻止默认行为（如输入'b'或'+'）
                executeBuy((isShiftClicked || isShiftKeyPressed || event.shiftKey) ? 'open' : 'close');
                break;

            case 's':
            case '-':
            case '_':
                event.preventDefault(); // 阻止默认行为
                executeSell((isShiftClicked || isShiftKeyPressed || event.shiftKey) ? 'open' : 'close');
                break;

            case ' ':
                // 仅空格 = 下一根K线（Enter 已让位给连续折线的"结束成线"，避免与空格功能重复）
                event.preventDefault();
                nextBar();
                break;

            case '0': case '1': case '2': case '3': case '4':
            case '5': case '6': case '7': case '8': case '9':
                // 此处焦点不在任何输入框（已在上方提前返回），直接重定向到数量输入
                event.preventDefault();
                quantityInput.focus();
                quantityInput.value = event.key;
                break;
        }

    });
    
    document.addEventListener('keyup', function (event) {
        if (event.key === 'Shift') {
            isShiftKeyPressed = false;
            updatePriceMode();
        }
    });
}

function getChartPanelElements() {
    const container = document.getElementById('chart-panels');
    const panels = {
        chart: document.getElementById('chart'),
        'volume-chart': document.getElementById('volume-chart'),
        'indicator-chart': document.getElementById('indicator-chart'),
    };
    return { container, panels };
}

function normalizeChartPanelRatios(candidate) {
    const source = candidate && typeof candidate === 'object' ? candidate : CHART_PANEL_DEFAULT_RATIOS;
    const values = Object.keys(CHART_PANEL_DEFAULT_RATIOS).map((panelId) => {
        const value = Number(source[panelId]);
        return Number.isFinite(value) && value > 0 ? value : CHART_PANEL_DEFAULT_RATIOS[panelId];
    });
    const total = values.reduce((sum, value) => sum + value, 0) || 1;
    return {
        chart: values[0] / total,
        'volume-chart': values[1] / total,
        'indicator-chart': values[2] / total,
    };
}

function chartPanelStorageKey() {
    return isAshareLiveMode ? CHART_PANEL_STORAGE_KEY_ASHARE : CHART_PANEL_STORAGE_KEY;
}

function readChartPanelRatios() {
    const storageKey = chartPanelStorageKey();
    if (chartPanelRatios && chartPanelRatiosKey === storageKey) return chartPanelRatios;
    try {
        chartPanelRatios = normalizeChartPanelRatios(JSON.parse(localStorage.getItem(storageKey) || 'null'));
    } catch (error) {
        chartPanelRatios = normalizeChartPanelRatios(null);
    }
    chartPanelRatiosKey = storageKey;
    return chartPanelRatios;
}

function persistChartPanelRatios() {
    if (!chartPanelRatios) return;
    localStorage.setItem(chartPanelStorageKey(), JSON.stringify(chartPanelRatios));
}

function setChartPanelHeight(panel, height) {
    if (!panel || !Number.isFinite(height)) return;
    panel.style.flex = `0 0 ${Math.round(height)}px`;
    panel.style.height = `${Math.round(height)}px`;
}

function getChartPanelAvailableHeight(container) {
    const splitterHeight = Array.from(container.querySelectorAll('.chart-panel-splitter'))
        .filter((splitter) => splitter.style.display !== 'none' && !splitter.classList.contains('splitter-hidden'))
        .reduce((sum, splitter) => sum + splitter.getBoundingClientRect().height, 0);
    return Math.max(0, container.clientHeight - splitterHeight);
}

function isSubchartPanelVisible() {
    const el = document.getElementById('indicator-chart');
    if (!el) return false;
    if (el.classList.contains('panel-collapsed')) return false;
    if (!indicatorPanelVisible) return false;
    return Array.isArray(activeSubcharts) && activeSubcharts.length > 0;
}

function applyChartPanelRatios(candidateRatios) {
    const { container, panels } = getChartPanelElements();
    if (!container || container.clientHeight <= 0) return;
    chartPanelRatios = normalizeChartPanelRatios(candidateRatios || readChartPanelRatios());

    const indicatorEl = panels['indicator-chart'];
    const volumeEl = panels['volume-chart'];
    const chartEl = panels.chart;
    const indicatorSplitter = document.getElementById('indicator-splitter')
        || container.querySelector('.chart-panel-splitter[data-after-panel="indicator-chart"]');
    const volumeSplitter = container.querySelector('.chart-panel-splitter[data-after-panel="volume-chart"]');

    const showIndicator = isSubchartPanelVisible();
    const showVolume = volumeEl && !volumeEl.classList.contains('panel-collapsed');

    // 动态同步 DOM 显示状态与类名，彻底消除留白与残留缝隙
    if (indicatorEl) {
        if (showIndicator) {
            indicatorEl.style.display = 'flex';
            indicatorEl.classList.remove('panel-collapsed');
        } else {
            indicatorEl.style.display = 'none';
            indicatorEl.classList.add('panel-collapsed');
        }
    }
    if (indicatorSplitter) {
        if (showIndicator) {
            indicatorSplitter.style.display = '';
            indicatorSplitter.classList.remove('splitter-hidden');
        } else {
            indicatorSplitter.style.display = 'none';
            indicatorSplitter.classList.add('splitter-hidden');
        }
    }
    if (volumeSplitter) {
        if (showVolume) {
            volumeSplitter.style.display = '';
            volumeSplitter.classList.remove('splitter-hidden');
        } else {
            volumeSplitter.style.display = 'none';
            volumeSplitter.classList.add('splitter-hidden');
        }
    }

    const availableHeight = getChartPanelAvailableHeight(container);
    if (availableHeight <= 0) return;

    const heights = { chart: 0, 'volume-chart': 0, 'indicator-chart': 0 };

    if (!showIndicator && !showVolume) {
        // 仅主图可见，主图独占全部可用高度
        heights.chart = availableHeight;
    } else if (!showIndicator && showVolume) {
        // 主图 + 成交量图，副图完全隐藏，原副图高度全部返还主图
        const totalWeight = (chartPanelRatios.chart || 0.72) + (chartPanelRatios['volume-chart'] || 0.11);
        const volRatio = (chartPanelRatios['volume-chart'] || 0.11) / (totalWeight || 1);
        heights['volume-chart'] = Math.max(CHART_PANEL_MIN_HEIGHTS['volume-chart'], availableHeight * volRatio);
        heights.chart = Math.max(CHART_PANEL_MIN_HEIGHTS.chart, availableHeight - heights['volume-chart']);
    } else if (showIndicator && !showVolume) {
        // 主图 + 副图
        const minIndHeight = Math.max(52, (activeSubcharts.length || 1) * 65);
        const totalWeight = (chartPanelRatios.chart || 0.72) + (chartPanelRatios['indicator-chart'] || 0.17);
        const indRatio = (chartPanelRatios['indicator-chart'] || 0.17) / (totalWeight || 1);
        heights['indicator-chart'] = Math.max(minIndHeight, availableHeight * indRatio);
        heights.chart = Math.max(CHART_PANEL_MIN_HEIGHTS.chart, availableHeight - heights['indicator-chart']);
    } else {
        // 三个面板均可见：根据激活副图数量动态自适应副图最小高度与比例
        const subCount = Math.max(1, activeSubcharts.length);
        const minIndHeight = subCount === 1 ? 52 : Math.max(52, subCount * 70);
        CHART_PANEL_MIN_HEIGHTS['indicator-chart'] = minIndHeight;

        let indRatio = chartPanelRatios['indicator-chart'] || 0.17;
        let chartRatio = chartPanelRatios.chart || 0.72;
        let volRatio = chartPanelRatios['volume-chart'] || 0.11;

        if (subCount >= 2 && indRatio < 0.28) {
            const targetIndRatio = Math.min(0.46, subCount * 0.15);
            const needed = targetIndRatio - indRatio;
            if (chartRatio - needed >= 0.35) {
                indRatio = targetIndRatio;
                chartRatio -= needed;
            }
        }

        heights.chart = Math.max(CHART_PANEL_MIN_HEIGHTS.chart, availableHeight * chartRatio);
        heights['volume-chart'] = Math.max(CHART_PANEL_MIN_HEIGHTS['volume-chart'], availableHeight * volRatio);
        heights['indicator-chart'] = Math.max(minIndHeight, availableHeight * indRatio);

        let overflow = heights.chart + heights['volume-chart'] + heights['indicator-chart'] - availableHeight;
        ['chart', 'indicator-chart', 'volume-chart'].forEach((panelId) => {
            if (overflow <= 0) return;
            const minH = panelId === 'indicator-chart' ? minIndHeight : CHART_PANEL_MIN_HEIGHTS[panelId];
            const reducible = Math.max(0, heights[panelId] - minH);
            const reduction = Math.min(reducible, overflow);
            heights[panelId] -= reduction;
            overflow -= reduction;
        });
        if (overflow < 0) heights.chart += Math.abs(overflow);
    }

    setChartPanelHeight(chartEl, heights.chart);
    setChartPanelHeight(volumeEl, showVolume ? heights['volume-chart'] : 0);
    setChartPanelHeight(indicatorEl, showIndicator ? heights['indicator-chart'] : 0);
    applySubchartHeights();
    window.requestAnimationFrame(resizeCharts);
}

function updateChartPanelRatiosFromDom() {
    const { container, panels } = getChartPanelElements();
    if (!container) return;
    const availableHeight = getChartPanelAvailableHeight(container);
    if (availableHeight <= 0) return;
    chartPanelRatios = normalizeChartPanelRatios({
        chart: panels.chart.getBoundingClientRect().height / availableHeight,
        'volume-chart': panels['volume-chart'].getBoundingClientRect().height / availableHeight,
        'indicator-chart': panels['indicator-chart'].getBoundingClientRect().height / availableHeight,
    });
}

function resizeChartPanelPair(splitter, delta) {
    const beforePanel = document.getElementById(splitter.dataset.beforePanel);
    const afterPanel = document.getElementById(splitter.dataset.afterPanel);
    if (!beforePanel || !afterPanel) return;

    if (splitter.id === 'indicator-splitter' || splitter.dataset.afterPanel === 'indicator-chart') {
        const chartEl = document.getElementById('chart');
        const volumeEl = document.getElementById('volume-chart');
        const indicatorEl = afterPanel;
        if (!chartEl || !indicatorEl) return;

        const chartStart = Number(splitter.dataset.chartStart || chartEl.getBoundingClientRect().height);
        const volumeStart = Number(splitter.dataset.volumeStart || (volumeEl ? volumeEl.getBoundingClientRect().height : 0));
        const indicatorStart = Number(splitter.dataset.indicatorStart || indicatorEl.getBoundingClientRect().height);
        const showVolume = volumeEl && !volumeEl.classList.contains('panel-collapsed');

        const totalHeight = chartStart + (showVolume ? volumeStart : 0) + indicatorStart;
        const subCount = Math.max(1, activeSubcharts.length);
        const minIndH = Math.max(52, subCount * 50);
        const minChartH = CHART_PANEL_MIN_HEIGHTS.chart;
        const minVolH = showVolume ? CHART_PANEL_MIN_HEIGHTS['volume-chart'] : 0;
        const upperMin = minChartH + minVolH;

        const nextInd = Math.min(totalHeight - upperMin, Math.max(minIndH, indicatorStart - delta));
        const upperAvailable = totalHeight - nextInd;

        let nextChart = 0;
        let nextVol = 0;
        if (showVolume) {
            nextVol = Math.max(minVolH, Math.min(volumeStart, upperAvailable - minChartH));
            nextChart = upperAvailable - nextVol;
        } else {
            nextChart = upperAvailable;
        }

        setChartPanelHeight(chartEl, nextChart);
        if (showVolume) setChartPanelHeight(volumeEl, nextVol);
        setChartPanelHeight(indicatorEl, nextInd);

        applySubchartHeights();
        updateChartPanelRatiosFromDom();
        resizeCharts();
        return;
    }

    const beforeStart = Number(splitter.dataset.beforeStart);
    const afterStart = Number(splitter.dataset.afterStart);
    if (!Number.isFinite(beforeStart) || !Number.isFinite(afterStart)) return;
    const pairHeight = beforeStart + afterStart;
    const beforeMinimum = CHART_PANEL_MIN_HEIGHTS[beforePanel.id];
    const afterMinimum = CHART_PANEL_MIN_HEIGHTS[afterPanel.id];
    const nextBefore = Math.min(pairHeight - afterMinimum, Math.max(beforeMinimum, beforeStart + delta));
    setChartPanelHeight(beforePanel, nextBefore);
    setChartPanelHeight(afterPanel, pairHeight - nextBefore);
    updateChartPanelRatiosFromDom();
    resizeCharts();
}

function beginChartPanelResize(splitter, clientY) {
    const beforePanel = document.getElementById(splitter.dataset.beforePanel);
    const afterPanel = document.getElementById(splitter.dataset.afterPanel);
    if (!beforePanel || !afterPanel) return;
    splitter.dataset.dragStartY = String(clientY);
    splitter.dataset.beforeStart = String(beforePanel.getBoundingClientRect().height);
    splitter.dataset.afterStart = String(afterPanel.getBoundingClientRect().height);

    const chartEl = document.getElementById('chart');
    const volumeEl = document.getElementById('volume-chart');
    const indicatorEl = document.getElementById('indicator-chart');
    if (chartEl) splitter.dataset.chartStart = String(chartEl.getBoundingClientRect().height);
    if (volumeEl) splitter.dataset.volumeStart = String(volumeEl.getBoundingClientRect().height);
    if (indicatorEl) splitter.dataset.indicatorStart = String(indicatorEl.getBoundingClientRect().height);
}

function setupChartPanelResizers() {
    const { container } = getChartPanelElements();
    if (!container || container.dataset.resizersReady === 'true') return;
    container.dataset.resizersReady = 'true';
    applyChartPanelRatios(readChartPanelRatios());

    const finishResize = (event) => {
        if (!activeChartPanelSplitter) return;
        activeChartPanelSplitter.releasePointerCapture?.(event.pointerId);
        activeChartPanelSplitter.classList.remove('is-dragging');
        document.body.classList.remove('chart-panel-resizing');
        activeChartPanelSplitter = null;
        chartPanelResizing = false;
        updateChartPanelRatiosFromDom();
        persistChartPanelRatios();
    };

    container.querySelectorAll('.chart-panel-splitter').forEach((splitter) => {
        splitter.addEventListener('pointerdown', (event) => {
            event.preventDefault();
            activeChartPanelSplitter = splitter;
            chartPanelResizing = true;
            beginChartPanelResize(splitter, event.clientY);
            splitter.classList.add('is-dragging');
            document.body.classList.add('chart-panel-resizing');
            splitter.setPointerCapture?.(event.pointerId);
        });
        splitter.addEventListener('keydown', (event) => {
            if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
            event.preventDefault();
            beginChartPanelResize(splitter, 0);
            resizeChartPanelPair(splitter, event.key === 'ArrowDown' ? 16 : -16);
            persistChartPanelRatios();
        });
    });

    window.addEventListener('pointermove', (event) => {
        if (!chartPanelResizing || !activeChartPanelSplitter) return;
        resizeChartPanelPair(
            activeChartPanelSplitter,
            event.clientY - Number(activeChartPanelSplitter.dataset.dragStartY),
        );
    });
    window.addEventListener('pointerup', finishResize);
    window.addEventListener('pointercancel', finishResize);
    window.addEventListener('blur', finishResize);

    if (typeof ResizeObserver !== 'undefined') {
        chartPanelResizeObserver?.disconnect();
        chartPanelResizeObserver = new ResizeObserver(() => {
            if (chartPanelResizing) return;
            window.cancelAnimationFrame(chartPanelResizeFrame);
            chartPanelResizeFrame = window.requestAnimationFrame(() => {
                applyChartPanelRatios(chartPanelRatios || readChartPanelRatios());
            });
        });
        chartPanelResizeObserver.observe(container);
    }
}

// === Crypto console resizer (vertical splitter + collapse) ===
const CRYPTO_CONSOLE_WIDTH_KEY = 'kline-crypto-console-width-v1';
const CRYPTO_CONSOLE_COLLAPSED_KEY = 'kline-crypto-console-collapsed-v1';
const CRYPTO_CONSOLE_DEFAULT_WIDTH = 380;
const CRYPTO_CONSOLE_MIN_WIDTH = 340;
const CRYPTO_CONSOLE_MAX_WIDTH = 580;

let cryptoConsoleResizing = false;

function readCryptoConsoleLayout() {
    let width = CRYPTO_CONSOLE_DEFAULT_WIDTH;
    let collapsed = false;
    try {
        const storedWidth = localStorage.getItem(CRYPTO_CONSOLE_WIDTH_KEY);
        if (storedWidth) {
            const parsed = parseInt(storedWidth, 10);
            if (Number.isFinite(parsed) && parsed >= CRYPTO_CONSOLE_MIN_WIDTH && parsed <= CRYPTO_CONSOLE_MAX_WIDTH) {
                width = parsed;
            }
        }
        const storedCollapsed = localStorage.getItem(CRYPTO_CONSOLE_COLLAPSED_KEY);
        if (storedCollapsed === 'true') collapsed = true;
    } catch (e) {
        // localStorage may be unavailable
    }
    // Clamp to 45% of viewport
    const maxViewport = Math.floor(window.innerWidth * 0.45);
    if (width > maxViewport) width = Math.max(CRYPTO_CONSOLE_MIN_WIDTH, maxViewport);
    return { width, collapsed };
}

function persistCryptoConsoleLayout(layout) {
    try {
        if (layout.width !== undefined) localStorage.setItem(CRYPTO_CONSOLE_WIDTH_KEY, String(layout.width));
        if (layout.collapsed !== undefined) localStorage.setItem(CRYPTO_CONSOLE_COLLAPSED_KEY, String(layout.collapsed));
    } catch (e) {
        // localStorage may be unavailable
    }
}

function applyCryptoConsoleLayout(layout) {
    const mainApp = document.getElementById('main-app');
    if (!mainApp) return;
    const clamped = Math.max(CRYPTO_CONSOLE_MIN_WIDTH, Math.min(CRYPTO_CONSOLE_MAX_WIDTH, layout.width || CRYPTO_CONSOLE_DEFAULT_WIDTH));
    mainApp.style.setProperty('--crypto-console-width', clamped + 'px');
    mainApp.classList.toggle('crypto-console-collapsed', !!layout.collapsed);
    // Update collapse button icon and aria
    const collapseBtn = document.getElementById('crypto-console-collapse-btn');
    if (collapseBtn) {
        collapseBtn.textContent = layout.collapsed ? '‹' : '›';
        collapseBtn.setAttribute('aria-label', layout.collapsed ? '展开交易台' : '收起交易台');
        collapseBtn.setAttribute('title', layout.collapsed ? '展开交易台' : '收起交易台');
    }
}

function toggleCryptoConsoleCollapsed() {
    const layout = readCryptoConsoleLayout();
    layout.collapsed = !layout.collapsed;
    persistCryptoConsoleLayout(layout);
    applyCryptoConsoleLayout(layout);
    resizeCharts();
}

function setupCryptoConsoleResizer() {
    const splitter = document.getElementById('crypto-console-splitter');
    const collapseBtn = document.getElementById('crypto-console-collapse-btn');
    const collapsedTab = document.getElementById('crypto-console-collapsed-tab');
    const mainApp = document.getElementById('main-app');
    if (!splitter || !mainApp) return;

    // Collapse button
    collapseBtn?.addEventListener('click', toggleCryptoConsoleCollapsed);

    // Collapsed tab click to expand
    collapsedTab?.addEventListener('click', toggleCryptoConsoleCollapsed);
    collapsedTab?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggleCryptoConsoleCollapsed();
        }
    });

    // Pointer drag on splitter
    let startX = 0;
    let startWidth = 0;

    function onPointerDown(e) {
        if (e.button !== 0) return;
        cryptoConsoleResizing = true;
        const layout = readCryptoConsoleLayout();
        startWidth = layout.width;
        startX = e.clientX;
        splitter.classList.add('is-dragging');
        document.body.classList.add('crypto-console-resizing');
        splitter.setPointerCapture(e.pointerId);
        e.preventDefault();
    }

    function onPointerMove(e) {
        if (!cryptoConsoleResizing) return;
        const dx = startX - e.clientX;
        const newWidth = Math.max(CRYPTO_CONSOLE_MIN_WIDTH, Math.min(CRYPTO_CONSOLE_MAX_WIDTH, startWidth + dx));
        const maxViewport = Math.floor(window.innerWidth * 0.45);
        const clamped = Math.min(newWidth, maxViewport);
        mainApp.style.setProperty('--crypto-console-width', clamped + 'px');
        resizeCharts();
    }

    function onPointerUp(e) {
        if (!cryptoConsoleResizing) return;
        cryptoConsoleResizing = false;
        splitter.classList.remove('is-dragging');
        document.body.classList.remove('crypto-console-resizing');
        // Read the current width from CSS custom property and persist
        const computed = getComputedStyle(mainApp).getPropertyValue('--crypto-console-width').trim();
        const parsed = parseInt(computed, 10);
        if (Number.isFinite(parsed)) {
            persistCryptoConsoleLayout({ width: parsed });
        }
        resizeCharts();
    }

    splitter.addEventListener('pointerdown', onPointerDown);
    splitter.addEventListener('pointermove', onPointerMove);
    splitter.addEventListener('pointerup', onPointerUp);
    splitter.addEventListener('pointercancel', onPointerUp);

    // Keyboard: ArrowLeft increases console width, ArrowRight decreases
    splitter.addEventListener('keydown', (e) => {
        const layout = readCryptoConsoleLayout();
        if (e.key === 'ArrowLeft') {
            e.preventDefault();
            const newWidth = Math.min(CRYPTO_CONSOLE_MAX_WIDTH, layout.width + 16);
            persistCryptoConsoleLayout({ width: newWidth, collapsed: layout.collapsed });
            applyCryptoConsoleLayout({ width: newWidth, collapsed: layout.collapsed });
            resizeCharts();
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            const newWidth = Math.max(CRYPTO_CONSOLE_MIN_WIDTH, layout.width - 16);
            persistCryptoConsoleLayout({ width: newWidth, collapsed: layout.collapsed });
            applyCryptoConsoleLayout({ width: newWidth, collapsed: layout.collapsed });
            resizeCharts();
        }
    });

    // Apply stored layout on setup
    const storedLayout = readCryptoConsoleLayout();
    applyCryptoConsoleLayout(storedLayout);
}

// 处理窗口大小变化
function resizeCharts() {
    if (chart && !document.getElementById('training-interface').classList.contains('hidden')) {
        applySubchartHeights();
        const chartContainer = document.getElementById('chart');
        const volumeContainer = document.getElementById('volume-chart');

        if (chartContainer && chartContainer.clientWidth > 0 && chartContainer.clientHeight > 0) {
            chart.resize(chartContainer.clientWidth, chartContainer.clientHeight);
        }
        if (volumeContainer && volumeContainer.clientWidth > 0 && volumeContainer.clientHeight > 0) {
            volumeChart.resize(volumeContainer.clientWidth, volumeContainer.clientHeight);
        }
        // 调整所有激活的副图
        if (typeof subchartInstances === 'object' && subchartInstances) {
            Object.keys(subchartInstances).forEach((id) => {
                const inst = subchartInstances[id];
                const canvasEl = document.getElementById('subchart-canvas-' + id);
                if (inst && inst.chart && canvasEl && canvasEl.clientWidth > 0 && canvasEl.clientHeight > 0) {
                    inst.chart.resize(canvasEl.clientWidth, canvasEl.clientHeight);
                }
            });
        }
        // 兼容单例 indicatorChart
        const indicatorContainer = document.getElementById('indicator-canvas');
        if (indicatorChart && indicatorContainer && indicatorContainer.clientWidth > 0 && indicatorContainer.clientHeight > 0) {
            indicatorChart.resize(indicatorContainer.clientWidth, indicatorContainer.clientHeight);
        }
        
        scheduleChipDistributionRender();
        scheduleExtremePriceTagsUpdate();
        scheduleTradingHoursBandsUpdate();
        scheduleAshareAlertChipsUpdate();
    }
}

// 用户管理
async function loadUsers() {
    try {
        const response = await fetch(`${API_BASE}/users`);
        const users = await response.json();

        const container = document.getElementById('existing-users');
        container.innerHTML = '';

        users.forEach(user => {
            const userItem = document.createElement('div');
            userItem.className = 'user-item';
            userItem.textContent = user;

            let pressTimer;

            // 鼠标长按事件
            userItem.addEventListener('mousedown', () => {
                pressTimer = window.setTimeout(() => {
                    // 长按触发删除确认
                    if (confirm(`确定要永久删除用户 "${user}" 吗？此操作不可恢复！`)) {
                        deleteUser(user);
                    }
                }, 1000); // 1秒后触发
            });

            userItem.addEventListener('mouseup', () => {
                clearTimeout(pressTimer);
            });

            userItem.addEventListener('mouseleave', () => {
                clearTimeout(pressTimer);
            });

            // 触摸长按事件 (移动端支持)
            userItem.addEventListener('touchstart', () => {
                pressTimer = window.setTimeout(() => {
                    if (confirm(`确定要永久删除用户 "${user}" 吗？此操作不可恢复！`)) {
                        deleteUser(user);
                    }
                }, 1000);
            });

            userItem.addEventListener('touchend', () => {
                clearTimeout(pressTimer);
            });

            userItem.addEventListener('touchmove', () => {
                clearTimeout(pressTimer);
            });

            // 单击事件
            userItem.addEventListener('click', (e) => {
                // 防止长按后还触发单击
                if (e.detail) { // e.detail > 0 for real clicks
                    selectUser(user);
                }
            });

            container.appendChild(userItem);
        });
    } catch (error) {
        console.error('加载用户列表失败:', error);
    }
}

async function createUser() {
    const username = document.getElementById('new-username').value.trim();
    if (!username) {
        alert('请输入用户名');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/users`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username })
        });

        if (response.ok) {
            await loadUsers();
            document.getElementById('new-username').value = '';
            selectUser(username);
        } else {
            const error = await response.json();
            alert(error.message || '创建用户失败');
        }
    } catch (error) {
        console.error('创建用户失败:', error);
        alert('创建用户失败');
    }
}

async function deleteUser(username) {
    try {
        const response = await fetch(`${API_BASE}/users/${username}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            alert(`用户 "${username}" 已成功删除。`);
            await loadUsers(); // 重新加载用户列表
        } else {
            const error = await response.json();
            alert(error.message || '删除用户失败');
        }
    } catch (error) {
        console.error('删除用户失败:', error);
        alert('删除用户时发生网络错误。');
    }
}

function selectUser(username) {
    currentUser = username;
    localStorage.setItem('currentUser', username);
    pushStateToBackend({ active_user: username });
    document.getElementById('current-username').textContent = username;
    showMainApp();
    loadUserStatistics();
    loadHistoryDashboard();

    // 初始化 AI API 状态
    fetch(`${API_BASE}/users/${username}/settings`)
        .then(res => res.json())
        .then(settings => {
            updateAIApiStatus(!!settings.enable_ai_api, username);
            if (settings.theme) {
                applyTheme(settings.theme, true, false);
            }
            applyCryptoTheme(settings.crypto_theme || currentCryptoTheme, true, false);
            applyTradingHoursFromSettings(settings);
        }).catch(e => console.error(e));
}

async function loadUserStatistics() {
    if (!currentUser) return;

    try {
        const response = await fetch(`${API_BASE}/users/${currentUser}/statistics`);
        const stats = await response.json();

        // 显示用户统计信息
        const statsElement = document.getElementById('user-stats');
        if (statsElement) {
            statsElement.innerHTML = `
                <div class="stat-item">
                    <span>历史总收益:</span>
                    <span class="${stats.avg_return >= 0 ? 'positive' : 'negative'}">${stats.avg_return.toFixed(2)}%</span>
                </div>
                <div class="stat-item">
                    <span>局胜率:</span>
                    <span class="${stats.avg_session_win_rate >= 50 ? 'positive' : 'negative'}">${stats.avg_session_win_rate.toFixed(2)}%</span>
                </div>
                <div class="stat-item">
                    <span>总训练次数:</span>
                    <span>${stats.total_sessions}</span>
                </div>
            `;
        }
    } catch (error) {
        console.error('加载用户统计失败:', error);
    }
}

/**
 * 控制顶部工具栏在训练期间的元素可见性
 * @param {boolean} isTraining - 是否正在进行训练
 */
function toggleToolbarForTraining(isTraining) {
    const elementsToToggle = [
        document.getElementById('switch-user-btn'),
        document.getElementById('theme-toggle-btn'),
        document.getElementById('data-sync-btn'),
        document.getElementById('settings-btn'),
        document.getElementById('new-training-btn'),
        document.getElementById('main-title') // 新增的标题元素
    ];

    elementsToToggle.forEach(el => {
        if (el) { // 确保元素存在
            el.classList.toggle('hidden', isTraining);
        }
    });
    document.getElementById('main-app')?.classList.toggle('training-active', isTraining);
}

/**
 * 重置整个训练环境，回到主应用界面
 * 用于从复盘报告或训练界面返回时，清理所有状态
 */
function resetToMainAppState() {
    const cleanupTrainingId = currentTraining?.id;
    clearSessionDrawings();
    // 1. 暂停任何正在进行的回放
    if (isPlaying) {
        pausePlayback();
    }
    stopAutoSync();
    destroyDrawingTools();

    // 2. 清理图表对象和数据
    if (chart) {
        chart.remove();
        chart = null;
    }
    if (volumeChart) {
        volumeChart.remove();
        volumeChart = null;
    }
    if (indicatorChart) {
        indicatorChart.remove();
        indicatorChart = null;
    }
    // 清空图表容器，确保 Lightweight Charts 的 DOM 被彻底移除
    document.getElementById('chart').innerHTML = '';
    document.getElementById('volume-chart').innerHTML = '';
    const indicatorCanvas = document.getElementById('indicator-canvas');
    if (indicatorCanvas) {
        indicatorCanvas.innerHTML = '';
    }

    // 3. 重置所有图表系列变量
    candlestickSeries = null;
    volumeSeries = null;
    maSeries = {};
    indicatorSeries = null;
    tradeMarkerSeries = null;
    currentIndicatorSeries = [];
    bollSeries = {};
    latestRenderedKlineData = [];
    resetChartWindowState();

    // 4. 清理界面上的动态数据
    // 清理交易记录
    document.getElementById('trade-history').innerHTML = '<div class="no-trades">暂无交易记录</div>';
    // 清理持仓信息
    document.getElementById('current-positions').innerHTML = '<div class="no-positions">暂无持仓</div>';
    // 清理账户信息
    document.getElementById('total-assets').textContent = '¥-';
    document.getElementById('available-cash').textContent = '¥-';
    document.getElementById('position-value').textContent = '¥-';
    document.getElementById('floating-pnl').textContent = '¥-';
    document.getElementById('floating-pnl').style.color = getThemePalette().text;
    
    // reset shift toggle
    isShiftClicked = false;
    isShiftKeyPressed = false;
    if(typeof updatePriceMode === 'function') updatePriceMode();
    document.getElementById('max-buy-quantity').textContent = '0';
    document.getElementById('max-sell-quantity').textContent = '0';
    document.getElementById('trade-quantity').value = '1'; // 重置交易数量
    document.getElementById('sell-quantity').value = '1';
    document.getElementById('trigger-price').value = '';
    document.getElementById('take-profit-price').value = '';
    document.getElementById('stop-loss-price').value = '';
    skipTradeReasonPrompt = false;
    pendingTradeReasonAction = null;
    renderPendingOrders(null);
    setOrderType('market');
    // 清理K线信息
    document.getElementById('stock-name').textContent = '未知股票';
    document.getElementById('current-date').textContent = 'YYYY/MM/DD';
    document.getElementById('current-price').textContent = '¥-.--';
    document.getElementById('current-bar-id').textContent = 'Bar ID: N/A';
    document.getElementById('training-progress').textContent = '进度: -';


    // 5. 重置全局状态变量
    currentTraining = null;
    syncCryptoWorkspaceMode();
    updatePeriodBadge('daily');
    isPlaying = false;
    trainingSetupReturnScreen = 'main';

    // 6. 隐藏所有主要界面，然后显示主应用界面
    document.getElementById('training-interface').classList.add('hidden');
    document.getElementById('report-interface').classList.add('hidden');
    document.getElementById('user-selection').classList.add('hidden');
    document.getElementById('main-app').classList.remove('hidden');

    setTrainingViewOnlyMode(false, { showBackToReport: false });
    document.getElementById('history-dashboard')?.classList.remove('hidden');

    // 清理后端的训练会话
    if (cleanupTrainingId) {
        fetch(`${API_BASE}/training/${cleanupTrainingId}/cleanup`, { method: 'POST' })
            .catch(e => console.error('Cleanup failed:', e));
    }
    
    // Clear current report data and training data
    currentReportData = null;
    currentTraining = null;

    // 7. 确保主界面的工具栏是可见的
    toggleToolbarForTraining(false);
    loadHistoryDashboard();
}

// 界面切换
function showUserSelection() {
    document.getElementById('user-selection').classList.remove('hidden');
    document.getElementById('main-app').classList.add('hidden');
    document.getElementById('training-interface').classList.add('hidden');
    document.getElementById('report-interface').classList.add('hidden');
    currentUser = null;
    localStorage.removeItem('currentUser');
    pushStateToBackend({ active_user: null });
}

function showMainApp() {
    document.getElementById('user-selection').classList.add('hidden');
    document.getElementById('main-app').classList.remove('hidden');
    document.getElementById('history-dashboard')?.classList.remove('hidden');
    document.getElementById('training-interface').classList.add('hidden');
    document.getElementById('report-interface').classList.add('hidden');
    updatePeriodBadge('daily');
    setTrainingViewOnlyMode(false, { showBackToReport: false });

    // 确保按钮和标题是可见的
    toggleToolbarForTraining(false);
    loadHistoryDashboard();
}

async function showTrainingSetup(returnScreen = null) {
    trainingSetupReturnScreen = returnScreen || (document.getElementById('report-interface').classList.contains('hidden') ? 'main' : 'report');
    if (currentUser) {
        try {
            const response = await fetch(`${API_BASE}/users/${currentUser}/settings`);
            const settings = await response.json();
            // 应用默认初始资金，如果不存在则使用100000
            document.getElementById('initial-capital').value = settings.default_initial_capital || 100000;
        } catch (error) {
            console.error('加载用户默认资金失败:', error);
            // 加载失败时使用硬编码的默认值
            document.getElementById('initial-capital').value = 100000;
        }
    }
    document.getElementById('training-setup').classList.remove('hidden');
    setTrainingMarketType(selectedTrainingMarketType);
    // 设置默认日期为一年前
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
    document.getElementById('start-date').value = oneYearAgo.toISOString().split('T')[0];
    const cryptoStart = document.getElementById('crypto-start-time');
    if (cryptoStart && !cryptoStart.value) {
        const local = new Date(oneYearAgo.getTime() - oneYearAgo.getTimezoneOffset() * 60000);
        cryptoStart.value = local.toISOString().slice(0, 16);
    }
}

function hideTrainingSetup() {
    document.getElementById('training-setup').classList.add('hidden');
    trainingSetupReturnScreen = 'main';
}

function showDataSyncModal() {
    const modal = document.getElementById('data-sync-modal');
    if (!modal) return;

    const currentStock = currentTraining?.stock_code || document.getElementById('stock-code')?.value || '';
    const stockInput = document.getElementById('sync-stock-code');
    const startInput = document.getElementById('sync-start-date');
    const endInput = document.getElementById('sync-end-date');
    const sourceSelect = document.getElementById('sync-source');
    const scopeSelect = document.getElementById('sync-scope');
    const forceFull = document.getElementById('sync-force-full');
    const resultBox = document.getElementById('sync-result');
    const progressWrap = document.getElementById('sync-progress-wrap');
    const progressFill = document.getElementById('sync-progress-fill');
    const progressText = document.getElementById('sync-progress-text');

    if (stockInput && currentStock) stockInput.value = currentStock;
    if (startInput && !startInput.value) {
        startInput.value = '2010-01-01';
    }
    if (endInput && !endInput.value) {
        endInput.value = new Date().toISOString().split('T')[0];
    }
    if (sourceSelect && !sourceSelect.value) {
        sourceSelect.value = 'akshare';
    }
    if (forceFull) forceFull.checked = false;
    if (scopeSelect && !scopeSelect.value) {
        scopeSelect.value = 'single';
    }
    if (resultBox) {
        resultBox.classList.add('hidden');
        resultBox.textContent = '';
    }
    if (progressWrap) {
        progressWrap.classList.add('hidden');
    }
    if (progressFill) {
        progressFill.style.width = '0%';
    }
    if (progressText) {
        progressText.textContent = '准备中...';
    }

    updateSyncScopeUI();
    modal.classList.remove('hidden');
}

function hideDataSyncModal() {
    document.getElementById('data-sync-modal')?.classList.add('hidden');
}

function updateSyncScopeUI() {
    const scope = document.getElementById('sync-scope')?.value || 'single';
    const stockInput = document.getElementById('sync-stock-code');
    const stockGroup = stockInput?.closest('.form-group');
    if (stockGroup) {
        stockGroup.classList.toggle('hidden', scope !== 'single');
    }
}

function updateSyncProgress(completed, total, label = '') {
    const progressWrap = document.getElementById('sync-progress-wrap');
    const progressFill = document.getElementById('sync-progress-fill');
    const progressText = document.getElementById('sync-progress-text');
    if (!progressWrap || !progressFill || !progressText) return;

    progressWrap.classList.remove('hidden');
    const percent = total > 0 ? Math.min(100, (completed / total) * 100) : 0;
    progressFill.style.width = `${percent}%`;
    progressText.textContent = label || `${completed}/${total}`;
}

function getSyncThrottleMs(source) {
    if (source === 'xtdata') return 40;
    if (source === 'mootdx') return 240;
    return 260;
}

function getSyncScopeLabel(scope) {
    if (scope === 'sh') return '全沪市';
    if (scope === 'sz') return '全深市';
    if (scope === 'all') return '全市场';
    return '单只股票';
}

function describeSyncRange(startDate, endDate) {
    if (startDate && endDate) {
        return `${startDate} ~ ${endDate}`;
    }
    if (startDate) {
        return `${startDate} 起`;
    }
    if (endDate) {
        return `截至 ${endDate}`;
    }
    return '默认区间';
}

async function syncSingleStock(stockCode, source, startDate, endDate, forceFull) {
    const response = await fetch(`${API_BASE}/data/sync`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            stock_code: stockCode,
            source,
            start_date: startDate || null,
            end_date: endDate || null,
            force_full: forceFull,
        }),
    });
    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.error || '补数失败');
    }
    return result;
}

async function syncOfflineData() {
    const scope = document.getElementById('sync-scope')?.value || 'single';
    const stockCode = document.getElementById('sync-stock-code')?.value.trim();
    const source = document.getElementById('sync-source')?.value || 'akshare';
    const startDate = document.getElementById('sync-start-date')?.value || '';
    const endDate = document.getElementById('sync-end-date')?.value || '';
    const forceFull = !!document.getElementById('sync-force-full')?.checked;
    const resultBox = document.getElementById('sync-result');
    const btn = document.getElementById('confirm-sync-btn');

    if (scope === 'single' && !stockCode) {
        alert('请输入股票代码');
        return;
    }
    if (startDate && endDate && startDate > endDate) {
        alert('结束日期不能早于开始日期');
        return;
    }

    if (btn) btn.disabled = true;
    if (resultBox) {
        resultBox.classList.remove('hidden');
        resultBox.textContent = scope === 'single'
            ? `正在按区间 ${describeSyncRange(startDate, endDate)} 同步离线数据，请稍候...`
            : `正在准备批量补数列表（区间 ${describeSyncRange(startDate, endDate)}）...`;
    }

    try {
        if (scope === 'single') {
            updateSyncProgress(0, 1, '正在同步 1/1');
            const result = await syncSingleStock(stockCode, source, startDate, endDate, forceFull);
            updateSyncProgress(1, 1, '已完成 1/1');
            if (resultBox) {
                resultBox.classList.remove('hidden');
                const beforeRange = result.range_before ? `${result.range_before.start} ~ ${result.range_before.end}` : '无本地数据';
                const afterRange = result.range_after ? `${result.range_after.start} ~ ${result.range_after.end}` : '无数据';
                const plannedRangeText = Array.isArray(result.planned_ranges) && result.planned_ranges.length > 0
                    ? ` 计划补齐 ${result.planned_ranges.map(item => `${item.start} ~ ${item.end}`).join('；')}。`
                    : '';
                const fetchedRangeText = Array.isArray(result.fetched_ranges) && result.fetched_ranges.length > 0
                    ? ` 实际抓取 ${result.fetched_ranges.map(item => `${item.start} ~ ${item.end}`).join('；')}。`
                    : '';
                const missingRangeText = Array.isArray(result.missing_ranges) && result.missing_ranges.length > 0
                    ? ` 在线源未返回 ${result.missing_ranges.map(item => `${item.start} ~ ${item.end}`).join('；')}。`
                    : '';
                const fileStateText = result.local_file_changed === false ? ' 本地文件未改动。' : '';
                resultBox.textContent = `完成: ${result.message} 请求区间 ${describeSyncRange(startDate, endDate)}，本地范围 ${beforeRange} -> ${afterRange}，新增 ${result.added_rows || 0} 条，抓取 ${result.fetched_rows || 0} 条。${plannedRangeText}${fetchedRangeText}${missingRangeText}${fileStateText}`;
            }
        } else {
            const universeResponse = await fetch(`${API_BASE}/data/stock_universe?market=${scope}`);
            const universePayload = await universeResponse.json();
            if (!universeResponse.ok) {
                throw new Error(universePayload.error || '获取股票列表失败');
            }

            const stockCodes = universePayload.stock_codes || [];
            if (stockCodes.length === 0) {
                throw new Error('当前市场没有可补数的股票列表');
            }

            let successCount = 0;
            let failureCount = 0;
            let addedRows = 0;
            let latestSuccessCode = '';
            const throttleMs = getSyncThrottleMs(source);

            for (let index = 0; index < stockCodes.length; index += 1) {
                const code = stockCodes[index];
                updateSyncProgress(index, stockCodes.length, `正在补数 ${index + 1}/${stockCodes.length}：${code}`);
                try {
                    const result = await syncSingleStock(code, source, startDate, endDate, forceFull);
                    successCount += 1;
                    addedRows += result.added_rows || 0;
                    latestSuccessCode = code;
                } catch (error) {
                    failureCount += 1;
                    console.error(`批量补数失败 ${code}:`, error);
                }

                if (index < stockCodes.length - 1) {
                    await sleep(throttleMs);
                }
            }

            updateSyncProgress(stockCodes.length, stockCodes.length, `批量补数完成 ${stockCodes.length}/${stockCodes.length}`);
            if (resultBox) {
                resultBox.classList.remove('hidden');
                resultBox.textContent = `完成: ${getSyncScopeLabel(scope)}区间 ${describeSyncRange(startDate, endDate)}，共 ${stockCodes.length} 只，成功 ${successCount}，失败 ${failureCount}，累计新增 ${addedRows} 条。${latestSuccessCode ? ` 最近成功股票 ${latestSuccessCode}。` : ''}`;
            }
        }
    } catch (error) {
        console.error('离线数据补充失败:', error);
        if (resultBox) {
            resultBox.classList.remove('hidden');
            resultBox.textContent = `失败: ${error.message || '未知错误'}`;
        }
    } finally {
        if (btn) btn.disabled = false;
    }
}

function showSettings() {
    document.getElementById('settings-modal').classList.remove('hidden');
    loadUserSettings();
    loadCryptoOfflineStatus();
}

function renderMaPeriodsEditor() {
    const container = document.getElementById('ma-periods-editor');
    if (!container) return;
    syncMaLineSettingsWithPeriods();
    container.innerHTML = '';

    maPeriods.forEach((p, index) => {
        const tag = document.createElement('div');
        tag.className = 'ma-period-tag';
        const value = document.createElement('span');
        value.className = 'ma-period-value';
        value.textContent = `MA${p}`;

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'ma-period-remove delete-ma';
        removeBtn.dataset.index = String(index);
        removeBtn.setAttribute('aria-label', `删除 MA${p}`);
        removeBtn.textContent = 'x';

        tag.appendChild(value);
        tag.appendChild(removeBtn);
        container.appendChild(tag);
    });

    if (maPeriods.length < 6) {
        const addBtn = document.createElement('button');
        addBtn.className = 'btn-add-ma';
        addBtn.type = 'button';
        addBtn.textContent = '+';
        addBtn.onclick = () => {
            const val = prompt('输入新的均线周期 (如: 60):');
            if (val && !isNaN(val)) {
                const p = parseInt(val);
                if (p > 0 && !maPeriods.includes(p)) {
                    maPeriods.push(p);
                    maPeriods.sort((a, b) => a - b);
                    renderMaPeriodsEditor();
                }
            }
        };
        container.appendChild(addBtn);
    }

    // 删除事件
    container.querySelectorAll('.delete-ma').forEach(btn => {
        btn.onclick = (e) => {
            const idx = parseInt(e.target.dataset.index);
            maPeriods.splice(idx, 1);
            renderMaPeriodsEditor();
        };
    });
}

function hideSettings() {
    document.getElementById('settings-modal').classList.add('hidden');
}

async function loadUserSettings() {
    if (!currentUser) return;

    try {
        const response = await fetch(`${API_BASE}/users/${currentUser}/settings`);
        const settings = await response.json();

        document.getElementById('default-initial-capital').value = settings.default_initial_capital || 100000;
        document.getElementById('commission-rate').value = (settings.commission_rate * 10000).toFixed(1);
        document.getElementById('min-commission').value = settings.min_commission;
        document.getElementById('stamp-tax-rate').value = (settings.stamp_tax_rate * 1000).toFixed(1);
        document.getElementById('theme-select').value = settings.theme || currentTheme;
        applyCryptoTheme(settings.crypto_theme || currentCryptoTheme, true, false);
        applyTradingHoursFromSettings(settings);
        document.getElementById('adjustment-mode').value = 'forward';
        const adjustmentRadio = document.querySelector('input[name="adjustment"][value="forward"]');
        if (adjustmentRadio) {
            adjustmentRadio.checked = true;
        }

        // 加载 AI API 设置
        if (settings.enable_ai_api !== undefined) {
            document.getElementById('enable-ai-api').checked = settings.enable_ai_api;
        } else {
            document.getElementById('enable-ai-api').checked = false;
        }

        // 加载MA周期
        if (settings.ma_periods && Array.isArray(settings.ma_periods)) {
            maPeriods = [...settings.ma_periods];
        } else {
            maPeriods = [10, 20, 40, 80, 160];
        }
        renderMaPeriodsEditor();

        // 加载指标配置
        if (settings.indicators) {
            const ind = settings.indicators;
            if (ind.macd) {
                document.getElementById('macd-fast').value = ind.macd.fast || 10;
                document.getElementById('macd-slow').value = ind.macd.slow || 20;
                document.getElementById('macd-signal').value = ind.macd.signal || 5;
            }
            if (ind.kdj) {
                document.getElementById('kdj-n').value = ind.kdj.n || 9;
                document.getElementById('kdj-m1').value = ind.kdj.m1 || 3;
                document.getElementById('kdj-m2').value = ind.kdj.m2 || 3;
            }
            if (ind.rsi && ind.rsi.periods) {
                document.getElementById('rsi-periods').value = ind.rsi.periods.join(',');
            }
            if (ind.boll) {
                document.getElementById('boll-period').value = ind.boll.period || 20;
                document.getElementById('boll-std-dev').value = ind.boll.std_dev || 2;
            }
        }
    } catch (error) {
        console.error('加载用户设置失败:', error);
    }
}

async function saveSettings() {
    if (!currentUser) return;

    try {
        // 收集指标参数
        const indicators = {
            macd: {
                fast: parseInt(document.getElementById('macd-fast').value) || 10,
                slow: parseInt(document.getElementById('macd-slow').value) || 20,
                signal: parseInt(document.getElementById('macd-signal').value) || 5
            },
            kdj: {
                n: parseInt(document.getElementById('kdj-n').value) || 9,
                m1: parseInt(document.getElementById('kdj-m1').value) || 3,
                m2: parseInt(document.getElementById('kdj-m2').value) || 3
            },
            rsi: {
                periods: document.getElementById('rsi-periods').value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
            },
            boll: {
                period: parseInt(document.getElementById('boll-period').value) || 20,
                std_dev: parseFloat(document.getElementById('boll-std-dev').value) || 2
            }
        };
        if (indicators.rsi.periods.length === 0) indicators.rsi.periods = [6, 12, 24];

        const settings = {
            default_initial_capital: parseInt(document.getElementById('default-initial-capital').value, 10),
            commission_rate: parseFloat(document.getElementById('commission-rate').value) / 10000,
            min_commission: parseFloat(document.getElementById('min-commission').value),
            stamp_tax_rate: parseFloat(document.getElementById('stamp-tax-rate').value) / 1000,
            adjustment_mode: 'forward',
            theme: document.getElementById('theme-select').value,
            enable_ai_api: document.getElementById('enable-ai-api').checked,
            ma_periods: maPeriods,
            indicators: indicators
        };

        const response = await fetch(`${API_BASE}/users/${currentUser}/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            const adjustmentRadio = document.querySelector('input[name="adjustment"][value="forward"]');
            if (adjustmentRadio) {
                adjustmentRadio.checked = true;
            }

            // 更新 AI 接口信息
            updateAIApiStatus(settings.enable_ai_api, currentUser);
            applyTheme(settings.theme, true, false);

            hideSettings();
            alert('设置保存成功');
        } else {
            alert('设置保存失败');
        }
    } catch (error) {
        console.error('保存设置失败:', error);
        alert('保存设置失败');
    }
}

function switchTab(tabName) {
    // 更新标签按钮状态
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // 更新标签内容显示
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tabName}-tab`);
    });
}

function setTrainingMarketType(marketType) {
    selectedTrainingMarketType = marketType === CRYPTO_MARKET_TYPE ? CRYPTO_MARKET_TYPE : 'a_share';
    const crypto = selectedTrainingMarketType === CRYPTO_MARKET_TYPE;
    document.querySelectorAll('.market-type-btn').forEach((button) => {
        button.classList.toggle('active', button.dataset.marketType === selectedTrainingMarketType);
    });
    document.querySelectorAll('.a-share-market-field').forEach((element) => element.classList.toggle('hidden', crypto));
    document.querySelectorAll('.crypto-market-field').forEach((element) => element.classList.toggle('hidden', !crypto));
    document.getElementById('crypto-market-fields')?.classList.toggle('hidden', !crypto);
    document.getElementById('sector-filter')?.closest('.form-group')?.classList.toggle('hidden', crypto);

    const periodSelect = document.getElementById('kline-period');
    periodSelect?.querySelectorAll('option').forEach((option) => {
        const allowed = crypto ? option.dataset.cryptoPeriod : option.dataset.aSharePeriod;
        option.hidden = !allowed;
        option.disabled = !allowed;
    });
    if (periodSelect && !supportedReplayPeriods().includes(periodSelect.value)) {
        periodSelect.value = crypto ? '1m' : 'daily';
    }

    const limitLabel = document.querySelector('label[for="max-training-bars"]');
    const limitHelp = document.getElementById('training-day-limit-help');
    if (limitLabel) limitLabel.textContent = crypto ? '训练自然日限制（0=不限制）' : '训练交易日限制（0=不限制）';
    if (limitHelp) {
        limitHelp.textContent = crypto
            ? '按UTC自然日统计，市场全天候运行；界面时间显示为UTC+8。'
            : '按实际交易日期统计，不是30分钟K线根数，也不是当前显示周期K线根数。';
    }
}

function syncCryptoWorkspaceMode() {
    scheduleTradingHoursBandsUpdate();
    const active = isCryptoMode();
    const mainApp = document.getElementById('main-app');
    mainApp?.classList.toggle('crypto-training-active', active);
    document.getElementById('training-interface')?.classList.toggle('crypto-workspace-active', active);
    document.querySelectorAll('[data-crypto-workspace-only]').forEach((element) => {
        element.classList.toggle('hidden', !active);
    });
    document.querySelectorAll('[data-a-share-workspace-only]').forEach((element) => {
        element.classList.toggle('hidden', active);
    });
    document.querySelectorAll('[data-ashare-live-only]').forEach((element) => {
        element.classList.add('hidden');
    });
    if (active) {
        applyCryptoTheme(currentCryptoTheme, false, false);
        applyCryptoConsoleLayout(readCryptoConsoleLayout());
        showLatestChartInfo();
    } else {
        mainApp?.classList.remove('crypto-console-collapsed');
        mainApp?.style.removeProperty('--crypto-console-width');
        applyChartTheme();
    }
}

function selectCryptoOrderAction(action, updateSelect = true) {
    const select = document.getElementById('crypto-order-action');
    if (!select || !['open_long', 'open_short', 'close'].includes(action)) return;
    if (updateSelect) select.value = action;
    document.querySelectorAll('[data-crypto-action]').forEach((button) => {
        button.classList.toggle('active', button.dataset.cryptoAction === action);
        button.setAttribute('aria-pressed', String(button.dataset.cryptoAction === action));
    });
    // 平仓时隐藏止盈止损
    const tpslSection = document.querySelector('.crypto-tpsl-section');
    if (tpslSection) tpslSection.classList.toggle('hidden', action === 'close');
    if (action === 'close') {
        const checkbox = document.getElementById('crypto-tpsl-enabled');
        if (checkbox) checkbox.checked = false;
        document.getElementById('crypto-tpsl-fields')?.classList.add('hidden');
    }
    updateCryptoPriceShortcuts();
    refreshCryptoMarginFraction();
    refreshCryptoOrderPreview();
    refreshCryptoTpSlPnl();
}

function toggleChartPanel(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    if (panelId === 'indicator-chart') {
        if (indicatorPanelVisible && !panel.classList.contains('panel-collapsed')) {
            indicatorPanelVisible = false;
            panel.classList.add('panel-collapsed');
        } else {
            indicatorPanelVisible = true;
            panel.classList.remove('panel-collapsed');
            if (!activeSubcharts.length) activeSubcharts = ['macd'];
            renderSubchartsDOM();
            loadTechnicalIndicators();
        }
        const collapsed = !indicatorPanelVisible;
        const button = document.querySelector('[aria-controls="' + panelId + '"]');
        button?.classList.toggle('active', !collapsed);
        button?.setAttribute('aria-expanded', String(!collapsed));
    } else {
        const collapsed = panel.classList.toggle('panel-collapsed');
        const button = document.querySelector('[aria-controls="' + panelId + '"]');
        button?.classList.toggle('active', !collapsed);
        button?.setAttribute('aria-expanded', String(!collapsed));
    }
    requestAnimationFrame(() => {
        applyChartPanelRatios(readChartPanelRatios());
        resizeCharts();
    });
}

function setChartFocusMode(enabled) {
    const mainApp = document.getElementById('main-app');
    if (!mainApp) return;
    const active = Boolean(enabled);
    mainApp.classList.toggle('chart-focus-mode', active);
    document.body.classList.toggle('chart-focus-active', active);
    const toggleButton = document.getElementById('chart-fullscreen-btn');
    toggleButton?.classList.toggle('active', active);
    toggleButton?.setAttribute('aria-pressed', String(active));
    if (toggleButton) {
        toggleButton.textContent = active ? '退出全屏' : '全屏';
        toggleButton.title = active ? '退出全屏 (ESC)' : '全屏图表';
    }
    document.getElementById('chart-focus-exit-btn')?.classList.toggle('hidden', !active);
    requestAnimationFrame(() => {
        applyChartPanelRatios(readChartPanelRatios());
        resizeCharts();
    });
    setTimeout(() => {
        applyChartPanelRatios(readChartPanelRatios());
        resizeCharts();
    }, 60);
}

function toggleChartFullscreen() {
    const mainApp = document.getElementById('main-app');
    if (!mainApp) return;
    setChartFocusMode(!mainApp.classList.contains('chart-focus-mode'));
}

function renderCryptoInstrumentResults(instruments) {
    const container = document.getElementById('crypto-symbol-results');
    if (!container) return;
    container.replaceChildren();
    (Array.isArray(instruments) ? instruments : []).forEach((instrument) => {
        const symbol = instrument.symbol || instrument.code;
        if (!symbol) return;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'crypto-symbol-option';
        button.dataset.symbol = symbol;
        button.innerHTML = '<strong>' + symbol + '</strong><span>' + (instrument.source || '') + '</span>';
        button.addEventListener('click', () => {
            selectedCryptoInstrument = instrument;
            const input = document.getElementById('crypto-symbol-search');
            if (input) input.value = symbol;
            container.replaceChildren();
        });
        container.appendChild(button);
    });
}

async function searchCryptoInstruments(query) {
    const text = String(query || '').trim().toUpperCase();
    if (text.length < 2) {
        renderCryptoInstrumentResults([]);
        return [];
    }
    const response = await fetch(API_BASE + '/crypto/instruments?query=' + encodeURIComponent(text) + '&limit=20');
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || '币圈合约搜索失败');
    const instruments = payload.instruments || payload;
    renderCryptoInstrumentResults(instruments);
    return instruments;
}

function normalizeCryptoSymbol(value) {
    const symbol = String(value || '').trim().toUpperCase().replace(/[\s/_-]+/g, '');
    return symbol && !symbol.endsWith('USDT') && !symbol.endsWith('USDC') ? symbol + 'USDT' : symbol;
}

function getCryptoHistoryYears() {
    const input = document.getElementById('crypto-history-years');
    const historyYears = Number(input?.value ?? 2);
    if (!Number.isInteger(historyYears) || historyYears < 2 || historyYears > 5) {
        throw new Error('训练前历史年数必须是 2 到 5 之间的整数');
    }
    return historyYears;
}

function setCryptoHistoryPrepareProgress(payload = {}) {
    const completedMonths = Number(payload.completed_months ?? payload.completed ?? payload.progress?.completed ?? 0) || 0;
    const totalMonths = Number(payload.total_months ?? payload.total ?? payload.progress?.total ?? 0) || 0;
    const explicitPercent = Number(payload.percent ?? payload.progress?.percent);
    const percent = Number.isFinite(explicitPercent)
        ? Math.max(0, Math.min(100, explicitPercent))
        : (totalMonths > 0 ? Math.max(0, Math.min(100, completedMonths / totalMonths * 100)) : 0);
    const currentMonth = payload.current_month || payload.month || '--';
    const statusText = payload.message || payload.status_text || '正在检查离线缓存并补齐缺失月份...';
    const status = document.getElementById('crypto-history-prepare-status');
    const month = document.getElementById('crypto-history-prepare-month');
    const count = document.getElementById('crypto-history-prepare-count');
    const percentText = document.getElementById('crypto-history-prepare-percent');
    const progress = document.getElementById('crypto-history-prepare-progress');
    if (status) status.textContent = statusText;
    if (month) month.textContent = String(currentMonth);
    if (count) count.textContent = `${completedMonths} / ${totalMonths}`;
    if (percentText) percentText.textContent = `${Math.round(percent)}%`;
    if (progress) progress.style.width = `${percent}%`;
}

function showCryptoHistoryPrepareModal(trainingConfig) {
    cryptoHistoryPrepareRetryConfig = { ...trainingConfig };
    document.getElementById('crypto-history-prepare-modal')?.classList.remove('hidden');
    document.getElementById('retry-crypto-history-prepare-btn')?.classList.add('hidden');
    const cancelButton = document.getElementById('cancel-crypto-history-prepare-btn');
    if (cancelButton) cancelButton.textContent = '取消';
    const errorBox = document.getElementById('crypto-history-prepare-error');
    if (errorBox) {
        errorBox.textContent = '';
        errorBox.classList.add('hidden');
    }
    setCryptoHistoryPrepareProgress();
}

function hideCryptoHistoryPrepareModal() {
    document.getElementById('crypto-history-prepare-modal')?.classList.add('hidden');
}

function showCryptoHistoryPrepareFailure(message, status = 'failed') {
    const actionableMessage = status === 'cancelled'
        ? '历史数据准备已取消。你可以修改参数后重试。'
        : (message || '历史数据准备失败，请重试。');
    const statusElement = document.getElementById('crypto-history-prepare-status');
    const errorBox = document.getElementById('crypto-history-prepare-error');
    if (statusElement) statusElement.textContent = status === 'cancelled' ? '准备任务已取消' : '准备历史数据失败';
    if (errorBox) {
        errorBox.textContent = actionableMessage;
        errorBox.classList.remove('hidden');
    }
    document.getElementById('retry-crypto-history-prepare-btn')?.classList.remove('hidden');
    const cancelButton = document.getElementById('cancel-crypto-history-prepare-btn');
    if (cancelButton) cancelButton.textContent = '关闭';
}

async function pollCryptoHistoryPreparation(jobId, signal) {
    while (true) {
        const response = await fetch(`${API_BASE}/crypto/history/prepare/${encodeURIComponent(jobId)}`, { signal });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || payload.message || `查询历史准备进度失败: ${response.status}`);
        setCryptoHistoryPrepareProgress({
            ...payload,
            current_month: payload.current_month,
            completed_months: payload.completed_months,
            total_months: payload.total_months,
        });
        const status = String(payload.status || '').toLowerCase();
        if (status === 'ready' || status === 'completed') return { ...payload, job_id: payload.job_id || jobId };
        if (status === 'failed') throw new Error(payload.error || payload.message || '历史数据准备失败');
        if (status === 'cancelled') {
            const error = new Error(payload.message || '历史数据准备已取消');
            error.name = 'AbortError';
            throw error;
        }
        await new Promise((resolve) => setTimeout(resolve, 700));
    }
}

async function prepareCryptoHistory(trainingConfig) {
    showCryptoHistoryPrepareModal(trainingConfig);
    cryptoHistoryPrepareAbortController?.abort();
    cryptoHistoryPrepareAbortController = new AbortController();
    cryptoHistoryPrepareJobId = null;
    try {
        const prepareConfig = { ...trainingConfig };
        delete prepareConfig.history_prepare_id;
        const response = await fetch(`${API_BASE}/crypto/history/prepare`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(prepareConfig),
            signal: cryptoHistoryPrepareAbortController.signal,
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || payload.message || `创建历史准备任务失败: ${response.status}`);
        cryptoHistoryPrepareJobId = payload.job_id;
        if (!cryptoHistoryPrepareJobId) throw new Error('历史准备任务未返回 job_id');
        setCryptoHistoryPrepareProgress(payload);
        return await pollCryptoHistoryPreparation(cryptoHistoryPrepareJobId, cryptoHistoryPrepareAbortController.signal);
    } catch (error) {
        if (error?.name !== 'AbortError') {
            showCryptoHistoryPrepareFailure(error.message, 'failed');
            error.cryptoHistoryHandled = true;
        }
        throw error;
    } finally {
        cryptoHistoryPrepareAbortController = null;
    }
}

async function cancelCryptoHistoryPreparation() {
    const jobId = cryptoHistoryPrepareJobId;
    const retryButton = document.getElementById('retry-crypto-history-prepare-btn');
    if (!cryptoHistoryPrepareAbortController && retryButton && !retryButton.classList.contains('hidden')) {
        cryptoHistoryPrepareJobId = null;
        hideCryptoHistoryPrepareModal();
        return;
    }
    if (!jobId && !cryptoHistoryPrepareAbortController) {
        hideCryptoHistoryPrepareModal();
        return;
    }
    cryptoHistoryPrepareAbortController?.abort();
    cryptoHistoryPrepareAbortController = null;
    cryptoHistoryPrepareJobId = null;
    if (jobId) {
        try {
            await fetch(`${API_BASE}/crypto/history/prepare/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
        } catch (error) {
            console.error('取消币圈历史准备任务失败:', error);
        }
    }
    showCryptoHistoryPrepareFailure('', 'cancelled');
}

async function retryCryptoHistoryPreparation() {
    if (!cryptoHistoryPrepareRetryConfig) return;
    try {
        await startCryptoTrainingWithHistoryPreparation({ ...cryptoHistoryPrepareRetryConfig });
    } catch (error) {
        if (error?.name !== 'AbortError' && !error?.cryptoHistoryHandled) {
            showCryptoHistoryPrepareFailure(error.message, 'failed');
        }
    }
}

async function startCryptoTrainingWithHistoryPreparation(trainingConfig) {
    const prepared = await prepareCryptoHistory(trainingConfig);
    const historyPrepareId = prepared.job_id || cryptoHistoryPrepareJobId;
    if (!historyPrepareId) throw new Error('币圈历史数据准备结果无效，请重试');
    hideCryptoHistoryPrepareModal();
    return startTrainingWithConfig({
        ...trainingConfig,
        history_prepare_id: historyPrepareId,
    });
}

function buildCryptoStartPayload(isRandomMode) {
    const symbolInput = document.getElementById('crypto-symbol-search');
    const startTimeInput = document.getElementById('crypto-start-time');
    const makerRate = parseFloat(document.getElementById('modal-crypto-maker-fee-rate')?.value ?? document.getElementById('crypto-maker-fee-rate')?.value ?? '0');
    const takerRate = parseFloat(document.getElementById('modal-crypto-taker-fee-rate')?.value ?? document.getElementById('crypto-taker-fee-rate')?.value ?? '0');
    const payload = {
        user: currentUser,
        market_type: CRYPTO_MARKET_TYPE,
        data_mode: CRYPTO_DATA_MODE,
        mode: isRandomMode ? 'random' : 'specified',
        data_source: 'auto',
        period: getSelectedKlinePeriod(),
        max_training_days: parseInt(document.getElementById('max-training-bars')?.value) || 0,
        initial_capital: parseFloat(document.getElementById('crypto-initial-capital')?.value) || 10000,
        leverage: parseInt(document.getElementById('crypto-leverage')?.value) || 5,
        history_years: getCryptoHistoryYears(),
        maker_fee_rate: Number.isFinite(makerRate) && makerRate >= 0 ? makerRate / 100 : 0,
        taker_fee_rate: Number.isFinite(takerRate) && takerRate >= 0 ? takerRate / 100 : 0,
    };
    if (isRandomMode) {
        payload.date_start = document.getElementById('random-start-date').value.trim();
        payload.date_end = document.getElementById('random-end-date').value.trim();
    } else {
        payload.symbol = normalizeCryptoSymbol(selectedCryptoInstrument?.symbol || symbolInput?.value || '');
        payload.start_time = startTimeInput?.value || '';
        if (!payload.symbol || !payload.start_time) throw new Error('请选择合约并填写起始时间');
    }
    return payload;
}

function replaceRenderedKlineData(klineData, volumeData) {
    latestRenderedKlineData = Array.isArray(klineData) ? klineData.map(item => ({ ...item })) : [];
    if (Array.isArray(volumeData)) {
        latestRenderedVolumeData = volumeData.map(item => ({ ...item }));
    }
    syncDrawingToolBars();
    if ((isCryptoMode() || isAshareLiveMode) && maVisible) updateMaLinesFromRendered();
    applyLastPriceTagColor();
    showLatestChartInfo();
    updateChartTradePriceLines();
    scheduleExtremePriceTagsUpdate();
}

function upsertRenderedBar(bar, volBar) {
    if (!bar) return;
    if (volBar && Array.isArray(latestRenderedVolumeData)) {
        const lastVol = latestRenderedVolumeData[latestRenderedVolumeData.length - 1];
        if (lastVol && lastVol.time === volBar.time) {
            latestRenderedVolumeData[latestRenderedVolumeData.length - 1] = { ...volBar };
        } else {
            latestRenderedVolumeData.push({ ...volBar });
        }
    }
    if (latestRenderedKlineData.length === 0) {
        latestRenderedKlineData = [{ ...bar }];
        syncDrawingToolBars();
        if ((isCryptoMode() || isAshareLiveMode) && maVisible) updateMaLinesFromRendered();
        applyLastPriceTagColor();
        showLatestChartInfo();
        updateChartTradePriceLines();
        scheduleExtremePriceTagsUpdate();
        return;
    }

    const lastBar = latestRenderedKlineData[latestRenderedKlineData.length - 1];
    if (lastBar.time === bar.time) {
        latestRenderedKlineData[latestRenderedKlineData.length - 1] = { ...bar };
        syncDrawingToolBars();
        if ((isCryptoMode() || isAshareLiveMode) && maVisible) updateMaLinesFromRendered();
        applyLastPriceTagColor();
        showLatestChartInfo();
        updateChartTradePriceLines();
        scheduleExtremePriceTagsUpdate();
        return;
    }

    latestRenderedKlineData.push({ ...bar });
    syncDrawingToolBars();
    if ((isCryptoMode() || isAshareLiveMode) && maVisible) updateMaLinesFromRendered();
    applyLastPriceTagColor();
    showLatestChartInfo();
    updateChartTradePriceLines();
    scheduleExtremePriceTagsUpdate();
}

function syncDrawingToolBars() {
    if (!drawingController) return;
    if (typeof drawingController.setBars === 'function') {
        drawingController.setBars(latestRenderedKlineData);
    }
    if (typeof drawingController.requestUpdate === 'function') {
        drawingController.requestUpdate();
    }
}

function destroyDrawingTools() {
    if (drawingUiAbortController) {
        drawingUiAbortController.abort();
        drawingUiAbortController = null;
    }
    if (drawingController && typeof drawingController.destroy === 'function') {
        drawingController.destroy();
    }
    drawingController = null;
}

function setDrawingStatus(message = '', state = '') {
    const element = document.getElementById('drawing-status') || document.getElementById('chart-window-status');
    if (!element) return;
    element.textContent = message;
    element.dataset.state = state;
}

function setDrawingInteractionState(active) {
    document.getElementById('chart-panels')?.classList.toggle('drawing-interacting', !!active);
    chart?.applyOptions?.({
        handleScroll: !active,
        handleScale: !active,
    });
}

// 画图工具快捷键映射（Alt+* 层，TradingView 惯例；与裸键交易/回放层通过修饰键物理隔离）
const DRAWING_TOOL_SHORTCUTS = {
    q: 'select', t: 'trend', h: 'horizontal', r: 'ray', b: 'rectangle',
    x: 'text', f: 'fibonacci', m: 'ruler', l: 'long', s: 'short', z: 'polyline'
};
const DRAWING_TOOL_LABELS = {
    select: '选择', trend: '趋势线', horizontal: '水平线', ray: '射线', rectangle: '矩形区间',
    text: '文字标注', fibonacci: '斐波那契回撤', 'fib-trend-time': '斐波那契趋势时间',
    ruler: '量尺', long: '做多测算', short: '做空测算', polyline: '连续折线'
};
const DRAWING_TOOL_KEY_HINTS = {
    select: 'Alt+Q', trend: 'Alt+T', horizontal: 'Alt+H', ray: 'Alt+R', rectangle: 'Alt+B',
    text: 'Alt+X', fibonacci: 'Alt+F', ruler: 'Alt+M', long: 'Alt+L', short: 'Alt+S', polyline: 'Alt+Z'
};

/**
 * 激活画图工具（鼠标点击工具条按钮与键盘 Alt+* 快捷键共用的唯一入口）。
 * 包含：控制器激活、工具条高亮同步、状态条提示（含快捷键提示）、
 * 斐波那契趋势时间特例（弹出档位图例面板）。
 */
function activateDrawingTool(tool) {
    try {
        drawingController?.activateTool?.(tool);
        syncDrawingToolbarState(tool);
        const label = DRAWING_TOOL_LABELS[tool] || tool;
        const hint = DRAWING_TOOL_KEY_HINTS[tool];
        setDrawingStatus(
            tool === 'select'
                ? '选择并拖动已有图形。'
                : `${label}${hint ? ` (${hint})` : ''} 已激活：按住并拖动鼠标创建图形。`,
            'active'
        );
    } catch (error) {
        setDrawingStatus(error?.message || '无法启用画线工具。', 'error');
        syncDrawingToolbarState(null);
    }
    // 画图工具激活时不再自动弹出设置面板，避免遮挡 K 线。
    // 设置仅在选中已有对象后通过浮动工具条的"设置"按钮进入。
    // 例外：斐波那契趋势时间激活时弹出档位图例面板（对齐 AiCoin 顶部彩色图例条）。
    if (tool === 'fib-trend-time') {
        const fibPanel = document.getElementById('drawing-fibonacci-settings');
        if (fibPanel) {
            fibPanel.classList.remove('hidden');
            renderFibonacciSettingsPanel();
        }
    }
}

function syncDrawingToolbarState(tool = null) {
    document.querySelectorAll('[data-drawing-tool]').forEach((button) => {
        const aliases = { 'long-position': 'long', 'short-position': 'short' };
        const active = (aliases[button.dataset.drawingTool] || button.dataset.drawingTool) === tool;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
    });
}

function clearSessionDrawings() {
    clearChartTradePriceLines();
    drawingController?.resetAll?.();
    drawingController?.cancelGesture?.();
    setDrawingInteractionState(false);
    syncDrawingToolbarState(null);
    setDrawingStatus('');
}

function syncDrawingToolbarHideButton() {
    const btn = document.querySelector('#drawing-toolbar [data-drawing-action="hide"]');
    if (!btn || !drawingController) return;
    const allHidden = typeof drawingController.areAllHidden === 'function' ? drawingController.areAllHidden() : false;
    btn.classList.toggle('active', allHidden);
    btn.setAttribute('aria-pressed', String(allHidden));
    btn.title = allHidden ? '显示所有画线 (当前已全部隐藏)' : '隐藏所有画线';
    btn.setAttribute('aria-label', allHidden ? '显示所有画线 (当前已全部隐藏)' : '隐藏所有画线');
}

function handleDrawingHideAction(source) {
    // 如果是从浮动工具条触发且存在选中对象，针对当前选中的单个画线进行隐藏/显示切换
    if (source === 'floating' && drawingController.selectedId) {
        drawingController.toggleHidden();
        const selectedId = drawingController.selectedId;
        const afterModel = selectedId ? drawingController.store.get(selectedId) : null;
        syncDrawingFloatingToolbar(selectedId, afterModel);
        syncDrawingToolbarHideButton();
        setDrawingStatus(
            afterModel && afterModel.hidden
                ? '👁️ 已隐藏该画线（可在浮动工具栏或左侧点击恢复）'
                : '👁️ 已恢复显示该画线',
            'active'
        );
        return;
    }
    // 如果是从左侧工具栏触发的（或未选中特定画线时），执行全局"隐藏所有画线 / 恢复显示所有画线"
    if (!drawingController.store || drawingController.store.size === 0) {
        setDrawingStatus('当前图表上暂无画线', 'info');
        syncDrawingToolbarHideButton();
        return;
    }
    const isHidden = typeof drawingController.toggleAllHidden === 'function'
        ? drawingController.toggleAllHidden()
        : false;
    syncDrawingToolbarHideButton();
    syncDrawingFloatingToolbar(null, null);
    setDrawingStatus(
        isHidden ? '👁️ 已隐藏所有画线（再次点击恢复显示）' : '👁️ 已恢复显示所有画线',
        'active'
    );
}

function invokeDrawingAction(action, source = 'toolbar') {
    if (!drawingController) return;
    if (action === 'settings') {
        const selectedId = drawingController.selectedId;
        const model = selectedId ? drawingController.store.get(selectedId) : null;
        if (!model) {
            setDrawingStatus('请先选中一个画图对象。', 'active');
            return;
        }
        openSelectedDrawingSettingsPanel(model);
        return;
    }
    if (action === 'sync-order') {
        syncDrawingToOrderPanel();
        return;
    }
    if (action === 'magnet') {
        const enabled = drawingController.toggleMagnet();
        const magnetBtn = document.getElementById('drawing-magnet-btn');
        if (magnetBtn) {
            magnetBtn.classList.toggle('active', enabled);
            magnetBtn.setAttribute('aria-pressed', String(enabled));
        }
        setDrawingStatus(enabled ? '🧲 磁吸模式已开启（吸附 OHLC 极值点）' : '磁吸模式已关闭', 'active');
        return;
    }
    if (action === 'hide') {
        handleDrawingHideAction(source);
        return;
    }
    const methodMap = {
        lock: 'toggleLock',
        delete: 'deleteSelected',
        undo: 'undo',
        redo: 'redo',
        clear: 'clearAll',
    };
    const method = methodMap[action];
    if (method && typeof drawingController[method] === 'function') drawingController[method]();

    syncDrawingToolbarHideButton();

    // 锁定/删除后立即回刷状态：控制器只在"选中变化"时通知上层，
    // 这里补一次显式同步，保证图标高亮与提示文案立刻反映真实状态。
    if (action === 'lock' || action === 'delete') {
        const selectedId = drawingController.selectedId;
        const model = selectedId ? drawingController.store.get(selectedId) : null;
        syncDrawingFloatingToolbar(selectedId, model);
        if (action === 'lock') {
            setDrawingStatus(
                model && model.locked
                    ? '🔒 已锁定：该图形不可拖动/缩放（仅对这一个图形生效）'
                    : '🔓 已解锁：可拖动/缩放',
                'active'
            );
        }
    }
}

function collectFibonacciLevelRows() {
    return Array.from(document.querySelectorAll('#drawing-fibonacci-levels .drawing-level-row')).map((row) => ({
        value: Number(row.querySelector('[data-fibonacci-field="value"]')?.value || 0),
        color: row.querySelector('[data-fibonacci-field="color"]')?.value || '#7c3aed',
        enabled: !!row.querySelector('[data-fibonacci-field="enabled"]')?.checked,
    }));
}

function applyFibonacciRowsToSelection() {
    drawingController?.updateSelectedFibonacciSettings?.({ levels: collectFibonacciLevelRows() });
}

function renderFibonacciSettingsPanel() {
    const container = document.getElementById('drawing-fibonacci-levels');
    if (!container) return;
    const selected = drawingController?.getSelectedFibonacciSettings?.();
    let fallbackLevels = window.KLineDrawingTools?.resetFibonacciLevels?.() || [];
    if (!selected && drawingController?.activeTool === 'fib-trend-time') {
        fallbackLevels = window.KLineDrawingTools?.resetFibTrendTimeLevels?.() || fallbackLevels;
    }
    const settings = selected || { levels: fallbackLevels, reverse: false };
    container.replaceChildren();
    settings.levels.forEach((level, index) => {
        const row = document.createElement('div');
        row.className = 'drawing-level-row';
        const enabled = document.createElement('input');
        enabled.type = 'checkbox';
        enabled.checked = level.enabled !== false;
        enabled.dataset.fibonacciField = 'enabled';
        enabled.setAttribute('aria-label', '启用第 ' + (index + 1) + ' 个斐波那契档位');
        const value = document.createElement('input');
        value.type = 'number';
        value.step = '0.001';
        value.value = Number(level.value);
        value.dataset.fibonacciField = 'value';
        value.setAttribute('aria-label', '第 ' + (index + 1) + ' 个斐波那契档位数值');
        const color = document.createElement('input');
        color.type = 'color';
        color.value = level.color || '#7c3aed';
        color.dataset.fibonacciField = 'color';
        color.setAttribute('aria-label', '第 ' + (index + 1) + ' 个斐波那契档位颜色');
        const up = document.createElement('button');
        up.setAttribute('aria-label', '上移第 ' + (index + 1) + ' 个档位');
        up.type = 'button'; up.textContent = '↑'; up.disabled = index === 0;
        const down = document.createElement('button');
        down.setAttribute('aria-label', '下移第 ' + (index + 1) + ' 个档位');
        down.type = 'button'; down.textContent = '↓'; down.disabled = index === settings.levels.length - 1;
        const remove = document.createElement('button');
        remove.setAttribute('aria-label', '删除第 ' + (index + 1) + ' 个档位');
        remove.type = 'button'; remove.textContent = '×';
        enabled.addEventListener('change', applyFibonacciRowsToSelection);
        value.addEventListener('change', applyFibonacciRowsToSelection);
        color.addEventListener('input', applyFibonacciRowsToSelection);
        up.addEventListener('click', () => {
            drawingController?.reorderFibonacciLevel?.(index, index - 1);
            renderFibonacciSettingsPanel();
        });
        down.addEventListener('click', () => {
            drawingController?.reorderFibonacciLevel?.(index, index + 1);
            renderFibonacciSettingsPanel();
        });
        remove.addEventListener('click', () => {
            drawingController?.removeFibonacciLevel?.(index);
            renderFibonacciSettingsPanel();
        });
        row.append(enabled, value, color, up, down, remove);
        container.appendChild(row);
    });
    const reverse = document.getElementById('drawing-fibonacci-reverse');
    if (reverse) reverse.checked = !!settings.reverse;
}

/**
 * 渲染通用线条设置面板（horizontal/trend/ray/ruler/polyline）。
 */
function renderLineSettingsPanel(model) {
    const settings = drawingController?.getSelectedLineSettings?.();
    if (!settings) return;
    const selectedModel = model || (drawingController?.selectedId && drawingController?.store?.get?.(drawingController?.selectedId));
    const type = selectedModel ? selectedModel.type : 'trend';

    // 动态调整面板标题，使各种线条设置更清晰合理
    const headerTitle = document.querySelector('#drawing-line-settings .drawing-settings-header strong');
    if (headerTitle) {
        const titleMap = {
            'polyline': '折线设置',
            'horizontal': '水平线设置',
            'ray': '射线设置',
            'trend': '趋势线设置',
            'ruler': '测算尺设置',
        };
        headerTitle.textContent = titleMap[type] || '线条设置';
    }

    const color = document.getElementById('drawing-line-color');
    const width = document.getElementById('drawing-line-width');
    const style = document.getElementById('drawing-line-style');
    const label = document.getElementById('drawing-line-label-visible');
    if (color) color.value = settings.color || '#2962ff';
    if (width) width.value = settings.lineWidth ?? 1;
    if (style) style.value = settings.lineStyle || 'solid';
    if (label) {
        label.checked = settings.labelVisible !== false;
        // 折线与测算尺没有单点价格标签，隐藏价格标签选项；水平线/射线/趋势线则保留
        const labelRow = label.closest('label');
        if (labelRow) {
            labelRow.style.display = (type === 'polyline' || type === 'ruler') ? 'none' : '';
        }
    }
}

/**
 * 渲染矩形设置面板（线条字段 +填充颜色/透明度）。
 */
function renderRectangleSettingsPanel() {
    const settings = drawingController?.getSelectedLineSettings?.();
    if (!settings) return;
    const setVal = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.value = value;
    };
    const setCheck = (id, checked) => {
        const el = document.getElementById(id);
        if (el) el.checked = !!checked;
    };
    setVal('drawing-rect-color', settings.color || '#2962ff');
    setVal('drawing-rect-fill', settings.fillColor || '#2962ff');
    setVal('drawing-rect-opacity', settings.fillOpacity ?? 0.12);
    setVal('drawing-rect-width', settings.lineWidth ?? 1);
    setVal('drawing-rect-style', settings.lineStyle || 'solid');
}

/**
 * 渲染文字标注设置面板。
 */
function renderTextSettingsPanel() {
    const settings = drawingController?.getSelectedLineSettings?.();
    if (!settings) return;
    const setVal = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.value = value;
    };
    setVal('drawing-text-content', settings.text || 'Text');
    setVal('drawing-text-color', settings.color || '#f0b90b');
    setVal('drawing-text-size', settings.fontSize ?? 14);
}

/**
 * 渲染持仓测算设置面板（账户风险比例）。
 */
function renderPositionSettingsPanel() {
    const model = drawingController?.store?.get?.(drawingController?.selectedId);
    if (!model) return;
    const riskInput = document.getElementById('drawing-pos-risk');
    if (riskInput) {
        const current = drawingController?.accountRiskPercent ?? 1;
        riskInput.value = current;
    }
}

/**
 * 绑定各类型设置面板的"应用/关闭"事件（一次性绑定）。
 */
let drawingSettingPanelsBound = false;
function bindDrawingSettingPanels() {
    if (drawingSettingPanelsBound) return;
    drawingSettingPanelsBound = true;
    const bind = (id, event, handler) => {
        document.getElementById(id)?.addEventListener(event, handler);
    };

    // 通用线条
    bind('drawing-line-color', 'input', () => {
        drawingController?.updateSelectedLineSettings?.({ color: document.getElementById('drawing-line-color').value });
    });
    bind('drawing-line-width', 'change', () => {
        drawingController?.updateSelectedLineSettings?.({ lineWidth: Number(document.getElementById('drawing-line-width').value) });
    });
    bind('drawing-line-style', 'change', () => {
        drawingController?.updateSelectedLineSettings?.({ lineStyle: document.getElementById('drawing-line-style').value });
    });
    bind('drawing-line-label-visible', 'change', () => {
        drawingController?.updateSelectedLineSettings?.({ labelVisible: document.getElementById('drawing-line-label-visible').checked });
    });
    document.querySelectorAll('[data-line-action]').forEach((btn) => {
        btn.addEventListener('click', () => {
            if (btn.dataset.lineAction === 'close') {
                document.getElementById('drawing-line-settings')?.classList.add('hidden');
            }
        });
    });

    // 矩形
    bind('drawing-rect-color', 'input', () => {
        drawingController?.updateSelectedLineSettings?.({ color: document.getElementById('drawing-rect-color').value });
    });
    bind('drawing-rect-fill', 'input', () => {
        drawingController?.updateSelectedLineSettings?.({ fillColor: document.getElementById('drawing-rect-fill').value });
    });
    bind('drawing-rect-opacity', 'change', () => {
        drawingController?.updateSelectedLineSettings?.({ fillOpacity: Number(document.getElementById('drawing-rect-opacity').value) });
    });
    bind('drawing-rect-width', 'change', () => {
        drawingController?.updateSelectedLineSettings?.({ lineWidth: Number(document.getElementById('drawing-rect-width').value) });
    });
    bind('drawing-rect-style', 'change', () => {
        drawingController?.updateSelectedLineSettings?.({ lineStyle: document.getElementById('drawing-rect-style').value });
    });
    document.querySelectorAll('[data-rect-action]').forEach((btn) => {
        btn.addEventListener('click', () => {
            if (btn.dataset.rectAction === 'close') {
                document.getElementById('drawing-rectangle-settings')?.classList.add('hidden');
            }
        });
    });

    // 文字标注
    bind('drawing-text-content', 'change', () => {
        drawingController?.updateSelectedLineSettings?.({ text: document.getElementById('drawing-text-content').value });
    });
    bind('drawing-text-color', 'input', () => {
        drawingController?.updateSelectedLineSettings?.({ color: document.getElementById('drawing-text-color').value });
    });
    bind('drawing-text-size', 'change', () => {
        drawingController?.updateSelectedLineSettings?.({ fontSize: Number(document.getElementById('drawing-text-size').value) });
    });
    document.querySelectorAll('[data-text-action]').forEach((btn) => {
        btn.addEventListener('click', () => {
            if (btn.dataset.textAction === 'close') {
                document.getElementById('drawing-text-settings')?.classList.add('hidden');
            }
        });
    });

    // 持仓测算
    bind('drawing-pos-risk', 'change', () => {
        const next = Number(document.getElementById('drawing-pos-risk').value);
        if (Number.isFinite(next) && next > 0) drawingController.accountRiskPercent = next;
    });
    document.querySelectorAll('[data-pos-action]').forEach((btn) => {
        btn.addEventListener('click', () => {
            if (btn.dataset.posAction === 'close') {
                document.getElementById('drawing-position-settings')?.classList.add('hidden');
            }
        });
    });
}

// ===== A股实时看盘 画图持久化 =====
// 实时看盘每次进入都会走 initializeChart → 重建 DrawingController，
// 不做持久化则用户所画的线在退出/重进（含刷新页面）后全部丢失。
// 说明：仅对实时看盘生效，按标的隔离（茅台上的线不会串到五粮液）；
// 回放训练保持原语义（clearSessionDrawings 即"每次训练从干净画布开始"）。
/**
 * 标准化 A 股代码/symbol，统一补齐标准市场前缀（sh/sz/bj），确保大小写与跨模块数据一致。
 */
function normalizeAshareSymbol(symbolOrCode) {
    if (!symbolOrCode) return '';
    const s = String(symbolOrCode).trim().toLowerCase();
    if (s.startsWith('sh') || s.startsWith('sz') || s.startsWith('bj')) {
        return s;
    }
    const c = s.replace(/^(sh|sz|bj)/i, '');
    if (!c) return '';
    if (c.startsWith('6') || c.startsWith('9') || c.startsWith('5') || c.startsWith('11')) {
        return 'sh' + c;
    } else if (c.startsWith('8') || c.startsWith('4') || c.startsWith('92')) {
        return 'bj' + c;
    } else {
        return 'sz' + c;
    }
}

const ASHARE_LIVE_DRAWINGS_PREFIX = 'kline-ashare-live-drawings-v1::';

function ashareLiveDrawingsKey(symbol) {
    const raw = String(symbol || currentAshareSymbol || 'default').trim();
    const norm = normalizeAshareSymbol(raw) || raw;
    return ASHARE_LIVE_DRAWINGS_PREFIX + norm;
}

function readAshareLiveDrawings(symbol) {
    try {
        const key = ashareLiveDrawingsKey(symbol);
        let raw = localStorage.getItem(key);
        if (!raw) {
            // 向下兼容回退：检查历史可能存储的无前缀纯代码或备用前缀
            const rawSym = String(symbol || currentAshareSymbol || '').trim();
            const normCode = rawSym.replace(/^(sh|sz|bj)/i, '');
            const candidates = [
                ASHARE_LIVE_DRAWINGS_PREFIX + rawSym,
                ASHARE_LIVE_DRAWINGS_PREFIX + normCode,
                ASHARE_LIVE_DRAWINGS_PREFIX + ('sh' + normCode),
                ASHARE_LIVE_DRAWINGS_PREFIX + ('sz' + normCode),
            ];
            for (const cand of candidates) {
                if (cand !== key) {
                    const fallbackRaw = localStorage.getItem(cand);
                    if (fallbackRaw) {
                        raw = fallbackRaw;
                        try { localStorage.setItem(key, raw); } catch (e) {}
                        break;
                    }
                }
            }
        }
        const parsed = JSON.parse(raw || 'null');
        return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
        return [];
    }
}

function persistAshareLiveDrawings(store, symbol) {
    if (!store || !symbol || !isAshareLiveMode) return;
    try {
        const normSym = normalizeAshareSymbol(symbol) || symbol;
        const snapshot = store.snapshot();
        if (!snapshot.length) {
            localStorage.removeItem(ashareLiveDrawingsKey(symbol));
            pushStateToBackend({ drawings: { [normSym]: [] } });
        } else {
            localStorage.setItem(ashareLiveDrawingsKey(symbol), JSON.stringify(snapshot));
            pushStateToBackend({ drawings: { [normSym]: snapshot } });
        }
    } catch (error) {
        // 存储不可用（隐私模式/配额）时静默降级为纯内存画图
    }
}

// 返回注入了"恢复 + 自动回写"的 DrawingStore；非实时看盘或无 DrawingStore 时返回 null（走默认内存 store）。
function createAshareLiveDrawingStore(api, persistSymbol) {
    const Store = api?.DrawingStore;
    if (!Store || !persistSymbol) return null;
    const store = new Store(readAshareLiveDrawings(persistSymbol));
    // 所有增删改（含 undo/redo/clear）都收敛到 _commit；reset 单独处理。
    const originalCommit = store._commit.bind(store);
    store._commit = (nextDrawings) => {
        originalCommit(nextDrawings);
        persistAshareLiveDrawings(store, persistSymbol);
    };
    const originalReset = store.reset.bind(store);
    store.reset = () => {
        const changed = originalReset();
        persistAshareLiveDrawings(store, persistSymbol);
        return changed;
    };
    return store;
}

function initializeDrawingTools() {
    destroyDrawingTools();
    drawingUiAbortController = new AbortController();
    const drawingUiSignal = drawingUiAbortController.signal;
    const api = window.KLineDrawingTools;
    const Controller = api?.DrawingController;
    if (!Controller || !chart || !candlestickSeries) return;
    // 实时看盘：按当前标的恢复已保存画图，并在每次变更后回写 localStorage。
    const persistSymbol = isAshareLiveMode ? (currentAshareSymbol || 'default') : null;
    const restoredDrawingStore = createAshareLiveDrawingStore(api, persistSymbol);
    drawingController = new Controller({
        chart,
        series: candlestickSeries,
        element: document.getElementById('chart'),
        bars: latestRenderedKlineData,
        store: restoredDrawingStore || undefined,
        accountSizeProvider: () => Number(currentTraining?.account?.equity ?? currentTraining?.initial_capital ?? 0),
        axisLabelColors: getDrawingAxisLabelColors,
        defaultDrawingColor: getDrawingDefaultColor,
        onError: (error) => {
            setDrawingStatus(error?.message || '画线失败，请在K线区域内重试。', 'error');
            setDrawingInteractionState(false);
            syncDrawingToolbarState(null);
        },
        onInteractionChange: (active) => setDrawingInteractionState(active),
        onToolChange: (tool) => syncDrawingToolbarState(tool),
        onSelectionChange: (selectedId, model) => syncDrawingFloatingToolbar(selectedId, model),
        onMagnetChange: (enabled) => {
            const magnetBtn = document.getElementById('drawing-magnet-btn');
            if (magnetBtn) {
                magnetBtn.classList.toggle('active', enabled);
                magnetBtn.setAttribute('aria-pressed', String(enabled));
            }
        },
    });

    document.querySelectorAll('[data-drawing-tool]').forEach((button) => {
        if (button.dataset.drawingBound === '1') return;
        button.dataset.drawingBound = '1';
        button.addEventListener('click', () => {
            const toolAliases = { 'long-position': 'long', 'short-position': 'short' };
            const tool = toolAliases[button.dataset.drawingTool] || button.dataset.drawingTool;
            activateDrawingTool(tool);
        });
    });
    document.querySelectorAll('[data-drawing-action]').forEach((button) => {
        if (button.dataset.drawingBound === '1') return;
        // 浮动工具条的按钮由 bindDrawingFloatingToolbar() 专属处理（含 settings/sync-order/drag 分支）。
        // 这里绝不能再绑一次：lock/hide 是 toggle 动作，被触发两次等于没点——
        // 这正是"点锁定没反应"的根因（一次点击 toggleLock 跑两遍，锁上又立刻解锁）。
        if (button.closest('#drawing-floating-toolbar')) return;
        button.dataset.drawingBound = '1';
        button.addEventListener('click', () => invokeDrawingAction(button.dataset.drawingAction));
    });
    // 价格预警按钮（独立于画图工具绑定，见 data-alert-action）
    const alertAddBtn = document.getElementById('alert-add-btn');
    if (alertAddBtn && alertAddBtn.dataset.alertBound !== '1') {
        alertAddBtn.dataset.alertBound = '1';
        alertAddBtn.addEventListener('click', () => toggleAshareAlertAddMode());
    }
    document.querySelector('[data-fibonacci-action="close"]')?.addEventListener('click', () => {
        document.getElementById('drawing-fibonacci-settings')?.classList.add('hidden');
    }, { signal: drawingUiSignal });
    document.querySelector('[data-fibonacci-action="add"]')?.addEventListener('click', () => {
        drawingController?.addFibonacciLevel?.({ value: 2.618, color: '#f59e0b', enabled: true });
        renderFibonacciSettingsPanel();
    }, { signal: drawingUiSignal });
    document.querySelector('[data-fibonacci-action="reset"]')?.addEventListener('click', () => {
        drawingController?.resetFibonacciSettings?.();
        renderFibonacciSettingsPanel();
    }, { signal: drawingUiSignal });
    document.getElementById('drawing-fibonacci-reverse')?.addEventListener('change', (event) => {
        drawingController?.updateSelectedFibonacciSettings?.({ reverse: !!event.target.checked });
    }, { signal: drawingUiSignal });
    syncDrawingToolBars();
    bindDrawingFloatingToolbar();
    bindDrawingSettingPanels();
    syncDrawingToolbarHideButton();
}

function shiftLogicalRange(range, delta = 1) {
    if (!range) return null;
    return {
        from: range.from + delta,
        to: range.to + delta
    };
}

/**
 * 在下一根 K 线推进时，智能保持用户的可视范围：
 * 1. 若用户在右侧预留了空白（最新 K 线的 logical index 在当前可视范围内），则完全不移动可视范围，新 K 线静默绘制在空白处；
 * 2. 若最新 K 线到达或超出可视范围右侧，平移使最新 K 线刚好可见，维持视口缩放与宽度；
 * 3. 若用户正在查看远期历史，保持历史可视范围不变。
 */
function computePreservedNextLogicalRange(previousLogicalRange, dataLength) {
    if (!previousLogicalRange || !Number.isFinite(previousLogicalRange.from) || !Number.isFinite(previousLogicalRange.to)) {
        if (dataLength > 0) {
            const count = Math.min(dataLength, 150);
            return { from: dataLength - count, to: dataLength + 15 };
        }
        return null;
    }
    const newBarIndex = Math.max(0, dataLength - 1);

    // A. 最新 K 线已经在当前可视窗口内部（例如用户在右侧预留了空白）
    if (newBarIndex >= previousLogicalRange.from && newBarIndex <= previousLogicalRange.to - 1) {
        return previousLogicalRange;
    }

    // B. 最新 K 线到达或超出了右边缘：整体平移以露出新 K 线，维持视口宽度
    if (newBarIndex > previousLogicalRange.to - 1) {
        const delta = newBarIndex - (previousLogicalRange.to - 1);
        return {
            from: previousLogicalRange.from + delta,
            to: previousLogicalRange.to + delta,
        };
    }

    // C. 用户正在向左回溯历史 K 线：保持用户当前查看的历史区间
    return previousLogicalRange;
}

function setVisibleRangeAll(range) {
    if (!range) return;
    chart?.timeScale().setVisibleLogicalRange(range);
    volumeChart?.timeScale().setVisibleLogicalRange(range);
    indicatorChart?.timeScale().setVisibleLogicalRange(range);
    syncSubchartsRange(range);
}

function setVisibleTimeRangeAll(range) {
    [chart, volumeChart, indicatorChart].forEach((item) => {
        if (!item) return;
        if (range) item.timeScale().setVisibleRange(range);
        else item.timeScale().fitContent();
    });
    if (subchartInstances && typeof subchartInstances === 'object') {
        Object.values(subchartInstances).forEach((inst) => {
            if (inst && inst.chart) {
                if (range) inst.chart.timeScale().setVisibleRange(range);
                else inst.chart.timeScale().fitContent();
            }
        });
    }
}

/**
 * 快速回到当前最新 K 线页，并复位价格刻度自适应
 * @param {Object} [options]
 * @param {boolean} [options.autoScale=true] 是否同时复位价格刻度自适应
 * @param {number} [options.visibleBars=75] 默认展示的 K 线根数
 * @param {number} [options.rightOffset=5] 右侧留白根数
 */
function scrollToLatestKline(options = {}) {
    const {
        autoScale = true,
        visibleBars = 75,
        rightOffset = 5,
    } = options;
    const totalBars = latestRenderedKlineData?.length || 0;
    if (totalBars > 0) {
        const to = totalBars - 1 + rightOffset;
        const from = Math.max(0, to - visibleBars);
        setVisibleRangeAll({ from, to });
    } else if (chart) {
        chart.timeScale().resetTimeScale();
    }
    if (autoScale) {
        try {
            chart?.priceScale('right')?.applyOptions({ autoScale: true });
            volumeChart?.priceScale('right')?.applyOptions({ autoScale: true });
            indicatorChart?.priceScale('right')?.applyOptions({ autoScale: true });
            if (subchartInstances && typeof subchartInstances === 'object') {
                Object.values(subchartInstances).forEach((inst) => {
                    inst?.chart?.priceScale('right')?.applyOptions({ autoScale: true });
                });
            }
        } catch (e) {
            console.warn('复位价格轴自适应失败:', e);
        }
    }
    updateJumpToLatestBtnVisibility();
}

/**
 * 动态更新“回到最新K线”浮动按钮的可见性
 * 当视野右侧滑离最新蜡烛（最新 K 线在视口外）时显示，视野处于最新附近时隐藏
 */
function updateJumpToLatestBtnVisibility(logicalRange) {
    const jumpBtn = document.getElementById('jump-to-latest-btn');
    if (!jumpBtn) return;
    const totalBars = latestRenderedKlineData?.length || 0;
    if (totalBars <= 0) {
        jumpBtn.classList.add('hidden');
        return;
    }
    const currentRange = logicalRange || chart?.timeScale().getVisibleLogicalRange?.();
    if (!currentRange || !Number.isFinite(currentRange.to)) {
        jumpBtn.classList.add('hidden');
        return;
    }
    // 当视野最右侧落后于最新 K 线一定距离（例如大于 8 根 K 棒），提示可以回到最新
    const isAwayFromLatest = currentRange.to < (totalBars - 8);
    jumpBtn.classList.toggle('hidden', !isAwayFromLatest);
}

let lastSelectedRiskDrawingModel = null;

/** 锁体形状：闭合（已锁） / 开口（未锁） */
const DRAWING_LOCK_SHACKLE_CLOSED = 'M8 11V7a4 4 0 0 1 8 0v4';
const DRAWING_LOCK_SHACKLE_OPEN = 'M8 11V7a4 4 0 0 1 7.7-1.6';

/**
 * 同步「锁定」按钮的视觉状态（主工具条 + 浮动工具条都有一处）。
 * 两处锁定都是"对当前选中对象生效"，但此前只在选中变化时才回刷：点完锁定后
 * 图标既不亮、锁体形状也不变，用户完全看不出有没有锁上（会误判成"锁定没起作用"）。
 */
function applyDrawingLockVisualState(model) {
    const locked = Boolean(model && model.locked);
    document.querySelectorAll('[data-drawing-action="lock"]').forEach((button) => {
        button.classList.toggle('active', locked);
        button.setAttribute('aria-pressed', String(locked));
        button.title = locked ? '已锁定：不可拖动/缩放（点击解锁）' : '锁定当前对象（锁定后不可拖动）';
        // 只替换浮动工具条那套 24x24 图标的锁体；主工具条是 16x16 的另一套几何，
        // 直接写入会把锁体画到 viewBox 外导致图标消失。
        const shackle = button.querySelector('path');
        if (shackle) {
            const current = shackle.getAttribute('d');
            if (current === DRAWING_LOCK_SHACKLE_CLOSED || current === DRAWING_LOCK_SHACKLE_OPEN) {
                shackle.setAttribute('d', locked ? DRAWING_LOCK_SHACKLE_CLOSED : DRAWING_LOCK_SHACKLE_OPEN);
            }
        }
    });
}

/**
 * 同步浮动工具条的显示位置与状态。
 */
function syncDrawingFloatingToolbar(selectedId, model) {
    const toolbar = document.getElementById('drawing-floating-toolbar');
    if (!toolbar) return;
    if (!selectedId || !model) {
        toolbar.classList.add('hidden');
        applyDrawingLockVisualState(null);
        closeAllDrawingSettingPanels();
        syncDrawingToolbarHideButton();
        return;
    }
    const isRiskDrawing = !!model && (
        model.type === 'long' ||
        model.type === 'short' ||
        model.type === 'long-position' ||
        model.type === 'short-position' ||
        model.type === 'risk-reward'
    );
    if (isRiskDrawing) {
        lastSelectedRiskDrawingModel = model;
    }
    toolbar.classList.remove('hidden');
    toolbar.style.display = model.hidden ? 'none' : '';
    // 同步锁定/隐藏按钮的状态高亮
    applyDrawingLockVisualState(model);
    toolbar.querySelector('[data-drawing-action="hide"]')?.classList.toggle('active', !!model.hidden);
    syncDrawingToolbarHideButton();

    // 只有做多/做空/风险回报测算框，才显示「⚡ 同步到下单区」按钮；折线、趋势线、射线、水平线、矩形、文字等一律彻底隐藏
    const syncBtn = toolbar.querySelector('[data-drawing-action="sync-order"]');
    if (syncBtn) {
        syncBtn.classList.toggle('hidden', !isRiskDrawing);
        syncBtn.style.setProperty('display', isRiskDrawing ? 'inline-flex' : 'none', 'important');
    }
}

/**
 * 关闭所有画图对象设置面板（选中取消时统一清理，避免多面板残留）。
 */
function closeAllDrawingSettingPanels() {
    [
        'drawing-fibonacci-settings',
        'drawing-line-settings',
        'drawing-rectangle-settings',
        'drawing-text-settings',
        'drawing-position-settings',
    ].forEach((id) => document.getElementById(id)?.classList.add('hidden'));
}

/**
 * 按选中对象类型打开对应设置面板。
 */
function openSelectedDrawingSettingsPanel(model) {
    closeAllDrawingSettingPanels();
    if (!model) return;
    const type = model.type;
    if (type === 'fibonacci' || type === 'fib-trend-time') {
        const panel = document.getElementById('drawing-fibonacci-settings');
        if (panel) {
            panel.classList.remove('hidden');
            renderFibonacciSettingsPanel();
            return;
        }
    }
    if (type === 'rectangle') {
        const panel = document.getElementById('drawing-rectangle-settings');
        if (panel) {
            panel.classList.remove('hidden');
            renderRectangleSettingsPanel();
            return;
        }
    }
    if (type === 'text') {
        const panel = document.getElementById('drawing-text-settings');
        if (panel) {
            panel.classList.remove('hidden');
            renderTextSettingsPanel();
            return;
        }
    }
    if (type === 'long' || type === 'short' || type === 'risk-reward') {
        const panel = document.getElementById('drawing-position-settings');
        if (panel) {
            panel.classList.remove('hidden');
            renderPositionSettingsPanel();
            return;
        }
    }
    // horizontal / trend / ray / ruler / polyline 等通用线条
    const panel = document.getElementById('drawing-line-settings');
    if (panel) {
        panel.classList.remove('hidden');
        renderLineSettingsPanel(model);
    }
}

/**
 * 获取当前活跃或最近绘制的做多/做空风险测算框模型。
 */
function getActiveRiskDrawingModel(explicitModel) {
    if (explicitModel && (explicitModel.type === 'long' || explicitModel.type === 'short' || explicitModel.type === 'risk-reward')) {
        return explicitModel;
    }
    if (drawingController?.selectedId) {
        const m = drawingController?.store?.get?.(drawingController.selectedId);
        if (m && (m.type === 'long' || m.type === 'short' || m.type === 'risk-reward')) return m;
    }
    if (lastSelectedRiskDrawingModel) {
        return lastSelectedRiskDrawingModel;
    }
    if (drawingController?.activeDrawing && (drawingController.activeDrawing.type === 'long' || drawingController.activeDrawing.type === 'short' || drawingController.activeDrawing.type === 'risk-reward')) {
        return drawingController.activeDrawing;
    }
    if (drawingController?.selectedDrawing && (drawingController.selectedDrawing.type === 'long' || drawingController.selectedDrawing.type === 'short' || drawingController.selectedDrawing.type === 'risk-reward')) {
        return drawingController.selectedDrawing;
    }
    const all = drawingController?.store?.snapshot?.()
        || drawingController?.store?._drawings
        || drawingController?.store?.getAll?.()
        || drawingController?.store?.list?.()
        || [];
    const found = all.slice().reverse().find((d) => d.type === 'long' || d.type === 'short' || d.type === 'risk-reward');
    if (found) return found;
    return explicitModel || null;
}

/**
 * 绑定浮动工具条按钮事件（仅绑定一次）。
 */
let drawingFloatingToolbarBound = false;
function bindDrawingFloatingToolbar() {
    if (drawingFloatingToolbarBound) return;
    const toolbar = document.getElementById('drawing-floating-toolbar');
    if (!toolbar) return;
    drawingFloatingToolbarBound = true;

    // 防止在工具条和设置弹窗内部点击/按下时冒泡触发画布取消选中
    [
        'drawing-floating-toolbar',
        'drawing-fibonacci-settings',
        'drawing-line-settings',
        'drawing-rectangle-settings',
        'drawing-text-settings',
        'drawing-position-settings',
    ].forEach((id) => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('pointerdown', (e) => e.stopPropagation());
            el.addEventListener('mousedown', (e) => e.stopPropagation());
        }
    });

    toolbar.querySelectorAll('[data-drawing-action]').forEach((button) => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const action = button.dataset.drawingAction;
            if (action === 'settings') {
                const model = (drawingController?.selectedId && drawingController?.store?.get?.(drawingController?.selectedId))
                    || lastSelectedRiskDrawingModel
                    || drawingController?.activeDrawing
                    || drawingController?.selectedDrawing;
                if (!model) {
                    setDrawingStatus('请先选中一个画图对象。', 'active');
                    return;
                }
                openSelectedDrawingSettingsPanel(model);
                return;
            }
            if (action === 'sync-order') {
                syncDrawingToOrderPanel();
                return;
            }
            if (action === 'drag') {
                drawingController?.activateTool?.('select');
                return;
            }
            invokeDrawingAction(action, 'floating');
        });
    });
}

/**
 * 将图表做多/做空风险测算框的入场、止损、止盈与风险金额一键同步到下单面板。
 */
function syncDrawingToOrderPanel(model) {
    model = getActiveRiskDrawingModel(model);
    if (!model) {
        setCryptoOrderStatus('请先在图表上选中或绘制做多/做空测算框', 'error');
        alert('请先在图表上选中一个做多/做空测算框');
        return;
    }
    const isCrypto = isCryptoMode() || selectedTrainingMarketType === CRYPTO_MARKET_TYPE || !!document.getElementById('crypto-trading-panel');
    const anchors = Array.isArray(model.anchors) ? model.anchors : [];
    if (anchors.length < 2) {
        setCryptoOrderStatus('该测算框尚未绘制完成，缺少入场或止损价', 'error');
        return;
    }
    const entryPrice = Number(anchors[0]?.price);
    const stopPrice = Number(anchors[1]?.price);
    const targetPrice = anchors.length >= 3 && Number.isFinite(Number(anchors[2]?.price)) ? Number(anchors[2]?.price) : null;

    if (!Number.isFinite(entryPrice) || !Number.isFinite(stopPrice)) {
        setCryptoOrderStatus('测算框价格数据无效', 'error');
        return;
    }

    // 判断方向
    let isLong = true;
    if (model.type === 'short') {
        isLong = false;
    } else if (model.type === 'long') {
        isLong = true;
    } else if (model.type === 'risk-reward') {
        isLong = stopPrice < entryPrice;
    }

    // 计算风险金额 (USDT)
    let riskAmount = 100;
    if (Number.isFinite(model.accountRiskAmount) && model.accountRiskAmount > 0) {
        riskAmount = model.accountRiskAmount;
    } else if (Number.isFinite(model.options?.accountRiskAmount) && model.options.accountRiskAmount > 0) {
        riskAmount = model.options.accountRiskAmount;
    } else {
        const riskPct = Number(drawingController?.accountRiskPercent || document.getElementById('drawing-pos-risk')?.value || 1);
        const equity = Number(currentCryptoSummary?.account_equity || currentCryptoSummary?.balance || currentTraining?.account?.equity || 10000);
        riskAmount = Math.max(1, Math.round(equity * (riskPct / 100)));
    }

    if (isCrypto) {
        // A. 切换做多/做空
        const action = isLong ? 'open_long' : 'open_short';
        selectCryptoOrderAction(action);

        // B. 设置为限价单并填入入场价
        setCryptoOrderType('limit', { preservePrice: true });
        const limitPriceInput = document.getElementById('crypto-limit-price');
        if (limitPriceInput) {
            limitPriceInput.value = formatCryptoInputPrice(entryPrice);
            limitPriceInput.dispatchEvent(new Event('input', { bubbles: true }));
            limitPriceInput.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // C. 开启止盈止损并填入
        const tpslCheckbox = document.getElementById('crypto-tpsl-enabled');
        if (tpslCheckbox) {
            tpslCheckbox.checked = true;
            document.getElementById('crypto-tpsl-fields')?.classList.remove('hidden');
        }
        const slInput = document.getElementById('crypto-sl-price');
        if (slInput) {
            slInput.value = formatCryptoInputPrice(stopPrice);
            slInput.dispatchEvent(new Event('input', { bubbles: true }));
            slInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
        const tpInput = document.getElementById('crypto-tp-price');
        if (tpInput && targetPrice !== null) {
            tpInput.value = formatCryptoInputPrice(targetPrice);
            tpInput.dispatchEvent(new Event('input', { bubbles: true }));
            tpInput.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // D. 开启以损定仓并填入
        const riskcalcCheckbox = document.getElementById('crypto-riskcalc-enabled');
        if (riskcalcCheckbox) {
            riskcalcCheckbox.checked = true;
            document.getElementById('crypto-riskcalc-fields')?.classList.remove('hidden');
        }
        const riskcalcEntry = document.getElementById('crypto-riskcalc-entry');
        if (riskcalcEntry) {
            riskcalcEntry.value = formatCryptoInputPrice(entryPrice);
            riskcalcEntry.dispatchEvent(new Event('input', { bubbles: true }));
            riskcalcEntry.dispatchEvent(new Event('change', { bubbles: true }));
        }
        const riskcalcStop = document.getElementById('crypto-riskcalc-stop');
        if (riskcalcStop) {
            riskcalcStop.value = formatCryptoInputPrice(stopPrice);
            riskcalcStop.dispatchEvent(new Event('input', { bubbles: true }));
            riskcalcStop.dispatchEvent(new Event('change', { bubbles: true }));
        }
        const riskcalcMaxLoss = document.getElementById('crypto-riskcalc-maxloss');
        if (riskcalcMaxLoss) {
            riskcalcMaxLoss.value = String(Math.round(riskAmount));
            riskcalcMaxLoss.dispatchEvent(new Event('input', { bubbles: true }));
            riskcalcMaxLoss.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // E. 自动执行计算并填入建议保证金与委托量
        refreshCryptoRiskCalcResult();
        applyCryptoRiskCalc();
        refreshCryptoOrderPreview();
        refreshCryptoTpSlPnl();

        // F. 界面高亮与提示
        setCryptoOrderStatus(`⚡ 已从图表同步${isLong ? '做多' : '做空'}测算框：入场 ${entryPrice.toFixed(2)}，止损 ${stopPrice.toFixed(2)}${targetPrice ? '，止盈 ' + targetPrice.toFixed(2) : ''}，风险 ${riskAmount} USDT`, 'ready');

        // 高亮提示限价输入框
        const limitGroup = document.getElementById('crypto-limit-price-group');
        if (limitGroup) {
            limitGroup.style.transition = 'all 0.3s ease';
            limitGroup.style.outline = '2px solid #f0b90b';
            limitGroup.style.outlineOffset = '2px';
            setTimeout(() => { limitGroup.style.outline = ''; }, 1500);
        }

        const orderPanel = document.getElementById('crypto-trading-panel') || document.querySelector('.crypto-order-panel') || document.getElementById('crypto-order-grid');
        orderPanel?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

/**
 * 币圈离线数据看板与增量下载
 */
async function loadCryptoOfflineStatus() {
    const tableBody = document.getElementById('offline-data-table-body');
    const totalSymbolsEl = document.getElementById('offline-total-symbols');
    const totalSizeEl = document.getElementById('offline-total-size');
    if (!tableBody) return;

    tableBody.innerHTML = '<tr><td colspan="6" style="padding: 12px; text-align: center; color: var(--text-muted, #848e9c);">正在扫描本地离线数据...</td></tr>';

    try {
        const response = await fetch(`${API_BASE}/crypto/data/offline_status`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        if (totalSymbolsEl) totalSymbolsEl.textContent = data.total_symbols || 0;
        if (totalSizeEl) totalSizeEl.textContent = (data.total_size_mb || 0) + ' MB';

        const symbols = data.symbols || [];
        if (symbols.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="6" style="padding: 12px; text-align: center; color: var(--text-muted, #848e9c);">本地尚未缓存任何币种离线数据，请使用下方工具下载</td></tr>';
            return;
        }

        tableBody.innerHTML = symbols.map((sym) => {
            const isComplete = sym.is_complete_2024_now;
            const statusBadge = isComplete
                ? '<span style="color: #0ecb81; font-weight: 600;">✅ 完整</span>'
                : `<span style="color: #f0b90b;">⏳ ${sym.trade_count}个月</span>`;
            return `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="padding: 6px 10px; font-weight: 600; color: #f0b90b;">
                        <a href="javascript:void(0)" class="offline-sym-link" data-sym="${sym.symbol}" title="点击填入下载框" style="color: #f0b90b; text-decoration: none;">${sym.symbol}</a>
                    </td>
                    <td style="padding: 6px 10px; color: var(--text-muted, #848e9c); text-transform: uppercase;">${sym.source}</td>
                    <td style="padding: 6px 10px;">${sym.trade_range} (${sym.trade_count}月)</td>
                    <td style="padding: 6px 10px;">${sym.mark_count} / ${sym.funding_count}</td>
                    <td style="padding: 6px 10px;">${sym.size_mb} MB</td>
                    <td style="padding: 6px 10px;">${statusBadge}</td>
                </tr>
            `;
        }).join('');

        tableBody.querySelectorAll('.offline-sym-link').forEach((link) => {
            link.addEventListener('click', () => {
                const symInput = document.getElementById('offline-download-symbol');
                if (symInput && link.dataset.sym) symInput.value = link.dataset.sym;
            });
        });
    } catch (err) {
        console.error('加载离线数据状态失败:', err);
        tableBody.innerHTML = `<tr><td colspan="6" style="padding: 12px; text-align: center; color: #f6465d;">加载离线数据看板失败: ${err.message}</td></tr>`;
    }
}

async function triggerCryptoOfflineDownload() {
    const symbolInput = document.getElementById('offline-download-symbol');
    const yearSelect = document.getElementById('offline-download-year');
    const btn = document.getElementById('start-offline-download-btn');
    const statusEl = document.getElementById('offline-download-status');

    const symbol = (symbolInput?.value || '').trim().toUpperCase();
    const year = yearSelect?.value || 'all';

    if (!symbol) {
        alert('请输入要下载的合约代码 (例如 BTCUSDT)');
        return;
    }

    if (btn) btn.disabled = true;
    if (statusEl) {
        statusEl.style.display = 'block';
        statusEl.style.color = '#f0b90b';
        statusEl.textContent = `⏳ 正在检查并从 Binance 官方归档下载 ${symbol} (${year}) 历史数据，请稍候...`;
    }

    try {
        const response = await fetch(`${API_BASE}/crypto/data/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol, year, source: 'binance' })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);

        if (statusEl) {
            statusEl.style.color = '#0ecb81';
            statusEl.textContent = `✅ 下载完成！新增下载 ${result.downloaded} 个月，已缓存 ${result.already_cached} 个月，失败 ${result.failed} 个月。`;
        }
        await loadCryptoOfflineStatus();
    } catch (err) {
        console.error('离线数据下载失败:', err);
        if (statusEl) {
            statusEl.style.color = '#f6465d';
            statusEl.textContent = `❌ 下载失败: ${err.message}`;
        }
    } finally {
        if (btn) btn.disabled = false;
    }
}


function alignTradeMarkerTimeToRenderedBar(markerTime) {
    const normalizedTime = normalizeChartTime({ time: markerTime });
    if (!normalizedTime || latestRenderedKlineData.length === 0) return normalizedTime;
    let left = 0;
    let right = latestRenderedKlineData.length - 1;
    let candidate = null;
    while (left <= right) {
        const middle = Math.floor((left + right) / 2);
        const barTime = Number(latestRenderedKlineData[middle].time);
        if (barTime === normalizedTime) return barTime;
        if (barTime < normalizedTime) {
            candidate = barTime;
            left = middle + 1;
        } else {
            right = middle - 1;
        }
    }
    return candidate || normalizedTime;
}

function syncActiveTradeMarkers(markers) {
    const normalizedMarkers = normalizeTradeMarkers(markers);
    if (currentTraining) currentTraining.tradeMarkers = normalizedMarkers;
    if (!chartWindowState.read_only) chartWindowState.trade_markers = normalizedMarkers;
    updateTradeMarkers(normalizedMarkers);
    lastKnownTradeCount = normalizedMarkers.length;
}


function setChartWindowStatus(message, type = '') {
    const status = document.getElementById('chart-window-status');
    if (!status) return;
    status.textContent = message || '';
    status.className = type;
}

function updateChartWindowControls() {
    const earlierButton = document.getElementById('load-earlier-year-btn');
    const laterButton = document.getElementById('load-later-year-btn');
    const toolbar = document.querySelector('.chart-window-toolbar');
    const isLoading = chartWindowLoadingDirection !== null;

    if (earlierButton) {
        earlierButton.disabled = isLoading || !chartWindowState.has_earlier;
        earlierButton.classList.toggle('loading', chartWindowLoadingDirection === 'earlier');
    }
    if (laterButton) {
        laterButton.classList.toggle('hidden', !chartWindowState.read_only);
        laterButton.disabled = isLoading || !chartWindowState.read_only || !chartWindowState.has_later;
        laterButton.classList.toggle('loading', chartWindowLoadingDirection === 'later');
    }
    toolbar?.classList.toggle('is-loading', isLoading);
}

function applyChartWindow(payload, options = {}) {
    clearCryptoPeriodSnapshotCache();
    const visibleRange = options.preserveRange && chart ? chart.timeScale().getVisibleLogicalRange() : null;
    const previous = options.replace ? createEmptyChartWindowState() : chartWindowState;
    const previousFirstTime = previous.kline_data[0]?.time || null;
    const merged = mergeChartWindow(previous, payload);
    merged.window_start = options.replace
        ? payload.window_start
        : earlierChartWindowTimestamp(previous.window_start, payload.window_start);
    merged.window_end = options.replace
        ? payload.window_end
        : laterChartWindowTimestamp(previous.window_end, payload.window_end);
    merged.history_start = options.replace
        ? (payload.history_start || payload.window_start)
        : earlierChartWindowTimestamp(previous.history_start, payload.history_start || payload.window_start);
    merged.history_end = options.replace
        ? (payload.history_end || payload.window_end)
        : laterChartWindowTimestamp(previous.history_end, payload.history_end || payload.window_end);
    merged.render_start = options.replace
        ? (payload.render_start || payload.window_start)
        : earlierChartWindowTimestamp(previous.render_start, payload.render_start || payload.window_start);
    merged.render_end = options.replace
        ? (payload.render_end || payload.window_end)
        : laterChartWindowTimestamp(previous.render_end, payload.render_end || payload.window_end);
    merged.has_earlier_render = payload.has_earlier_render ?? previous.has_earlier_render;
    if (!options.replace && options.direction === 'earlier') {
        merged.has_later = previous.has_later;
    }
    if (!options.replace && options.direction === 'later') {
        merged.has_earlier = previous.has_earlier;
    }
    merged.extended_history = Boolean(
        previous.extended_history
        || (options.direction === 'earlier' && Array.isArray(payload.kline_data) && payload.kline_data.length > 0)
    );
    chartWindowState = merged;
    if (currentTraining && !merged.read_only) {
        currentTraining.tradeMarkers = merged.trade_markers || [];
    }

    candlestickSeries.setData(merged.kline_data);
    volumeSeries.setData(merged.volume_data);
    replaceRenderedKlineData(merged.kline_data, merged.volume_data);
    loadTechnicalIndicator(currentIndicatorType);
    maPeriods.forEach((period) => maSeries[period]?.setData([]));
    updateTradeMarkers(merged.trade_markers || payload.trade_markers || []);

    const addedEarlierBars = previousFirstTime === null
        ? 0
        : merged.kline_data.filter((bar) => bar.time < previousFirstTime).length;
    if (visibleRange && addedEarlierBars > 0) {
        setVisibleRangeAll(shiftLogicalRange(visibleRange, addedEarlierBars));
    } else if (visibleRange) {
        setVisibleRangeAll(visibleRange);
    } else if (options.fitContent && chart) {
        chart.timeScale().fitContent();
    }

    updateChartWindowControls();
    return merged;
}

function enqueueChartWindowRequest(requestTask) {
    const generation = chartWindowRequestGeneration;
    const queued = chartWindowRequestChain
        .catch(() => null)
        .then(async () => {
            const result = await requestTask(generation);
            return generation === chartWindowRequestGeneration ? result : null;
        });
    chartWindowRequestChain = queued.catch(() => null);
    return queued;
}

function chartWindowRequestUrl(query) {
    if (chartWindowState.read_only) {
        if (!currentUser || !currentReportData?.session_id) throw new Error('历史复盘会话信息不完整');
        return `${API_BASE}/users/${encodeURIComponent(currentUser)}/history/${encodeURIComponent(currentReportData.session_id)}/chart?${query}`;
    }
    if (!currentTraining?.id) throw new Error('活动训练会话不存在');
    return `${API_BASE}/training/${currentTraining.id}/chart-window?${query}`;
}

async function requestChartWindow(rangeStart, rangeEnd, options = {}) {
    const query = new URLSearchParams({
        period: options.period || currentPeriod,
        range_start: rangeStart,
        range_end: rangeEnd,
    });
    const response = await fetch(chartWindowRequestUrl(query.toString()));
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `加载走势失败: ${response.status}`);
    if (options.requestGeneration !== undefined && options.requestGeneration !== chartWindowRequestGeneration) {
        return null;
    }
    if (!payload.kline_data || payload.kline_data.length === 0) {
        setChartWindowStatus('该时间范围没有可用走势数据。', 'empty');
    } else {
        setChartWindowStatus(options.successMessage || '走势数据已加载。', 'success');
    }
    return applyChartWindow(payload, options);
}

async function loadEarlierYear() {
    if (chartWindowLoadingDirection || !chartWindowState.window_start || !chartWindowState.has_earlier) return;
    const requestGeneration = chartWindowRequestGeneration;
    chartWindowLoadingDirection = 'earlier';
    updateChartWindowControls();
    setChartWindowStatus('正在加载更早一年的走势...', 'loading');
    try {
        const rangeEnd = chartWindowState.window_start;
        const rangeStart = shiftChartWindowYear(rangeEnd, -1);
        await enqueueChartWindowRequest((queuedGeneration) => requestChartWindow(rangeStart, rangeEnd, {
            preserveRange: true,
            direction: 'earlier',
            requestGeneration: queuedGeneration,
            successMessage: '已加载更早一年的走势。',
        }));
    } catch (error) {
        if (requestGeneration === chartWindowRequestGeneration) {
            console.error('加载更早走势失败:', error);
            setChartWindowStatus(error.message || '加载更早走势失败。', 'error');
        }
    } finally {
        if (requestGeneration === chartWindowRequestGeneration) {
            chartWindowLoadingDirection = null;
            updateChartWindowControls();
        }
    }
}

async function loadLaterYear() {
    if (chartWindowLoadingDirection || !chartWindowState.read_only || !chartWindowState.has_later || !chartWindowState.window_end) return;
    const requestGeneration = chartWindowRequestGeneration;
    chartWindowLoadingDirection = 'later';
    updateChartWindowControls();
    setChartWindowStatus('正在加载后一年的只读走势...', 'loading');
    try {
        const rangeStart = chartWindowState.window_end;
        const rangeEnd = shiftChartWindowYear(rangeStart, 1);
        await enqueueChartWindowRequest((queuedGeneration) => requestChartWindow(rangeStart, rangeEnd, {
            preserveRange: true,
            direction: 'later',
            requestGeneration: queuedGeneration,
            successMessage: '已加载后一年的只读走势。',
        }));
    } catch (error) {
        if (requestGeneration === chartWindowRequestGeneration) {
            console.error('加载后续走势失败:', error);
            setChartWindowStatus(error.message || '加载后续走势失败。', 'error');
        }
    } finally {
        if (requestGeneration === chartWindowRequestGeneration) {
            chartWindowLoadingDirection = null;
            updateChartWindowControls();
        }
    }
}

async function reloadChartWindowForPeriod(period, rangeEnd, options = {}) {
    if (!chartWindowState.window_start) return null;
    return enqueueChartWindowRequest((requestGeneration) => requestChartWindow(
        chartWindowState.window_start,
        rangeEnd || chartWindowState.window_end,
        { ...options, period, replace: true, requestGeneration }
    ));
}

function applyActiveSnapshotToChartWindow(snapshot) {
    applyIntradaySnapshot(snapshot, { fitContent: false });
    if (!chartWindowState.window_start || chartWindowState.read_only) return;
    const windowVolumePalette = getThemePalette();
    const volumeData = (snapshot.kline_data || []).map((bar) => ({
        time: intradayBarToTimestamp(bar),
        value: Number(bar.volume) || 0,
        color: Number(bar.close) >= Number(bar.open) ? windowVolumePalette.positive : windowVolumePalette.negative,
    }));
    applyChartWindow({
        period: snapshot.active_period || currentPeriod,
        window_start: chartWindowState.window_start,
        window_end: snapshot.current_time || chartWindowState.window_end,
        training_start: chartWindowState.training_start,
        training_end: chartWindowState.training_end,
        has_earlier: chartWindowState.has_earlier,
        has_later: false,
        read_only: false,
        kline_data: snapshot.kline_data || [],
        volume_data: volumeData,
        trade_markers: chartWindowState.trade_markers || [],
    }, { replace: true });
}

function applyTrainingSnapshot(data, options = {}) {
    const { fitContent = false } = options;
    if (!data.kline_data || data.kline_data.length === 0) {
        throw new Error('训练数据为空');
    }

    if (currentTraining) {
        currentTraining.latestProgress = data.progress || null;
        currentTraining.tradeMarkers = data.trade_markers || [];
    }

    if (typeof barReplayState !== 'undefined' && barReplayState && barReplayState.active) {
        handleBarReplayPeriodSwitch(data.kline_data, data.volume_data, currentPeriod);
        updateTradeMarkers(data.trade_markers || []);
        return;
    }

    candlestickSeries.setData(data.kline_data);
    volumeSeries.setData(data.volume_data || []);
    replaceRenderedKlineData(data.kline_data, data.volume_data);

    if (data.ma_data) {
        maPeriods.forEach(p => {
            if (maSeries[p]) {
                maSeries[p].setData(isMaLineVisible(p) ? (data.ma_data[p] || []) : []);
            }
        });
    }
    showLatestChartInfo();

    const currentBar = data.kline_data[data.kline_data.length - 1];
    updateCurrentInfo(currentBar, data.progress);
    updateTradeMarkers(data.trade_markers || []);

    if (fitContent) {
        chart.timeScale().fitContent();
    }
}

async function refreshTrainingView(options = {}) {
    if (!currentTraining || !currentTraining.id) return;
    const { preserveRange = true, fitContent = false } = options;

    // === intraday_30m 分支: GET /data 返回顶层 snapshot，直接渲染 ===
    if (isIntradayMode()) {
        const visibleRange = preserveRange && chart ? chart.timeScale().getVisibleLogicalRange() : null;
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/data`);
        if (!response.ok) {
            throw new Error(`刷新 intraday 视图失败: ${response.status}`);
        }
        const data = await response.json();
        const snapshot = extractIntradaySnapshot(data);
        applyIntradaySnapshot(snapshot, { fitContent });
        await updateAccountInfo();
        if (visibleRange !== null) {
            setVisibleRangeAll(visibleRange);
        }
        return;
    }

    // === legacy_daily 分支 (原逻辑) ===
    const visibleRange = preserveRange && chart ? chart.timeScale().getVisibleLogicalRange() : null;
    const maQuery = maPeriods.join(',');
    const dataEndpoint = isViewOnlyMode ? 'full_data' : 'data';
    const response = await fetch(`${API_BASE}/training/${currentTraining.id}/${dataEndpoint}?ma_periods=${maQuery}&${getViewPeriodQuery()}`);
    if (!response.ok) {
        throw new Error(`刷新训练视图失败: ${response.status}`);
    }

    const data = await response.json();
    if (data.stock_name) {
        document.getElementById('stock-name').textContent = data.stock_name;
    }
    applyTrainingSnapshot(data, { fitContent });
    await loadTechnicalIndicators();
    if (visibleRange !== null) {
        setVisibleRangeAll(visibleRange);
    }
    await updateChipDistribution();
}

function applyCryptoPeriodSnapshot(snapshot, nextPeriod, visibleRange, hadExtendedHistory, wasNearLatest = false) {
    applyIntradaySnapshot(snapshot, { fitContent: false });
    currentTraining.period = nextPeriod;
    updatePeriodBadge(nextPeriod);
    const periodBars = snapshot.kline_data || [];
    const renderedStart = latestRenderedKlineData[0]?.time ?? null;
    const renderedEnd = latestRenderedKlineData[latestRenderedKlineData.length - 1]?.time ?? null;
    const periodVolumes = Array.isArray(snapshot.volume_data) && snapshot.volume_data.length
        ? snapshot.volume_data
        : buildIntradayVolumeData(periodBars);
    chartWindowState = {
        ...chartWindowState,
        period: nextPeriod,
        window_start: snapshot.window_start || periodBars[0]?.time || periodBars[0]?.start_time || chartWindowState.window_start,
        window_end: snapshot.window_end || periodBars[periodBars.length - 1]?.time || snapshot.current_time || chartWindowState.window_end,
        history_start: snapshot.history_start || chartWindowState.history_start,
        history_end: snapshot.history_end || chartWindowState.history_end,
        render_start: snapshot.render_start || periodBars[0]?.time || periodBars[0]?.start_time || chartWindowState.render_start,
        render_end: snapshot.render_end || periodBars[periodBars.length - 1]?.time || snapshot.current_time || chartWindowState.render_end,
        has_earlier_render: snapshot.has_earlier_render ?? false,
        has_earlier: snapshot.has_earlier ?? chartWindowState.has_earlier,
        has_later: snapshot.has_later ?? chartWindowState.has_later,
        extended_history: hadExtendedHistory,
        kline_data: periodBars,
        volume_data: periodVolumes,
    };
    const canRestoreRange = !wasNearLatest && visibleRange && Number.isFinite(renderedStart) && Number.isFinite(renderedEnd)
        && visibleRange.from >= renderedStart && visibleRange.to <= renderedEnd;
    requestAnimationFrame(() => {
        if (wasNearLatest) {
            // 用户在原周期看的就是最新 K 线，切换周期后直接定位到新周期的最新 K 线页
            scrollToLatestKline();
            return;
        }
        if (canRestoreRange) {
            // 首选：保持原时间段（AiCoin 式，切换不丢位置）
            setVisibleTimeRangeAll(visibleRange);
            return;
        }
        // 数据不足或时间段无交集时：优先展示新周期的最新走势，避免跳到远古历史
        if (visibleRange && Number.isFinite(renderedStart) && Number.isFinite(renderedEnd)) {
            const clampedFrom = Math.max(visibleRange.from, renderedStart);
            const clampedTo = Math.min(visibleRange.to, renderedEnd);
            if (clampedTo > clampedFrom && (clampedTo - clampedFrom) >= 10) {
                setVisibleTimeRangeAll({ from: clampedFrom, to: clampedTo });
                return;
            }
        }
        scrollToLatestKline();
    });
}

function isFineCryptoPeriod(period) {
    return period === '1m' || period === '3m' || period === '5m' || period === '15m';
}

function cryptoVisibleTimeValue(value) {
    if (typeof value === 'number' && Number.isFinite(value)) return Math.floor(value);
    const parsed = parseChartWindowTimestamp(value);
    return parsed ? Math.floor(parsed.getTime() / 1000) : null;
}

function addFinePeriodVisibleWindow(requestBody, period, visibleRange) {
    if (!isFineCryptoPeriod(period)) return requestBody;
    const visibleStart = cryptoVisibleTimeValue(visibleRange?.from ?? chartWindowState.render_start);
    const visibleEnd = cryptoVisibleTimeValue(visibleRange?.to ?? chartWindowState.render_end);
    if (visibleStart !== null) requestBody.visible_start = visibleStart;
    if (visibleEnd !== null) requestBody.visible_end = visibleEnd;
    return requestBody;
}

function maybeLoadEarlierCryptoSegment(logicalRange) {
    const leftEdgeThreshold = 300;
    if (!isCryptoMode() || !isFineCryptoPeriod(currentPeriod) || !currentTraining?.id) return;
    if (!chartWindowState.has_earlier_render || cryptoEarlierSegmentLoading) return;
    if (!logicalRange || !Number.isFinite(logicalRange.from) || logicalRange.from > leftEdgeThreshold) return;
    void loadEarlierCryptoSegment();
}

async function loadEarlierCryptoSegment() {
    if (cryptoEarlierSegmentLoading || !currentTraining?.id || !isFineCryptoPeriod(currentPeriod)) return;
    const visibleRange = chart?.timeScale().getVisibleLogicalRange?.() || null;
    const renderStart = cryptoVisibleTimeValue(chartWindowState.render_start || chartWindowState.kline_data[0]?.time);
    const historyStart = cryptoVisibleTimeValue(chartWindowState.history_start || chartWindowState.window_start);
    if (renderStart === null || historyStart === null || historyStart >= renderStart) {
        chartWindowState.has_earlier_render = false;
        return;
    }
    cryptoEarlierSegmentLoading = true;
    const requestGeneration = ++cryptoEarlierSegmentGeneration;
    const requestedPeriod = currentPeriod;
    clearCryptoPeriodSnapshotCacheForPeriod(requestedPeriod);
    setChartWindowStatus('正在加载更早的 ' + formatIntradayPeriodBadge(requestedPeriod) + ' 数据...', 'loading');
    try {
        const response = await fetch(API_BASE + '/training/' + currentTraining.id + '/period', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                period: requestedPeriod,
                compact_chart: true,
                visible_start: historyStart,
                visible_end: Math.max(historyStart, renderStart - 1),
            }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || payload.message || `加载更早走势失败: ${response.status}`);
        if (requestGeneration !== cryptoEarlierSegmentGeneration || currentPeriod !== requestedPeriod) return;
        const snapshot = extractIntradaySnapshot(payload);
        const segmentBars = snapshot?.kline_data || [];
        const segmentVolumes = Array.isArray(snapshot?.volume_data) && snapshot.volume_data.length
            ? snapshot.volume_data
            : buildIntradayVolumeData(segmentBars);
        applyChartWindow({
            ...snapshot,
            period: requestedPeriod,
            window_start: snapshot.render_start || segmentBars[0]?.time,
            window_end: snapshot.render_end || segmentBars[segmentBars.length - 1]?.time,
            kline_data: segmentBars,
            volume_data: segmentVolumes,
        }, {
            preserveRange: true,
            direction: 'earlier',
        });
        if (visibleRange && segmentBars.length === 0) setVisibleRangeAll(visibleRange);
        setChartWindowStatus(segmentBars.length ? '已加载更早走势。' : '没有更早的可用走势。', segmentBars.length ? 'success' : 'empty');
    } catch (error) {
        console.error('加载币圈细周期早期分段失败:', error);
        setChartWindowStatus(error.message || '加载更早走势失败。', 'error');
    } finally {
        if (requestGeneration === cryptoEarlierSegmentGeneration) cryptoEarlierSegmentLoading = false;
    }
}

async function switchCryptoViewPeriod(nextPeriod) {
    if (currentPeriod === nextPeriod && currentTraining?.period === nextPeriod && currentTraining?.id) {
        updatePeriodBadge(nextPeriod);
        return;
    }
    if (!currentTraining?.id || !chart) {
        updatePeriodBadge(nextPeriod);
        return;
    }
    syncCryptoPeriodSnapshotCacheTraining(currentTraining.id);
    periodSwitchAbortController?.abort();
    periodSwitchAbortController = new AbortController();
    const requestGeneration = ++periodSwitchGeneration;
    const visibleRange = chart.timeScale().getVisibleRange?.() || null;
    const visibleLogicalRange = chart.timeScale().getVisibleLogicalRange?.() || null;
    const totalBarsBefore = latestRenderedKlineData?.length || 0;
    // 判断切换前用户是否正处于最新 K 线附近（右侧距最新 <= 8 根或超出）
    const wasNearLatest = Boolean(visibleLogicalRange && Number.isFinite(visibleLogicalRange.to) && (visibleLogicalRange.to >= totalBarsBefore - 8));
    const requestBody = {
        period: nextPeriod,
        request_id: requestGeneration,
        compact_chart: true,
    };
    if (isFineCryptoPeriod(nextPeriod)) {
        const visibleStart = cryptoVisibleTimeValue(visibleRange?.from ?? chartWindowState.render_start);
        const visibleEnd = cryptoVisibleTimeValue(visibleRange?.to ?? chartWindowState.render_end);
        if (visibleStart !== null) requestBody.visible_start = visibleStart;
        if (visibleEnd !== null) requestBody.visible_end = visibleEnd;
    }
    if (chartWindowState.extended_history) {
        const loadedWindowStart = parseChartWindowTimestamp(chartWindowState.window_start);
        const loadedWindowEnd = parseChartWindowTimestamp(chartWindowState.window_end);
        if (loadedWindowStart) requestBody.range_start = Math.floor(loadedWindowStart.getTime() / 1000);
        if (loadedWindowEnd) requestBody.range_end = Math.floor(loadedWindowEnd.getTime() / 1000);
    }
    const hadExtendedHistory = chartWindowState.extended_history;
    const cacheKey = buildCryptoPeriodSnapshotCacheKey(
        currentTraining.id,
        nextPeriod,
        getCryptoReplayCacheTime(),
        chartWindowState,
    );
    const cachedSnapshot = getCryptoPeriodSnapshotCache(cacheKey);
    if (cachedSnapshot) {
        applyCryptoPeriodSnapshot(cachedSnapshot, nextPeriod, visibleRange, hadExtendedHistory, wasNearLatest);
    } else {
        beginPeriodSwitchFeedback(nextPeriod);
    }
    try {
        const response = await fetch(API_BASE + '/training/' + currentTraining.id + '/period', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody),
            signal: periodSwitchAbortController.signal,
        });
        if (!response.ok) {
            const errorPayload = await response.json().catch(() => ({}));
            throw new Error(errorPayload.error || '切换周期失败: ' + response.status);
        }
        const data = await response.json();
        if (requestGeneration !== periodSwitchGeneration) return;
        const snapshot = extractIntradaySnapshot(data);
        setCryptoPeriodSnapshotCache(cacheKey, snapshot);
        applyCryptoPeriodSnapshot(snapshot, nextPeriod, visibleRange, hadExtendedHistory, wasNearLatest);
        setChartWindowStatus('已切换到 ' + formatIntradayPeriodBadge(nextPeriod) + '。', 'success');
        scheduleCryptoPeriodPrefetch(nextPeriod);
    } catch (error) {
        if (error?.name === 'AbortError') return;
        console.error('切换币圈周期失败:', error);
        setChartWindowStatus(error.message || '切换币圈周期失败。', 'error');
    } finally {
        if (requestGeneration === periodSwitchGeneration) endPeriodSwitchFeedback();
    }
}

// === 切换后静默预取相邻周期（丝滑切换优化）===
let cryptoPeriodPrefetchAbortController = null;
let cryptoPeriodPrefetchGeneration = 0;
const CRYPTO_PERIOD_NEIGHBORS = {
    '1m': ['3m'],
    '3m': ['1m', '5m'],
    '5m': ['3m', '15m'],
    '15m': ['5m', '30m'],
    '30m': ['15m', '1h'],
    '1h': ['30m', '2h'],
    '2h': ['1h', '3h'],
    '3h': ['2h', '4h'],
    '4h': ['3h', '6h'],
    '6h': ['4h', '8h'],
    '8h': ['6h', '12h'],
    '12h': ['8h', 'daily'],
    'daily': ['12h', '2d'],
    '2d': ['daily', '3d'],
    '3d': ['2d', 'weekly'],
    'weekly': ['3d'],
};

function scheduleCryptoPeriodPrefetch(period) {
    // Disabled: Avoid background calls that mutate backend session replay period
    return;
}

async function switchViewPeriod(period) {
    if (isAshareLiveMode) {
        await switchAshareLivePeriod(period);
        return;
    }

    const nextPeriod = supportedReplayPeriods().indexOf(period) >= 0 ? period : (period === 'weekly' ? 'weekly' : 'daily');

    if (isViewOnlyMode && chartWindowState.read_only && currentReportData?.session_id) {
        if (currentPeriod === nextPeriod) {
            updatePeriodBadge(nextPeriod);
            return;
        }
        showLoading('正在切换只读历史走势周期');
        try {
            updatePeriodBadge(nextPeriod);
            setChartWindowStatus('正在按新周期加载历史走势...', 'loading');
            await reloadChartWindowForPeriod(nextPeriod, chartWindowState.window_end, {
                fitContent: true,
                successMessage: '历史走势周期已切换。',
            });
        } catch (error) {
            console.error('切换历史走势周期失败:', error);
            setChartWindowStatus(error.message || '切换历史走势周期失败。', 'error');
        } finally {
            hideLoading();
        }
        return;
    }

    if (isCryptoMode()) {
        await switchCryptoViewPeriod(nextPeriod);
        return;
    }

    // === intraday_30m 分支: POST /period 切换，不调用 /next ===
    if (isIntradayMode()) {
        if (currentPeriod === nextPeriod && currentTraining && currentTraining.id) {
            updatePeriodBadge(nextPeriod);
            return;
        }
        if (!currentTraining || !currentTraining.id || !chart) {
            updatePeriodBadge(nextPeriod);
            return;
        }
        showLoading('正在切换 ' + formatIntradayPeriodBadge(nextPeriod) + ' 视图');
        try {
            const response = await fetch(`${API_BASE}/training/${currentTraining.id}/period`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ period: nextPeriod })
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || `切换周期失败: ${response.status}`);
            }
            const data = await response.json();
            // period 返回顶层 snapshot
            const snapshot = extractIntradaySnapshot(data);
            applyIntradaySnapshot(snapshot, { fitContent: false });
            await reloadChartWindowForPeriod(nextPeriod, snapshot.current_time, {
                fitContent: true,
                successMessage: '活动走势周期已切换。',
            });
            await updateAccountInfo();
        } catch (error) {
            console.error('切换 intraday 周期失败:', error);
            alert('切换周期失败');
        } finally {
            hideLoading();
        }
        return;
    }

    // === legacy_daily 分支 (原逻辑) ===
    const legacyNext = nextPeriod === 'weekly' ? 'weekly' : 'daily';
    if (currentPeriod === legacyNext) {
        updatePeriodBadge(legacyNext);
        return;
    }

    updatePeriodBadge(legacyNext);
    if (!currentTraining || !currentTraining.id || !chart) {
        return;
    }

    showLoading(legacyNext === 'weekly' ? '正在切换周K视图' : '正在切换日K视图');
    try {
        await refreshTrainingView({ preserveRange: false, fitContent: true });
    } catch (error) {
        console.error('切换K线视图失败:', error);
        alert('切换K线视图失败');
    } finally {
        hideLoading();
    }
}

// 极速功能测试模式（固定 2024 年 BTC 半年离线数据，极速开局）
async function launchQuickTestBtc() {
    document.getElementById('training-setup')?.classList.add('hidden');
    if (!currentUser) {
        alert('请先选择或创建用户');
        showUserSelection();
        return;
    }
    const payload = {
        user: currentUser,
        market_type: CRYPTO_MARKET_TYPE,
        data_mode: CRYPTO_DATA_MODE,
        mode: 'specified',
        symbol: 'BTCUSDT',
        start_time: '2024-07-01 00:00:00',
        data_source: 'binance',
        period: getSelectedKlinePeriod() || 'daily',
        max_training_days: 30,
        initial_capital: 100000,
        leverage: 10,
        history_years: 1,
        history_months: 6, // 固定半年数据（2024-01 ~ 2024-07），100% 离线秒开
    };
    try {
        await startCryptoTrainingWithHistoryPreparation(payload);
    } catch (error) {
        if (error?.name === 'AbortError' || error?.cryptoHistoryHandled) return;
        alert(error.message || '极速功能测试启动失败');
    }
}

// 训练管理
async function startTraining() {
    const isRandomMode = document.querySelector('.tab-btn.active').dataset.tab === 'random';
    if (selectedTrainingMarketType === CRYPTO_MARKET_TYPE) {
        try {
            return await startCryptoTrainingWithHistoryPreparation(buildCryptoStartPayload(isRandomMode));
        } catch (error) {
            if (error?.name === 'AbortError' || error?.cryptoHistoryHandled) return;
            alert(error.message || '币圈训练参数不完整');
            return;
        }
    }
    const initialCapital = parseFloat(document.getElementById('initial-capital').value);
    const dataSource = document.getElementById('data-source').value || 'akshare';
    const period = getSelectedKlinePeriod();

    let trainingConfig = {
        user: currentUser,
        initial_capital: initialCapital,
        mode: isRandomMode ? 'random' : 'specified',
        data_source: dataSource,
        data_mode: INTRADAY_DATA_MODE,
        period: period,
        max_training_days: parseInt(document.getElementById('max-training-bars')?.value) || 0
    };

    if (isRandomMode) {
        trainingConfig.sector = document.getElementById('sector-filter').value;
        trainingConfig.date_start = document.getElementById('random-start-date').value.trim();
        trainingConfig.date_end = document.getElementById('random-end-date').value.trim();
    } else {
        const stockCode = document.getElementById('stock-code').value.trim();
        const startDate = document.getElementById('start-date').value;

        if (!stockCode || !startDate) {
            alert('请填写完整的股票代码和起始日期');
            return;
        }

        trainingConfig.stock_code = stockCode;
        trainingConfig.start_date = startDate;
    }

    return startTrainingWithConfig(trainingConfig);
}

function startTrainingWithConfig(trainingConfig) {
    return (async () => {
    if (isAshareLiveMode) {
        stopAshareLivePolling();
        isAshareLiveMode = false;
        // 直接由实时看盘跳进训练（工具栏"快速测试/新建训练"）时并没有走 exitAshareLiveWatch，
        // 快照必须一并作废，否则之后任何一次 exit 都会用过期状态覆盖当前模式的副图/指标。
        asharePreLiveUiState = null;
        const mainApp = document.getElementById('main-app');
        mainApp?.classList.remove('ashare-live-active');
        document.getElementById('ashare-live-search-btn')?.classList.add('hidden');
        document.getElementById('ashare-live-exit-btn')?.classList.add('hidden');
    }
    clearCryptoPeriodSnapshotCache();
    const period = trainingConfig.period || 'daily';
    const dataSource = trainingConfig.data_source || 'akshare';
    try {
        updatePeriodBadge(period);
        showLoading(
            dataSource === 'offline' ? '正在筛选本地离线数据' : '正在创建训练',
            dataSource === 'offline' ? '首次校验离线股票可用范围时会稍慢一些。' : '正在准备图表和训练数据...'
        );
        const response = await fetch(`${API_BASE}/training/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(trainingConfig)
        });

        if (response.ok) {
            clearSessionDrawings();
            currentTraining = await response.json();
            syncCryptoPeriodSnapshotCacheTraining(currentTraining.id);
            currentTraining.period = currentTraining.period || period;
            updatePeriodBadge(currentTraining.period);
            currentReportData = null;
            hideTrainingSetup();
            document.getElementById('report-interface').classList.add('hidden');
            showTrainingInterface();
            initializeChart();

            if (isIntradayMode()) {
                // === intraday_30m 分支 ===
                // start 返回顶层 snapshot；直接渲染初始快照，禁止自动调用 nextBar。
                const snapshot = extractIntradaySnapshot(currentTraining);
                applyIntradaySnapshot(snapshot, { fitContent: false });
                resetChartWindowState();
                applyChartWindow({
                    period: snapshot.active_period || period,
                    window_start: currentTraining.window_start || currentTraining.training_start,
                    window_end: currentTraining.window_end || snapshot.current_time,
                    history_start: currentTraining.history_start || currentTraining.window_start || currentTraining.training_start,
                    history_end: currentTraining.history_end || currentTraining.window_end || snapshot.current_time,
                    render_start: currentTraining.render_start || currentTraining.window_start || currentTraining.training_start,
                    render_end: currentTraining.render_end || currentTraining.window_end || snapshot.current_time,
                    has_earlier_render: !!currentTraining.has_earlier_render,
                    training_start: currentTraining.training_start,
                    training_end: currentTraining.training_end,
                    has_earlier: !!currentTraining.has_earlier,
                    has_later: false,
                    read_only: false,
                    kline_data: currentTraining.context_kline_data?.length
                        ? currentTraining.context_kline_data
                        : snapshot.kline_data,
                    volume_data: currentTraining.context_volume_data?.length
                        ? currentTraining.context_volume_data
                        : buildIntradayVolumeData(snapshot.kline_data),
                    trade_markers: currentTraining.trade_markers || [],
                }, { replace: true, fitContent: true });
                setChartWindowStatus(isCryptoMode() ? '已加载币圈历史走势（UTC+8）。' : '已加载训练开始前至少两年的走势。', 'success');
                await updateAccountInfo();
                startAutoSync();
                renderActiveIndicatorTags();
            } else {
                // === legacy_daily 分支 (原逻辑) ===
                await loadInitialData();
                await updateChipDistribution(); // 加入此行，初始化筹码分布

                // 在所有内容加载完毕后，自动触发一次 nextBar
                // 我们加一个小的延时，确保图表渲染完成，视觉效果更平滑
                setTimeout(() => {
                    nextBar();
                }, 100); // 100毫秒的延时

                startAutoSync();
            }
        } else {
            const error = await response.json().catch(() => ({}));
            alert(error.error || error.message || `开始训练失败 (HTTP ${response.status})`);
        }
    } catch (error) {
        console.error('开始训练失败:', error);
        alert(error?.message || '开始训练失败');
    } finally {
        hideLoading();
    }
    })();
}

function showTrainingInterface() {
    document.getElementById('history-dashboard')?.classList.add('hidden');
    document.getElementById('training-interface').classList.remove('hidden');
    document.getElementById('a-share-trading-panel')?.classList.toggle('hidden', isCryptoMode());
    document.getElementById('limit-status')?.classList.toggle('hidden', isCryptoMode());
    document.getElementById('pending-orders')?.classList.toggle('hidden', isCryptoMode());
    document.getElementById('crypto-trading-panel')?.classList.toggle('hidden', !isCryptoMode());
    const cryptoOrderLeverage = document.getElementById('crypto-order-leverage');
    if (cryptoOrderLeverage && isCryptoMode()) {
        cryptoOrderLeverage.value = String(currentTraining.leverage || 5);
    }
    document.querySelectorAll('.crypto-view-period').forEach((button) => button.classList.toggle('hidden', !isCryptoMode()));
    document.querySelectorAll('.a-share-view-period').forEach((button) => button.classList.toggle('hidden', isCryptoMode()));
    syncCryptoWorkspaceMode();
    if (isCryptoMode()) selectCryptoOrderAction('open_long');
    setTrainingViewOnlyMode(false, { showBackToReport: false });
    updateAccountInfo();
    // 隐藏按钮和标题
    toggleToolbarForTraining(true);
}

// 图表时间显示换区说明：
// 币圈数据源时间为 UTC 原文，历史版本图表按 UTC 渲染导致比 AICoin（北京时间）慢 8 小时；
// 现统一"显示层换区"——币圈模式 +8h 渲染北京时间，A股（Intraday/实时看盘）数据原文即北京时间，偏移 0。
// 数据层时间戳保持 UTC 单一事实源，仅此显示出口换区。偏移取值见 formatChartCrosshairTime 之后的
// chartTimeDisplayOffsetSeconds()。
function formatChartCrosshairTime(time) {
    if (!time) return '';
    try {
        if (typeof time === 'object' && time !== null) {
            if (time instanceof Date) {
                const shifted = new Date(time.getTime() + chartTimeDisplayOffsetSeconds() * 1000);
                const y = shifted.getUTCFullYear();
                const m = String(shifted.getUTCMonth() + 1).padStart(2, '0');
                const d = String(shifted.getUTCDate()).padStart(2, '0');
                const hh = String(shifted.getUTCHours()).padStart(2, '0');
                const mm = String(shifted.getUTCMinutes()).padStart(2, '0');
                if (isCryptoMode() || isIntradayMode() || hh !== '00' || mm !== '00') {
                    return `${y}-${m}-${d} ${hh}:${mm}`;
                }
                return `${y}-${m}-${d}`;
            }
            if (time.year) {
                const y = time.year;
                const m = String(time.month || 1).padStart(2, '0');
                const d = String(time.day || 1).padStart(2, '0');
                return `${y}-${m}-${d}`;
            }
        }
        const num = Number(time);
        if (Number.isFinite(num)) {
            const date = new Date((num + chartTimeDisplayOffsetSeconds()) * 1000);
            if (!Number.isNaN(date.getTime())) {
                const year = date.getUTCFullYear();
                const month = String(date.getUTCMonth() + 1).padStart(2, '0');
                const day = String(date.getUTCDate()).padStart(2, '0');
                const hours = String(date.getUTCHours()).padStart(2, '0');
                const minutes = String(date.getUTCMinutes()).padStart(2, '0');
                if (isCryptoMode() || isIntradayMode() || hours !== '00' || minutes !== '00') {
                    return `${year}-${month}-${day} ${hours}:${minutes}`;
                }
                return `${year}-${month}-${day}`;
            }
        }
    } catch (e) {
        return '';
    }
    return String(time || '');
}

function chartTimeDisplayOffsetSeconds() {
    if (isAshareLiveMode) return 0;
    if (isCryptoMode()) return 8 * 3600;
    return 0;
}

// 底部时间轴刻度文本：与十字光标同一时区语义（币圈 UTC+8，A股原文）。
// 日内刻度显示 HH:mm，零点整刻度显示 MM-DD 日期（贴合日线/周线切换观感）。
function formatChartTickMarkTime(time) {
    if (!time) return '';
    if (typeof time === 'object' && time !== null && time.year) {
        const y = time.year;
        const m = String(time.month || 1).padStart(2, '0');
        const d = String(time.day || 1).padStart(2, '0');
        return `${m}-${d}`;
    }
    const num = Number(time);
    if (!Number.isFinite(num)) return String(time || '');
    const date = new Date((num + chartTimeDisplayOffsetSeconds()) * 1000);
    if (Number.isNaN(date.getTime())) return String(time || '');
    const month = String(date.getUTCMonth() + 1).padStart(2, '0');
    const day = String(date.getUTCDate()).padStart(2, '0');
    const hours = String(date.getUTCHours()).padStart(2, '0');
    const minutes = String(date.getUTCMinutes()).padStart(2, '0');
    if (hours === '00' && minutes === '00') return `${month}-${day}`;
    return `${hours}:${minutes}`;
}

// 图表管理
function initializeChart() {
    destroyDrawingTools();
    // 图表即将被整体重建：旧 series 对象属于废弃的 chart 实例，必须同步清空记账。
    // 否则下一次 loadTechnicalIndicator → clearTechnicalIndicatorSeries 会对旧 series
    // 调用 removeSeries 抛 "Value is undefined"，整个副图刷新被 catch 吞掉后直接返回，
    // 副图既不重绘也不更新 lastIndicatorData，但仍残留上一数据集（如币圈）的图例，
    // 表现为切换模式（币圈 ↔ A股实时看盘）后 MACD 副图空白。
    currentIndicatorSeries = [];
    bollSeries = {};
    clearSubchartInstances();
    applyChartPanelRatios(readChartPanelRatios());
    const palette = getThemePalette();
    // 初始化主图表
    const chartContainer = document.getElementById('chart');
    chartContainer.innerHTML = '';

    // 在图表容器内动态创建信息显示框
    const infoDisplay = document.createElement('div');
    infoDisplay.id = 'chart-info-display';
    infoDisplay.className = 'chart-info-display';
    chartContainer.appendChild(infoDisplay);

    const chartLegend = document.createElement('div');
    chartLegend.id = 'chart-legend';
    chartLegend.className = 'chart-legend';
    chartContainer.appendChild(chartLegend);

    chart = LightweightCharts.createChart(chartContainer, {
        width: chartContainer.clientWidth,
        height: chartContainer.clientHeight,
        layout: {
            background: { type: 'solid', color: palette.chartBg },
            textColor: palette.text,
        },
        grid: {
            vertLines: {
                color: palette.grid,
            },
            horzLines: {
                color: palette.grid,
            },
        },
        crosshair: getCrosshairOptions(palette),
        rightPriceScale: {
            borderColor: palette.border,
            minimumWidth: 80,
        },
        // 使用 localization 选项来格式化十字标线的时间 (精确到分钟，AiCoin 风格: 2026-08-14 17:00)
        localization: {
            timeFormatter: (businessDayOrTimestamp) => formatChartCrosshairTime(businessDayOrTimestamp),
            locale: 'zh-CN',
        },
        timeScale: {
            borderColor: palette.border,
            timeVisible: true,
            secondsVisible: false,
            // 时间轴刻度与十字光标同一时区语义：币圈按 UTC+8（对齐 AICoin），A股原文直出
            tickMarkFormatter: (time) => formatChartTickMarkTime(time),
        },
    });

    // 添加K线系列
    candlestickSeries = chart.addSeries(LightweightCharts.CandlestickSeries, getCandleStyleOptions(palette));
    candlestickSeries.applyOptions({
        lastValueVisible: isCryptoMode() || isAshareLiveMode,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
    });
    applyLastPriceTagColor();

    // 添加移动平均线
    maPeriods.forEach((p, index) => {
        maSeries[p] = chart.addSeries(LightweightCharts.LineSeries, {
            color: getMaLineColor(p, index),
            lineWidth: 1,
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
        });
        maSeries[p].applyOptions({ lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });
    });

    renderChartLegend();

    // 创建并复用同一个交易标记图层，成交后只更新标记数据。
    tradeMarkerSeries = LightweightCharts.createSeriesMarkers(candlestickSeries, []);

    // 初始化成交量图表
    const volumeContainer = document.getElementById('volume-chart');
    volumeContainer.innerHTML = '';

    volumeChart = LightweightCharts.createChart(volumeContainer, {
        width: volumeContainer.clientWidth,
        height: volumeContainer.clientHeight,
        layout: {
            background: { type: 'solid', color: palette.chartBg },
            textColor: palette.text,
        },
        grid: {
            vertLines: {
                color: palette.grid,
            },
            horzLines: {
                color: palette.grid,
            },
        },
        rightPriceScale: {
            borderColor: palette.border,
            minimumWidth: 80,
        },
        timeScale: {
            borderColor: palette.border,
            visible: false,
        },
    });

    // 添加成交量系列
    volumeSeries = volumeChart.addSeries(LightweightCharts.HistogramSeries, {
        color: '#26a69a',
        priceFormat: {
            type: 'volume',
        },
        priceLineVisible: false,
        lastValueVisible: false
    });

    // 初始化技术指标图表
    initSubcharts();

    // 监听主图表（K线图）的时间轴变化
    chart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
        if (timeRange && !isSyncingRange) {
            isSyncingRange = true;
            volumeChart.timeScale().setVisibleLogicalRange(timeRange);
            syncSubchartsRange(timeRange);
            if (indicatorChart) {
                try { indicatorChart.timeScale().setVisibleLogicalRange(timeRange); } catch (e) {}
            }
            maybeLoadEarlierCryptoSegment(timeRange);
            isSyncingRange = false;
        }
        updateJumpToLatestBtnVisibility(timeRange);
        scheduleChipDistributionRender();
        scheduleExtremePriceTagsUpdate();
        scheduleTradingHoursBandsUpdate();
        scheduleAshareAlertChipsUpdate();
    });
    
    chart.timeScale().subscribeVisibleTimeRangeChange(() => {
        scheduleChipDistributionRender();
        scheduleExtremePriceTagsUpdate();
        scheduleTradingHoursBandsUpdate();
        scheduleAshareAlertChipsUpdate();
    });

    // 价格轴纵向缩放/平移不会改变时间轴范围，需借助鼠标交互把预警标签贴回新坐标
    chart.subscribeCrosshairMove(() => scheduleAshareAlertChipsUpdate());

    // 监听成交量图表的时间轴变化
    volumeChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
        if (timeRange && !isSyncingRange) {
            isSyncingRange = true;
            chart.timeScale().setVisibleLogicalRange(timeRange);
            syncSubchartsRange(timeRange);
            if (indicatorChart) {
                try { indicatorChart.timeScale().setVisibleLogicalRange(timeRange); } catch (e) {}
            }
            isSyncingRange = false;
        }
    });

    // 监听技术指标图表的时间轴变化
    if (indicatorChart) {
        try {
            indicatorChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
                if (timeRange && !isSyncingRange) {
                    isSyncingRange = true;
                    chart.timeScale().setVisibleLogicalRange(timeRange);
                    volumeChart.timeScale().setVisibleLogicalRange(timeRange);
                    syncSubchartsRange(timeRange, indicatorChart);
                    isSyncingRange = false;
                }
            });
        } catch (e) {}
    }

    function getCrosshairDataPoint(series, param) {
        if (!param.time) {
            return null;
        }
        const dataPoint = param.seriesData.get(series);
        return dataPoint || null;
    }

    function syncCrosshair(chart, series, dataPoint) {
        if (dataPoint) {
            chart.setCrosshairPosition(dataPoint.value, dataPoint.time, series);
            return;
        }
        chart.clearCrosshairPosition();
    }


    chart.subscribeCrosshairMove(param => {
        const infoEl = document.getElementById('chart-info-display');
        if (!param.time || param.point.x < 0 || param.point.y < 0) {
            if (isCryptoMode() || isAshareLiveMode) {
                showLatestChartInfo();
            } else {
                infoEl.style.display = 'none';
            }
            // 同步其他图表的十字准星
            syncCrosshair(volumeChart, volumeSeries, null);
            syncCrosshairToAllSubcharts(null);
            if (currentIndicatorSeries.length > 0 && indicatorChart) {
                syncCrosshair(indicatorChart, currentIndicatorSeries[0], null);
            }
            return;
        }

        infoEl.style.display = 'block';

        // 创建数据Map以便快速查找
        const seriesData = latestRenderedKlineData;
        const dataMap = new Map();
        seriesData.forEach((dataPoint, index) => {
            // 确保数据点有时间属性
            if (dataPoint.time) {
                dataMap.set(dataPoint.time, { ...dataPoint, index });
            }
        });

        // 从Map中快速获取当前数据点及其索引
        const currentDataPoint = dataMap.get(param.time);

        if (!currentDataPoint) {
            return;
        }

        let previousDataPoint = null;
        // 检查是否存在前一个数据点
        if (currentDataPoint.index > 0) {
            // 直接通过索引从原始数据数组中获取
            previousDataPoint = seriesData[currentDataPoint.index - 1];
        }

        // 获取K线数据
        const ohlcData = param.seriesData.get(candlestickSeries);
        let ohlcHtml = '数据加载中...';
        const crosshairPalette = getThemePalette();
        const neutralColor = crosshairPalette.neutral;
        const upColor = crosshairPalette.positive;
        const downColor = crosshairPalette.negative;
        if (ohlcData) {
            if (previousDataPoint) {
                ohlcHtml = `
                    <div style="margin-bottom: 4px;">
                        <strong>开:</strong> <span style="color: ${ohlcData.open > previousDataPoint.close ? upColor : ohlcData.open < previousDataPoint.close ? downColor : neutralColor};">${ohlcData.open.toFixed(2)}</span>
                        <strong>高:</strong> <span style="color: ${ohlcData.high > previousDataPoint.close ? upColor : ohlcData.high < previousDataPoint.close ? downColor : neutralColor};">${ohlcData.high.toFixed(2)}</span>
                        <strong>低:</strong> <span style="color: ${ohlcData.low > previousDataPoint.close ? upColor : ohlcData.low < previousDataPoint.close ? downColor : neutralColor};">${ohlcData.low.toFixed(2)}</span>
                        <strong>收: <span style="color: ${ohlcData.close > ohlcData.open ? upColor : ohlcData.close < ohlcData.open ? downColor : neutralColor};">${ohlcData.close.toFixed(2)}</span></strong>
                    </div>
                `;
            } else {
                ohlcHtml = `
                    <div style="margin-bottom: 4px;">
                        <strong>开:</strong> <span>${ohlcData.open.toFixed(2)}</span>
                        <strong>高:</strong> <span>${ohlcData.high.toFixed(2)}</span>
                        <strong>低:</strong> <span>${ohlcData.low.toFixed(2)}</span>
                        <strong>收: <span style="color: ${ohlcData.close > ohlcData.open ? upColor : ohlcData.close < ohlcData.open ? downColor : neutralColor};">${ohlcData.close.toFixed(2)}</span></strong>
                    </div>
                `;
            }
        }

        // 获取MA数据
        let maHtml = '<div>';
        maPeriods.forEach(p => {
            if (!isMaLineVisible(p)) return;
            const mData = param.seriesData.get(maSeries[p]);
            if (mData) {
                maHtml += `<span style="color: ${maSeries[p].options().color};">MA${p}:${mData.value.toFixed(2)} </span>`;
            }
        });
        maHtml += '</div>';

        // 获取并显示BOLL指标数据
        let bollHtml = '';
        // 检查BOLL指标是否处于激活状态 (通过检查bollSeries对象)
        if ((bollVisible || currentIndicatorType === 'BOLL') && bollSeries.upper && bollSeries.middle && bollSeries.lower) {
            const upperData = param.seriesData.get(bollSeries.upper);
            const middleData = param.seriesData.get(bollSeries.middle);
            const lowerData = param.seriesData.get(bollSeries.lower);

            if (upperData && middleData && lowerData) {
                bollHtml = `
                    <div id="boll-info-content" style="margin-top: 4px;">
                        <span style="color: ${bollSeries.upper.options().color};">UP:${upperData.value.toFixed(2)} </span>
                        <span style="color: ${bollSeries.middle.options().color};">MID:${middleData.value.toFixed(2)} </span>
                        <span style="color: ${bollSeries.lower.options().color};">LOW:${lowerData.value.toFixed(2)} </span>
                    </div>
                `;
            }
        }

        // 组合所有信息并更新到DOM
        infoEl.innerHTML = ohlcHtml + maHtml + bollHtml;

        // 同步其他图表的十字准星
        const dataPoint = getCrosshairDataPoint(candlestickSeries, param);
        syncCrosshair(volumeChart, volumeSeries, dataPoint);
        syncCrosshairToAllSubcharts(param);
        if (currentIndicatorSeries.length > 0 && indicatorChart) {
            syncCrosshair(indicatorChart, currentIndicatorSeries[0], dataPoint);
        }
    });

    volumeChart.subscribeCrosshairMove(param => {
        const dataPoint = getCrosshairDataPoint(volumeSeries, param);
        syncCrosshair(chart, candlestickSeries, dataPoint);
        syncCrosshairToAllSubcharts(param);
        if (currentIndicatorSeries.length > 0 && indicatorChart) {
            syncCrosshair(indicatorChart, currentIndicatorSeries[0], dataPoint);
        }
    });

    if (indicatorChart) {
        try {
            indicatorChart.subscribeCrosshairMove(param => {
                const infoEl = document.getElementById('indicator-info-display');
                if (!infoEl) return;

                // 如果十字准星移出图表或没有数据，则隐藏信息框
                if (!param.time || param.point.x < 0 || param.point.y < 0 || currentIndicatorSeries.length === 0) {
                    infoEl.style.display = 'none';
                    syncCrosshairToAllSubcharts(null);
                    return;
                }

                infoEl.style.display = 'block';
                let indicatorHtml = '';

                // 根据当前指标类型，获取并格式化数据
                switch (currentIndicatorType) {
                    case 'MACD':
                    case 'MACD2':
                        const difData = param.seriesData.get(currentIndicatorSeries[0]);
                        const deaData = param.seriesData.get(currentIndicatorSeries[1]);
                        const histData = param.seriesData.get(currentIndicatorSeries[2]);
                        if (difData && deaData && histData) {
                            indicatorHtml = `
                                <div><strong>${currentIndicatorType}</strong></div>
                                <div style="color: ${currentIndicatorSeries[0].options().color};">DIF: ${difData.value.toFixed(2)}</div>
                                <div style="color: ${currentIndicatorSeries[1].options().color};">DEA: ${deaData.value.toFixed(2)}</div>
                                <div style="color: ${histData.color};">HIST: ${histData.value.toFixed(2)}</div>
                            `;
                        }
                        break;

                    case 'KDJ':
                        const kData = param.seriesData.get(currentIndicatorSeries[0]);
                        const dData = param.seriesData.get(currentIndicatorSeries[1]);
                        const jData = param.seriesData.get(currentIndicatorSeries[2]);
                        if (kData && dData && jData) {
                            indicatorHtml = `
                                <div><strong>KDJ</strong></div>
                                <div style="color: ${currentIndicatorSeries[0].options().color};">K: ${kData.value.toFixed(2)}</div>
                                <div style="color: ${currentIndicatorSeries[1].options().color};">D: ${dData.value.toFixed(2)}</div>
                                <div style="color: ${currentIndicatorSeries[2].options().color};">J: ${jData.value.toFixed(2)}</div>
                            `;
                        }
                        break;

                    case 'RSI':
                        indicatorHtml = '<div><strong>RSI</strong></div>';
                        currentIndicatorSeries.forEach(series => {
                            const rsiData = param.seriesData.get(series);
                            if (rsiData) {
                                const titleText = series.rsiTitle || series.options().title || 'RSI';
                                indicatorHtml += `<div style="color: ${series.options().color};">${titleText}: ${rsiData.value.toFixed(2)}</div>`;
                            }
                        });
                        break;
                }

                infoEl.innerHTML = indicatorHtml;

                // 同步其他图表的十字准星
                if (currentIndicatorSeries.length > 0) {
                    const dataPoint = getCrosshairDataPoint(currentIndicatorSeries[0], param);
                    syncCrosshair(chart, candlestickSeries, dataPoint);
                    syncCrosshair(volumeChart, volumeSeries, dataPoint);
                }
                syncCrosshairToAllSubcharts(param);
            });
        } catch (e) {}
    }

    // 绑定右下角“回到最新K线”浮动按钮点击事件
    const jumpToLatestBtn = document.getElementById('jump-to-latest-btn');
    if (jumpToLatestBtn && !jumpToLatestBtn.dataset.bound) {
        jumpToLatestBtn.dataset.bound = 'true';
        jumpToLatestBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            scrollToLatestKline();
        });
    }

    registerBarReplayChartEvents(chart);
    initializeDrawingTools();
}

// ==========================================================================
// K线任意截断复盘 (Bar Replay) 控制器
// 对标 AICoin / TradingView 交互：任意K线截断、局部切片、无前瞻MA重算、前进与随时退出回到最新
// ==========================================================================

function getBarReplayModule() {
    return (typeof window !== 'undefined' && window.KLineBarReplayModule) || {
        normalizeTimestamp: (t) => (typeof t === 'number' ? (t > 1e11 ? Math.floor(t / 1000) : t) : null),
        findBarIndexByTimestamp: (klines, t) => {
            if (!Array.isArray(klines) || klines.length === 0) return -1;
            const target = typeof t === 'number' ? (t > 1e11 ? Math.floor(t / 1000) : t) : Number(t);
            for (let i = klines.length - 1; i >= 0; i--) {
                const kTime = typeof klines[i].time === 'number' ? (klines[i].time > 1e11 ? Math.floor(klines[i].time / 1000) : klines[i].time) : Number(klines[i].time);
                if (kTime <= target) return i;
            }
            return 0;
        },
        sliceKlineData: (list, idx) => (Array.isArray(list) ? list.slice(0, Math.min(list.length, idx + 1)) : []),
        getNextReplayStep: (cur, max) => ({ nextIndex: Math.min(cur + 1, max), isFinished: cur + 1 >= max }),
        formatReplayTime: (t) => (t ? String(t) : '--'),
        createBarReplayState: () => ({
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
        }),
    };
}

function extractVolumeFromKlines(klines) {
    if (!Array.isArray(klines)) return [];
    const palette = typeof getThemePalette === 'function' ? getThemePalette() : { positive: '#f6465d', negative: '#0ecb81' };
    return klines.map(function (bar) {
        const isUp = Number(bar.close) >= Number(bar.open);
        const volVal = Number(bar.volume ?? bar.vol ?? bar.value) || 0;
        return {
            time: bar.time,
            value: volVal,
            color: isUp ? palette.positive : palette.negative,
        };
    });
}

function updateBarReplayCutIndicator(x) {
    const indicatorEl = document.getElementById('chart-replay-cut-indicator');
    if (!indicatorEl || !chart) return;
    const chartContainer = document.getElementById('chart');
    if (!chartContainer) return;

    const clampedX = Math.max(0, Math.min(chartContainer.clientWidth, x));
    indicatorEl.style.left = `${clampedX}px`;
    indicatorEl.classList.remove('hidden');

    const klinesToUse = barReplayState.fullKlineData.length > 0 ? barReplayState.fullKlineData : latestRenderedKlineData;
    let time = chart.timeScale().coordinateToTime(clampedX);
    let timeStr = '';
    const replayMod = getBarReplayModule();
    if (time) {
        timeStr = replayMod.formatReplayTime(time);
    } else {
        const logical = chart.timeScale().coordinateToLogical(clampedX);
        if (logical !== null && klinesToUse.length > 0) {
            const idx = Math.max(0, Math.min(klinesToUse.length - 1, Math.round(logical)));
            timeStr = replayMod.formatReplayTime(klinesToUse[idx]?.time);
        }
    }
    const badgeEl = indicatorEl.querySelector('.cut-indicator-badge');
    if (badgeEl) {
        badgeEl.textContent = timeStr ? `« 截断至 ${timeStr}` : '« 截断至此';
    }
}

function enterBarReplayCutSelection() {
    const currentBars = barReplayState.active && barReplayState.fullKlineData.length > 0
        ? barReplayState.fullKlineData
        : latestRenderedKlineData;

    if (!Array.isArray(currentBars) || currentBars.length < 2) {
        alert('当前图表K线数量过少，无法执行截断复盘');
        return;
    }

    if (typeof drawingController !== 'undefined' && drawingController?.cancelGesture) {
        drawingController.cancelGesture();
    }

    pauseBarReplay();

    if (barReplayState.active && barReplayState.fullKlineData.length > 0) {
        if (candlestickSeries) candlestickSeries.setData(barReplayState.fullKlineData);
        if (volumeSeries && barReplayState.fullVolumeData) volumeSeries.setData(barReplayState.fullVolumeData);
        replaceRenderedKlineData(barReplayState.fullKlineData);
        updateMaLinesFromRendered();
    }

    barReplayState.isSelectingCutPoint = true;

    const replayBtn = document.getElementById('chart-bar-replay-btn');
    if (replayBtn) {
        replayBtn.classList.add('active');
        replayBtn.setAttribute('aria-pressed', 'true');
    }
    const chartPanels = document.getElementById('chart-panels');
    if (chartPanels) chartPanels.classList.add('bar-replay-cutting');

    const statusEl = document.getElementById('chart-window-status');
    if (statusEl) statusEl.textContent = '【截断复盘】请在图表上点击任意一根K线作为复盘起点 (ESC取消)';
}

function cancelBarReplayCutSelection() {
    barReplayState.isSelectingCutPoint = false;

    const chartPanels = document.getElementById('chart-panels');
    if (chartPanels) chartPanels.classList.remove('bar-replay-cutting');

    const indicatorEl = document.getElementById('chart-replay-cut-indicator');
    if (indicatorEl) indicatorEl.classList.add('hidden');

    if (barReplayState.active && barReplayState.cutIndex >= 0) {
        const replayMod = getBarReplayModule();
        const slicedBars = replayMod.sliceKlineData(barReplayState.fullKlineData, barReplayState.cutIndex);
        const slicedVols = replayMod.sliceKlineData(barReplayState.fullVolumeData, barReplayState.cutIndex);
        if (candlestickSeries) candlestickSeries.setData(slicedBars);
        if (volumeSeries) volumeSeries.setData(slicedVols);
        replaceRenderedKlineData(slicedBars);
        updateMaLinesFromRendered();
        if (indicatorPanelVisible && currentIndicatorType) {
            loadTechnicalIndicators();
        }
    } else {
        const replayBtn = document.getElementById('chart-bar-replay-btn');
        if (replayBtn) {
            replayBtn.classList.remove('active');
            replayBtn.setAttribute('aria-pressed', 'false');
        }
    }

    const statusEl = document.getElementById('chart-window-status');
    if (statusEl && statusEl.textContent.includes('【截断复盘】')) {
        statusEl.textContent = '';
    }
}

function executeBarReplayCut(cutIndex) {
    const replayMod = getBarReplayModule();

    if (!barReplayState.active || !barReplayState.fullKlineData.length) {
        barReplayState.fullKlineData = latestRenderedKlineData.map(b => ({ ...b }));
        barReplayState.fullVolumeData = (Array.isArray(latestRenderedVolumeData) && latestRenderedVolumeData.length === barReplayState.fullKlineData.length)
            ? latestRenderedVolumeData.map(v => ({ ...v }))
            : extractVolumeFromKlines(barReplayState.fullKlineData);
        barReplayState.originalSymbol = isAshareLiveMode ? currentAshareSymbol : (currentTraining?.symbol || null);
        barReplayState.originalPeriod = isAshareLiveMode ? currentAsharePeriod : (currentTraining?.period || currentPeriod);
    }

    const totalLen = barReplayState.fullKlineData.length;
    const clampedIndex = Math.max(0, Math.min(totalLen - 1, cutIndex));

    barReplayState.cutIndex = clampedIndex;
    barReplayState.cutTimestamp = barReplayState.fullKlineData[clampedIndex].time;
    barReplayState.active = true;
    barReplayState.isSelectingCutPoint = false;
    pauseBarReplay();

    const chartPanels = document.getElementById('chart-panels');
    if (chartPanels) chartPanels.classList.remove('bar-replay-cutting');
    const indicatorEl = document.getElementById('chart-replay-cut-indicator');
    if (indicatorEl) indicatorEl.classList.add('hidden');

    const replayBar = document.getElementById('chart-bar-replay-bar');
    if (replayBar) replayBar.classList.remove('hidden');

    const replayBtn = document.getElementById('chart-bar-replay-btn');
    if (replayBtn) {
        replayBtn.classList.add('active');
        replayBtn.setAttribute('aria-pressed', 'true');
    }

    const slicedBars = replayMod.sliceKlineData(barReplayState.fullKlineData, clampedIndex);
    const slicedVols = replayMod.sliceKlineData(barReplayState.fullVolumeData, clampedIndex);

    if (candlestickSeries) candlestickSeries.setData(slicedBars);
    if (volumeSeries) volumeSeries.setData(slicedVols);

    replaceRenderedKlineData(slicedBars, slicedVols);
    updateMaLinesFromRendered();
    applyLastPriceTagColor();
    showLatestChartInfo();

    if (indicatorPanelVisible && currentIndicatorType) {
        loadTechnicalIndicators();
    }

    updateBarReplayProgressUI();

    if (slicedBars.length > 120) {
        setVisibleRangeAll({
            from: Math.max(0, slicedBars.length - 100),
            to: slicedBars.length + 5,
        });
    } else {
        [chart, volumeChart, indicatorChart].forEach(c => c?.timeScale().fitContent());
    }

    const statusEl = document.getElementById('chart-window-status');
    if (statusEl) {
        statusEl.textContent = `已截断复盘至 ${replayMod.formatReplayTime(barReplayState.cutTimestamp)} (第 ${clampedIndex + 1}/${totalLen} 根)`;
    }
}

/**
 * 切换周期时跨周期平滑继承复盘状态，对齐到新周期对应的历史截断 bar。
 */
function handleBarReplayPeriodSwitch(newKlines, newVolumes, newPeriod) {
    if (!barReplayState.active || !Array.isArray(newKlines) || newKlines.length === 0) {
        return false;
    }
    const replayMod = getBarReplayModule();

    // 1. 获取切换前当前的复盘时间戳
    const currentReplayTime = (barReplayState.cutIndex >= 0 && barReplayState.fullKlineData[barReplayState.cutIndex])
        ? barReplayState.fullKlineData[barReplayState.cutIndex].time
        : barReplayState.cutTimestamp;

    // 2. 将当前复盘的全量数据更新为新周期的全量数据
    barReplayState.fullKlineData = newKlines.map(b => ({ ...b }));
    barReplayState.fullVolumeData = (Array.isArray(newVolumes) && newVolumes.length > 0)
        ? newVolumes.map(v => ({ ...v }))
        : extractVolumeFromKlines(barReplayState.fullKlineData);

    if (newPeriod) {
        barReplayState.originalPeriod = newPeriod;
    }

    // 3. 在新周期的全量数据中，寻找与当前复盘点最佳对应的截断索引
    let newCutIndex = -1;
    if (typeof replayMod.mapReplayCutToNewPeriod === 'function') {
        newCutIndex = replayMod.mapReplayCutToNewPeriod(currentReplayTime, barReplayState.fullKlineData);
    } else {
        newCutIndex = replayMod.findBarIndexByTimestamp(barReplayState.fullKlineData, currentReplayTime);
    }

    if (newCutIndex < 0) {
        newCutIndex = 0;
    }

    // 4. 更新复盘截断索引与时间戳
    barReplayState.cutIndex = newCutIndex;
    barReplayState.cutTimestamp = barReplayState.fullKlineData[newCutIndex]?.time ?? currentReplayTime;

    // 5. 对新周期数据进行切片并渲染到图表
    const slicedBars = replayMod.sliceKlineData(barReplayState.fullKlineData, newCutIndex);
    const slicedVols = replayMod.sliceKlineData(barReplayState.fullVolumeData, newCutIndex);

    if (candlestickSeries) candlestickSeries.setData(slicedBars);
    if (volumeSeries) volumeSeries.setData(slicedVols);

    replaceRenderedKlineData(slicedBars, slicedVols);
    updateMaLinesFromRendered();
    applyLastPriceTagColor();
    showLatestChartInfo();

    if (indicatorPanelVisible && currentIndicatorType) {
        loadTechnicalIndicators();
    }

    // 6. 更新底部悬浮复盘控制栏的进度与时间
    updateBarReplayProgressUI();

    // 7. 确保悬浮控制栏保持显示，复盘按钮保持激活
    const replayBar = document.getElementById('chart-bar-replay-bar');
    if (replayBar) replayBar.classList.remove('hidden');

    const replayBtn = document.getElementById('chart-bar-replay-btn');
    if (replayBtn) {
        replayBtn.classList.add('active');
        replayBtn.setAttribute('aria-pressed', 'true');
    }

    // 8. 调整视野对齐到截断点
    if (slicedBars.length > 120) {
        setVisibleRangeAll({
            from: Math.max(0, slicedBars.length - 100),
            to: slicedBars.length + 5,
        });
    } else {
        [chart, volumeChart, indicatorChart].forEach(c => c?.timeScale().fitContent());
    }

    const statusEl = document.getElementById('chart-window-status');
    if (statusEl) {
        statusEl.textContent = `已切换周期并同步复盘至 ${replayMod.formatReplayTime(barReplayState.cutTimestamp)} (第 ${newCutIndex + 1}/${barReplayState.fullKlineData.length} 根)`;
    }

    return true;
}

function updateBarReplayProgressUI() {
    if (!barReplayState.active || !barReplayState.fullKlineData.length) return;
    const replayMod = getBarReplayModule();
    const currentBar = barReplayState.fullKlineData[barReplayState.cutIndex];
    const timeStr = currentBar ? replayMod.formatReplayTime(currentBar.time) : '--';
    const total = barReplayState.fullKlineData.length;
    const currentPos = barReplayState.cutIndex + 1;

    const timeEl = document.getElementById('replay-progress-time');
    if (timeEl) timeEl.textContent = timeStr;
    const fracEl = document.getElementById('replay-progress-fraction');
    if (fracEl) fracEl.textContent = `(${currentPos}/${total})`;
}

function stepBarReplayForward() {
    if (!barReplayState.active || !barReplayState.fullKlineData.length) return;
    const replayMod = getBarReplayModule();
    const maxIndex = barReplayState.fullKlineData.length - 1;
    const step = replayMod.getNextReplayStep(barReplayState.cutIndex, maxIndex);

    if (step.nextIndex === barReplayState.cutIndex && step.isFinished) {
        pauseBarReplay();
        const statusEl = document.getElementById('chart-window-status');
        if (statusEl) statusEl.textContent = '已回放到最新K线';
        return;
    }

    barReplayState.cutIndex = step.nextIndex;
    const nextBar = barReplayState.fullKlineData[step.nextIndex];
    if (!nextBar) return;
    barReplayState.cutTimestamp = nextBar.time;
    const nextVol = barReplayState.fullVolumeData ? barReplayState.fullVolumeData[step.nextIndex] : null;

    if (candlestickSeries && nextBar) candlestickSeries.update(nextBar);
    if (volumeSeries && nextVol) volumeSeries.update(nextVol);

    upsertRenderedBar(nextBar, nextVol);
    updateMaLinesFromRendered();
    applyLastPriceTagColor();
    showLatestChartInfo();

    if (indicatorPanelVisible && currentIndicatorType) {
        loadTechnicalIndicators();
    }

    updateBarReplayProgressUI();

    // 保持新推进的蜡烛处于可视区域内
    try {
        const visibleLogicalRange = chart?.timeScale().getVisibleLogicalRange?.();
        if (visibleLogicalRange && Number.isFinite(visibleLogicalRange.to)) {
            const currentTotalBars = latestRenderedKlineData.length;
            if (currentTotalBars > visibleLogicalRange.to - 2) {
                chart.timeScale().scrollToPosition(3, false);
            }
        }
    } catch (e) {}

    if (step.isFinished) {
        pauseBarReplay();
        const statusEl = document.getElementById('chart-window-status');
        if (statusEl) statusEl.textContent = '已回放到最新K线';
    }
}

function playBarReplay() {
    if (!barReplayState.active) return;
    if (barReplayState.cutIndex >= barReplayState.fullKlineData.length - 1) {
        return;
    }

    barReplayState.isPlaying = true;
    const playBtn = document.getElementById('replay-play-pause-btn');
    if (playBtn) {
        playBtn.classList.add('playing');
        playBtn.title = '暂停 (空格键)';
        playBtn.querySelector('.icon-play')?.classList.add('hidden');
        playBtn.querySelector('.icon-pause')?.classList.remove('hidden');
    }

    if (barReplayState.timerId) {
        clearInterval(barReplayState.timerId);
    }
    barReplayState.timerId = setInterval(() => {
        stepBarReplayForward();
    }, barReplayState.playbackSpeed);
}

function pauseBarReplay() {
    barReplayState.isPlaying = false;
    if (barReplayState.timerId) {
        clearInterval(barReplayState.timerId);
        barReplayState.timerId = null;
    }
    const playBtn = document.getElementById('replay-play-pause-btn');
    if (playBtn) {
        playBtn.classList.remove('playing');
        playBtn.title = '播放 (空格键)';
        playBtn.querySelector('.icon-play')?.classList.remove('hidden');
        playBtn.querySelector('.icon-pause')?.classList.add('hidden');
    }
}

function toggleBarReplayPlayPause() {
    if (!barReplayState.active) return;
    if (barReplayState.isPlaying) {
        pauseBarReplay();
    } else {
        playBarReplay();
    }
}

function exitBarReplay() {
    if (!barReplayState.active) {
        if (barReplayState.isSelectingCutPoint) {
            cancelBarReplayCutSelection();
        }
        return;
    }

    pauseBarReplay();

    if (barReplayState.fullKlineData && barReplayState.fullKlineData.length > 0) {
        if (candlestickSeries) candlestickSeries.setData(barReplayState.fullKlineData);
        if (volumeSeries && barReplayState.fullVolumeData && barReplayState.fullVolumeData.length > 0) {
            volumeSeries.setData(barReplayState.fullVolumeData);
        }
        replaceRenderedKlineData(barReplayState.fullKlineData, barReplayState.fullVolumeData);
        updateMaLinesFromRendered();
        applyLastPriceTagColor();
        showLatestChartInfo();
        if (indicatorPanelVisible && currentIndicatorType) {
            loadTechnicalIndicators();
        }
        scrollToLatestKline({ visibleBars: 80, rightOffset: 5 });
    }

    const replayMod = getBarReplayModule();
    barReplayState = replayMod.createBarReplayState();

    const replayBar = document.getElementById('chart-bar-replay-bar');
    if (replayBar) replayBar.classList.add('hidden');
    const indicatorEl = document.getElementById('chart-replay-cut-indicator');
    if (indicatorEl) indicatorEl.classList.add('hidden');
    const chartPanels = document.getElementById('chart-panels');
    if (chartPanels) chartPanels.classList.remove('bar-replay-cutting');

    const replayBtn = document.getElementById('chart-bar-replay-btn');
    if (replayBtn) {
        replayBtn.classList.remove('active');
        replayBtn.setAttribute('aria-pressed', 'false');
    }

    const statusEl = document.getElementById('chart-window-status');
    if (statusEl) statusEl.textContent = '已退出复盘，回到当前实时行情';
}

function toggleBarReplayCutSelection() {
    if (barReplayState.isSelectingCutPoint) {
        cancelBarReplayCutSelection();
    } else if (barReplayState.active) {
        enterBarReplayCutSelection();
    } else {
        enterBarReplayCutSelection();
    }
}

function registerBarReplayChartEvents(chartInstance) {
    if (!chartInstance) return;

    chartInstance.subscribeClick((param) => {
        if (!barReplayState.isSelectingCutPoint) return;
        const klinesToUse = barReplayState.active && barReplayState.fullKlineData.length > 0
            ? barReplayState.fullKlineData
            : latestRenderedKlineData;
        if (!klinesToUse || klinesToUse.length === 0) return;

        let cutIndex = -1;
        const replayMod = getBarReplayModule();
        if (param && param.time) {
            cutIndex = replayMod.findBarIndexByTimestamp(klinesToUse, param.time);
        } else if (param && param.point) {
            const time = chartInstance.timeScale().coordinateToTime(param.point.x);
            if (time) {
                cutIndex = replayMod.findBarIndexByTimestamp(klinesToUse, time);
            } else {
                const logical = chartInstance.timeScale().coordinateToLogical(param.point.x);
                if (logical !== null) {
                    cutIndex = Math.max(0, Math.min(klinesToUse.length - 1, Math.round(logical)));
                }
            }
        }
        if (cutIndex >= 0) {
            executeBarReplayCut(cutIndex);
        }
    });

    chartInstance.subscribeCrosshairMove((param) => {
        if (!barReplayState.isSelectingCutPoint) return;
        if (param && param.point && param.point.x >= 0) {
            updateBarReplayCutIndicator(param.point.x);
        }
    });
}

function initBarReplayToolbarEvents() {
    const replayBtn = document.getElementById('chart-bar-replay-btn');
    if (replayBtn && !replayBtn.dataset.bound) {
        replayBtn.dataset.bound = 'true';
        replayBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleBarReplayCutSelection();
        });
    }

    const playPauseBtn = document.getElementById('replay-play-pause-btn');
    if (playPauseBtn && !playPauseBtn.dataset.bound) {
        playPauseBtn.dataset.bound = 'true';
        playPauseBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleBarReplayPlayPause();
        });
    }

    const stepBtn = document.getElementById('replay-step-forward-btn');
    if (stepBtn && !stepBtn.dataset.bound) {
        stepBtn.dataset.bound = 'true';
        stepBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            stepBarReplayForward();
        });
    }

    const reselectBtn = document.getElementById('replay-reselect-cut-btn');
    if (reselectBtn && !reselectBtn.dataset.bound) {
        reselectBtn.dataset.bound = 'true';
        reselectBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            enterBarReplayCutSelection();
        });
    }

    const speedSelect = document.getElementById('replay-speed-select');
    if (speedSelect && !speedSelect.dataset.bound) {
        speedSelect.dataset.bound = 'true';
        speedSelect.addEventListener('change', (e) => {
            const sp = parseInt(e.target.value, 10) || 1000;
            barReplayState.playbackSpeed = sp;
            if (barReplayState.isPlaying) {
                playBarReplay();
            }
        });
    }

    const exitBtn = document.getElementById('replay-exit-btn');
    if (exitBtn && !exitBtn.dataset.bound) {
        exitBtn.dataset.bound = 'true';
        exitBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            exitBarReplay();
        });
    }

    // 绑定复盘控制栏自由拖拽移动
    const replayBar = document.getElementById('chart-bar-replay-bar');
    const dragHandle = replayBar?.querySelector('.replay-bar-drag-handle') || replayBar;
    if (replayBar && !replayBar.dataset.dragBound) {
        replayBar.dataset.dragBound = 'true';
        let isDragging = false;
        let startClientX = 0, startClientY = 0;
        let startLeft = 0, startTop = 0;

        const onDragStart = (e) => {
            if (e.type === 'mousedown' && e.button !== 0) return;
            const target = e.target;
            if (target.closest('button') || target.closest('select') || target.closest('input')) return;

            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            startClientX = clientX;
            startClientY = clientY;

            const parentRect = replayBar.offsetParent ? replayBar.offsetParent.getBoundingClientRect() : { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
            const barRect = replayBar.getBoundingClientRect();

            startLeft = barRect.left - parentRect.left;
            startTop = barRect.top - parentRect.top;

            isDragging = true;
            replayBar.classList.add('dragging');
            replayBar.style.transform = 'none';
            replayBar.style.bottom = 'auto';
            replayBar.style.left = `${startLeft}px`;
            replayBar.style.top = `${startTop}px`;

            document.addEventListener('mousemove', onDragMove, { passive: false });
            document.addEventListener('mouseup', onDragEnd);
            document.addEventListener('touchmove', onDragMove, { passive: false });
            document.addEventListener('touchend', onDragEnd);
            if (e.cancelable) e.preventDefault();
        };

        const onDragMove = (e) => {
            if (!isDragging) return;
            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            const dx = clientX - startClientX;
            const dy = clientY - startClientY;

            const parentEl = replayBar.offsetParent || document.body;
            const parentWidth = parentEl.clientWidth || window.innerWidth;
            const parentHeight = parentEl.clientHeight || window.innerHeight;
            const barWidth = replayBar.offsetWidth || 300;
            const barHeight = replayBar.offsetHeight || 40;

            const minLeft = 8;
            const maxLeft = Math.max(minLeft, parentWidth - barWidth - 8);
            const minTop = 8;
            const maxTop = Math.max(minTop, parentHeight - barHeight - 8);

            const clampedLeft = Math.min(Math.max(minLeft, startLeft + dx), maxLeft);
            const clampedTop = Math.min(Math.max(minTop, startTop + dy), maxTop);

            replayBar.style.left = `${clampedLeft}px`;
            replayBar.style.top = `${clampedTop}px`;
            if (e.cancelable) e.preventDefault();
        };

        const onDragEnd = () => {
            if (!isDragging) return;
            isDragging = false;
            replayBar.classList.remove('dragging');
            document.removeEventListener('mousemove', onDragMove);
            document.removeEventListener('mouseup', onDragEnd);
            document.removeEventListener('touchmove', onDragMove);
            document.removeEventListener('touchend', onDragEnd);
        };

        dragHandle.addEventListener('mousedown', onDragStart);
        dragHandle.addEventListener('touchstart', onDragStart, { passive: false });
        dragHandle.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            replayBar.style.left = '50%';
            replayBar.style.top = '64px';
            replayBar.style.transform = 'translateX(-50%)';
            replayBar.style.bottom = 'auto';
        });
    }

    const chartContainer = document.getElementById('chart');
    if (chartContainer && !chartContainer.dataset.barReplayBound) {
        chartContainer.dataset.barReplayBound = 'true';
        chartContainer.addEventListener('mouseleave', () => {
            if (barReplayState.isSelectingCutPoint) {
                const indicatorEl = document.getElementById('chart-replay-cut-indicator');
                if (indicatorEl) indicatorEl.classList.add('hidden');
            }
        });

        chartContainer.addEventListener('mousemove', (e) => {
            if (!barReplayState.isSelectingCutPoint) return;
            const rect = chartContainer.getBoundingClientRect();
            const x = e.clientX - rect.left;
            updateBarReplayCutIndicator(x);
        });

        chartContainer.addEventListener('click', (e) => {
            if (!barReplayState.isSelectingCutPoint) return;
            const rect = chartContainer.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const klinesToUse = barReplayState.active && barReplayState.fullKlineData.length > 0
                ? barReplayState.fullKlineData
                : latestRenderedKlineData;
            if (!klinesToUse || klinesToUse.length === 0 || !chart) return;

            const replayMod = getBarReplayModule();
            let cutIndex = -1;
            const time = chart.timeScale().coordinateToTime(x);
            if (time) {
                cutIndex = replayMod.findBarIndexByTimestamp(klinesToUse, time);
            } else {
                const logical = chart.timeScale().coordinateToLogical(x);
                if (logical !== null) {
                    cutIndex = Math.max(0, Math.min(klinesToUse.length - 1, Math.round(logical)));
                }
            }
            if (cutIndex >= 0) {
                executeBarReplayCut(cutIndex);
            }
        });
    }
}

// async function loadInitialData() {
//     try {
//         const response = await fetch(`${API_BASE}/training/${currentTraining.id}/data`);
//         const data = await response.json();
//
//         // 更新股票信息
//         document.getElementById('stock-name').textContent = data.stock_name || '未知股票';
//
//         // 加载初始K线数据
//         if (data.kline_data && data.kline_data.length > 0) {
//             candlestickSeries.setData(data.kline_data);
//             volumeSeries.setData(data.volume_data);
//
//             // 加载移动平均线数据
//             if (data.ma_data) {
//                 maSeries[5].setData(data.ma_data[5] || []);
//                 maSeries[10].setData(data.ma_data[10] || []);
//                 maSeries[20].setData(data.ma_data[20] || []);
//             }
//
//             // 更新当前日期和价格信息
//             const currentBar = data.kline_data[data.kline_data.length - 1];
//             updateCurrentInfo(currentBar, data.progress);
//
//             // 加载交易标记
//             updateTradeMarkers(data.trade_markers || []);
//         }
//
//         // 加载技术指标
//         await loadTechnicalIndicator(currentIndicatorType);
//
//         updateAccountInfo();
//
//     } catch (error) {
//         console.error('加载初始数据失败:', error);
//         alert('加载数据失败');
//     }
// }
/**
 * 加载初始训练数据。
 * 包含一次自动重置和重试的容错逻辑。
 */
async function loadInitialData() {
    // === intraday_30m 分支: 直接从 currentTraining（start 返回的顶层 snapshot）渲染 ===
    if (isIntradayMode()) {
        try {
            const snapshot = extractIntradaySnapshot(currentTraining);
            if (snapshot && snapshot.kline_data && snapshot.kline_data.length > 0) {
                applyIntradaySnapshot(snapshot, { fitContent: true });
                await updateAccountInfo();
                return;
            }
            // 若 start 响应没有携带 snapshot，则回退到 GET /data
            const response = await fetch(`${API_BASE}/training/${currentTraining.id}/data`);
            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }
            const data = await response.json();
            const fallbackSnapshot = extractIntradaySnapshot(data);
            if (fallbackSnapshot && fallbackSnapshot.kline_data && fallbackSnapshot.kline_data.length > 0) {
                applyIntradaySnapshot(fallbackSnapshot, { fitContent: true });
                await updateAccountInfo();
                return;
            }
            throw new Error('intraday 训练数据为空');
        } catch (error) {
            console.error('加载 intraday 初始数据失败:', error);
            alert('加载数据失败，请尝试重新开始一局训练。');
            resetToMainAppState();
        }
        return;
    }

    // === legacy_daily 分支 (原逻辑) ===
    // 内部函数，用于执行实际的数据加载尝试
    const attemptToLoad = async () => {
        const maQuery = maPeriods.join(',');
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/data?ma_periods=${maQuery}&${getViewPeriodQuery()}`);
        if (!response.ok) {
            // 如果响应不成功，直接抛出错误，由外部的catch块处理
            throw new Error(`Server responded with status: ${response.status}`);
        }
        const data = await response.json();

        // 更新股票信息
        document.getElementById('stock-name').textContent = data.stock_name || '未知股票';
        applyTrainingSnapshot(data);

        // 加载技术指标
        await loadTechnicalIndicators();

        updateAccountInfo();
    };

    try {
        // 第一次尝试加载数据
        await attemptToLoad();
    } catch (error) {
        console.error('初次加载初始数据失败:', error);
        console.log('正在尝试自动重置训练并重新加载...');

        try {
            // 自动重置训练
            const resetResponse = await fetch(`${API_BASE}/training/${currentTraining.id}/reset`, {
                method: 'POST'
            });

            if (!resetResponse.ok) {
                // 如果连重置都失败了，那就没有办法了
                throw new Error('自动重置训练失败，无法恢复。');
            }

            console.log('训练已成功重置，正在进行第二次加载尝试...');

            // 清理UI上的旧交易记录
            document.getElementById('trade-history').innerHTML = '<div class="no-trades">暂无交易记录</div>';

            // 第二次尝试加载数据
            await attemptToLoad();

            console.log('第二次加载成功！');

        } catch (finalError) {
            console.error('自动重置或第二次加载失败:', finalError);
            // 只有在重试也失败后，才向用户显示最终的错误提示
            alert('加载数据失败，请尝试重新开始一局训练。');

            // 加载失败后，最好将用户带回到主界面
            resetToMainAppState();
        }
    }
}

function formatMarketPrice(value) {
    const formatted = Number(value).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
    return isCryptoMode() ? formatted + ' USDT' : '¥' + formatted;
}

function formatCryptoToolbarPrice(value) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return '--';
    const absoluteValue = Math.abs(numericValue);
    const maximumFractionDigits = absoluteValue >= 100 ? 2 : absoluteValue >= 1 ? 4 : 8;
    return numericValue.toLocaleString(undefined, {maximumFractionDigits});
}

function formatCryptoToolbarVolume(value) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return '--';
    const units = [
        {threshold: 1e9, divisor: 1e9, suffix: 'B'},
        {threshold: 1e6, divisor: 1e6, suffix: 'M'},
        {threshold: 1e3, divisor: 1e3, suffix: 'K'},
    ];
    const unit = units.find(item => Math.abs(numericValue) >= item.threshold);
    if (!unit) return numericValue.toLocaleString();
    return `${Number((numericValue / unit.divisor).toFixed(2))}${unit.suffix}`;
}

// === Visible Range Extreme Price Tags (AICoin style: High / Low markers) ===
// 渲染逻辑已抽取到 modules/extreme_tags.js，此处仅保留 raf 调度与全局注入。
const {
    updateVisibleExtremePriceTags: updateVisibleExtremePriceTagsFor,
} = window.KLineExtremeTagsModule || {};
let extremePriceTagsRafId = null;

function scheduleExtremePriceTagsUpdate() {
    if (extremePriceTagsRafId) return;
    extremePriceTagsRafId = requestAnimationFrame(() => {
        extremePriceTagsRafId = null;
        updateVisibleExtremePriceTags();
    });
}

function updateVisibleExtremePriceTags() {
    updateVisibleExtremePriceTagsFor(chart, candlestickSeries, latestRenderedKlineData);
}

// === 做单时段色带（仅币圈 4H 以下周期；时段与开关在图表工具栏"做单"处配置） ===
let tradingHoursRafId = null;
let tradingHoursEnabled = true;

function scheduleTradingHoursBandsUpdate() {
    if (tradingHoursRafId) return;
    tradingHoursRafId = requestAnimationFrame(() => {
        tradingHoursRafId = null;
        renderTradingHoursBands();
    });
}

function renderTradingHoursBands() {
    const chartContainer = document.getElementById('chart');
    if (!chart || !chartContainer) return;
    const scoped = isCryptoMode() && isIntradayCryptoPeriod(currentPeriod);
    const controls = document.getElementById('trading-hours-controls');
    if (controls) {
        controls.classList.toggle('hidden', !scoped);
        controls.classList.toggle('disabled', !tradingHoursEnabled);
    }
    const toggleBtn = document.getElementById('trading-hours-toggle-btn');
    if (toggleBtn) {
        toggleBtn.classList.toggle('active', tradingHoursEnabled);
        toggleBtn.setAttribute('aria-pressed', String(tradingHoursEnabled));
    }
    const trainingHidden = document.getElementById('training-interface')?.classList.contains('hidden');
    if (!scoped || trainingHidden || !tradingHoursEnabled) {
        clearTradingHoursBands(chartContainer);
        return;
    }
    const rightScaleWidth = Number(chart.priceScale?.('right')?.width?.()) || 0;
    drawTradingHoursBands({
        chart,
        container: chartContainer,
        hours: getTradingHours(),
        color: getThemePalette().sessionBand,
        rightPad: rightScaleWidth,
    });
}

function updateTradingHoursControls() {
    const hours = getTradingHours();
    const startSelect = document.getElementById('trading-hours-start');
    const endSelect = document.getElementById('trading-hours-end');
    if (startSelect) startSelect.value = String(hours.start);
    if (endSelect) endSelect.value = String(hours.end);
}

function populateTradingHoursControls() {
    const startSelect = document.getElementById('trading-hours-start');
    const endSelect = document.getElementById('trading-hours-end');
    if (startSelect && startSelect.options.length === 0) {
        startSelect.innerHTML = Array.from({ length: 24 }, (_, h) =>
            `<option value="${h}">${String(h).padStart(2, '0')}:00</option>`).join('');
    }
    if (endSelect && endSelect.options.length === 0) {
        endSelect.innerHTML = Array.from({ length: 24 }, (_, i) => {
            const h = i + 1;
            return `<option value="${h}">${h === 24 ? '24:00' : String(h).padStart(2, '0') + ':00'}</option>`;
        }).join('');
    }
    updateTradingHoursControls();
}

function applyTradingHoursFromSettings(settings) {
    const start = Number(settings?.trading_hours_start);
    const end = Number(settings?.trading_hours_end);
    if (Number.isInteger(start) && start >= 0 && start <= 23) setTradingHours(start, getTradingHours().end);
    if (Number.isInteger(end) && end >= 1 && end <= 24) setTradingHours(getTradingHours().start, end);
    if (settings?.trading_hours_enabled !== undefined) {
        tradingHoursEnabled = Number(settings.trading_hours_enabled) === 1 || settings.trading_hours_enabled === true;
    }
    updateTradingHoursControls();
    scheduleTradingHoursBandsUpdate();
}

function saveTradingHoursLocal() {
    localStorage.setItem('tradingHours', JSON.stringify({
        start: getTradingHours().start,
        end: getTradingHours().end,
        enabled: tradingHoursEnabled,
    }));
}

function onTradingHoursChange() {
    const startValue = document.getElementById('trading-hours-start')?.value;
    const endValue = document.getElementById('trading-hours-end')?.value;
    const hours = setTradingHours(startValue, endValue);
    saveTradingHoursLocal();
    persistUserSettings({
        trading_hours_start: hours.start,
        trading_hours_end: hours.end,
        trading_hours_enabled: tradingHoursEnabled ? 1 : 0,
    });
    renderTradingHoursBands();
}

function onTradingHoursToggle() {
    tradingHoursEnabled = !tradingHoursEnabled;
    saveTradingHoursLocal();
    persistUserSettings({ trading_hours_enabled: tradingHoursEnabled ? 1 : 0 });
    renderTradingHoursBands();
}

function initTradingHours() {
    try {
        const saved = JSON.parse(localStorage.getItem('tradingHours') || 'null');
        if (saved) {
            setTradingHours(saved.start, saved.end);
            if (typeof saved.enabled === 'boolean') tradingHoursEnabled = saved.enabled;
        }
    } catch (error) {
        console.error('读取做单时段设置失败:', error);
    }
    populateTradingHoursControls();
    document.getElementById('trading-hours-start')?.addEventListener('change', onTradingHoursChange);
    document.getElementById('trading-hours-end')?.addEventListener('change', onTradingHoursChange);
    document.getElementById('trading-hours-toggle-btn')?.addEventListener('click', onTradingHoursToggle);
}

function updateElementText(elementId, text, color) {
    const element = document.getElementById(elementId);
    if (!element) return;
    element.textContent = text;
    if (color) element.style.color = color;
}

function updateCurrentInfo(barData, progress) {
    if (!barData) return;
    const palette = getThemePalette();

    let formattedDate = '';
    if (typeof formatChartCrosshairTime === 'function') {
        formattedDate = formatChartCrosshairTime(barData.time);
    } else {
        const date = new Date(barData.time * 1000);
        const year = date.getUTCFullYear();
        const month = String(date.getUTCMonth() + 1).padStart(2, '0');
        const day = String(date.getUTCDate()).padStart(2, '0');
        const hours = String(date.getUTCHours()).padStart(2, '0');
        const minutes = String(date.getUTCMinutes()).padStart(2, '0');
        formattedDate = (hours !== '00' || minutes !== '00')
            ? `${year}-${month}-${day} ${hours}:${minutes}`
            : `${year}-${month}-${day}`;
    }
    document.getElementById('current-date').textContent = formattedDate;
    document.getElementById('current-price').textContent = formatMarketPrice(barData.close);

    // 显示当前bar ID
    document.getElementById('current-bar-id').textContent = `Bar ID: ${barData.bar_id || 'N/A'}`;

    // 更新当日详情
    document.getElementById('open-price').textContent = formatMarketPrice(barData.open);
    document.getElementById('high-price').textContent = formatMarketPrice(barData.high);
    document.getElementById('low-price').textContent = formatMarketPrice(barData.low);
    document.getElementById('close-price').textContent = formatMarketPrice(barData.close);
    updateElementText('crypto-open-price', formatCryptoToolbarPrice(barData.open));
    updateElementText('crypto-high-price', formatCryptoToolbarPrice(barData.high));
    updateElementText('crypto-low-price', formatCryptoToolbarPrice(barData.low));
    updateElementText('crypto-close-price', formatCryptoToolbarPrice(barData.close));

    // 更新成交量
    if (barData.volume !== undefined) {
        let volText = barData.volume;
        if (volText >= 100000000) {
            volText = (volText / 100000000).toFixed(2) + '亿';
        } else if (volText >= 10000) {
            volText = (volText / 10000).toFixed(2) + '万';
        } else {
            volText = volText.toString();
        }
        document.getElementById('volume').textContent = volText;
        updateElementText('crypto-volume', formatCryptoToolbarVolume(barData.volume));
    } else {
        document.getElementById('volume').textContent = `--`;
        updateElementText('crypto-volume', '--');
    }

    // 计算涨跌幅（优先使用后端的lastClose，其次退化到图表的前一根的数据）
    if (progress && progress.current_bar_id > 1) {
        let prevClose = barData.lastClose;
        if (prevClose === undefined) {
            // 如果后端没有传lastClose，则尝试从本地的K线图表获取最后第二根数据的收盘价
            const localData = latestRenderedKlineData;
            if (localData && localData.length >= 2) {
                prevClose = localData[localData.length - 2].close;
            }
        }
        
        if (prevClose !== undefined && prevClose > 0) {
            const changePercent = ((barData.close - prevClose) / prevClose * 100).toFixed(2);
            document.getElementById('change-percent').textContent = `${changePercent}%`;
            document.getElementById('change-percent').style.color = changePercent > 0 ? palette.positive : changePercent < 0 ? palette.negative : palette.neutral;
            updateElementText(
                'crypto-change-percent', `${changePercent}%`,
                changePercent > 0 ? palette.positive : changePercent < 0 ? palette.negative : palette.neutral
            );
        } else {
            document.getElementById('change-percent').textContent = `--%`;
            document.getElementById('change-percent').style.color = palette.neutral;
            updateElementText('crypto-change-percent', '--%', palette.neutral);
        }
    } else {
        document.getElementById('change-percent').textContent = `--%`;
        document.getElementById('change-percent').style.color = palette.neutral;
        updateElementText('crypto-change-percent', '--%', palette.neutral);
    }

    // 更新进度信息
    if (progress) {
        const trainingProgress = Number(progress.training_progress);
        const currentBarId = Number(progress.current_bar_id);
        const totalBars = Number(progress.training_total_bars ?? (Number(progress.total_bars) - Number(progress.preview_bars)));
        if (Number.isFinite(trainingProgress) && Number.isFinite(currentBarId) && Number.isFinite(totalBars)) {
            document.getElementById('training-progress').textContent =
                `进度: ${trainingProgress.toFixed(1)}% (${currentBarId}/${totalBars})`;
        }
    }

    // === 涨停/跌停检测 ===
    checkLimitStatus(barData, progress);
}

// 涨停/跌停状态检测
let currentLimitStatus = null; // null | 'limit_up' | 'limit_down'

function checkLimitStatus(barData, progress) {
    const limitStatusEl = document.getElementById('limit-status');
    const buyBtn = document.getElementById('buy-btn');
    const sellBtn = document.getElementById('sell-btn');
    if (!limitStatusEl || !buyBtn || !sellBtn) return;

    if (!progress || progress.current_bar_id <= 1 || !barData.lastClose || barData.lastClose <= 0) {
        limitStatusEl.className = 'limit-status hidden';
        limitStatusEl.textContent = '';
        buyBtn.disabled = false;
        sellBtn.disabled = false;
        currentLimitStatus = null;
        return;
    }

    const prevClose = barData.lastClose;
    const close = barData.close;

    // 判断板块：创业板(30x)/科创板(68x) 涨跌幅20%，主板10%
    const stockCode = currentTraining ? currentTraining.stock_code : '';
    let limitPct = 0.10; // 默认主板
    if (stockCode.startsWith('30') || stockCode.startsWith('68')) {
        limitPct = 0.20;
    } else if (stockCode.startsWith('43') || stockCode.startsWith('83') || stockCode.startsWith('87') || stockCode.startsWith('92')) {
        limitPct = 0.30; // 北交所
    }

    const limitUpPrice = prevClose * (1 + limitPct);
    const limitDownPrice = prevClose * (1 - limitPct);
    const threshold = prevClose * 0.001; // 容差

    // 涨停：收盘价 >= 涨停价（允许微小误差）
    if (close >= limitUpPrice - threshold) {
        currentLimitStatus = 'limit_up';
        limitStatusEl.className = 'limit-status limit-up';
        limitStatusEl.textContent = `涨停 ¥${limitUpPrice.toFixed(2)} — 无法买入`;
        buyBtn.disabled = currentOrderType === 'market';
        sellBtn.disabled = false;
    }
    // 跌停：收盘价 <= 跌停价
    else if (close <= limitDownPrice + threshold) {
        currentLimitStatus = 'limit_down';
        limitStatusEl.className = 'limit-status limit-down';
        limitStatusEl.textContent = `跌停 ¥${limitDownPrice.toFixed(2)} — 无法卖出`;
        buyBtn.disabled = false;
        sellBtn.disabled = true;
    }
    else {
        currentLimitStatus = null;
        limitStatusEl.className = 'limit-status hidden';
        limitStatusEl.textContent = '';
        buyBtn.disabled = false;
        sellBtn.disabled = false;
    }
}

// function updateTradeMarkers(markers) {
//     if (!tradeMarkerSeries || !markers) return;
//
//     const markerData = markers.map(marker => ({
//         time: marker.time,
//         position: marker.type === 'B' ? 'aboveBar' : 'belowBar',
//         color: marker.type === 'B' ? '#ff4d4f' : '#008000',
//         shape: marker.type === 'B' ? 'arrowDown' : 'arrowUp',
//         text: marker.type,
//         size: 1
//     }));
//
//     tradeMarkerSeries.setMarkers(markerData);
// }
function updateTradeMarkers(markers) {
    if (!tradeMarkerSeries || !markers) return;

    // 1. 获取所有K线数据并构建一个以时间为键的Map，方便快速查找
    const allCandlestickData = latestRenderedKlineData;
    const candlestickMap = new Map();
    allCandlestickData.forEach(data => {
        candlestickMap.set(data.time, data);
    });

    const markerData = markers.map(marker => {
        const alignedTime = alignTradeMarkerTimeToRenderedBar(marker.time);
        const klineData = candlestickMap.get(alignedTime);
        let shape;

        if (klineData) {
            // 判断K线是涨是跌
            const isKlineUp = klineData.close > klineData.open;

            if (isKlineUp) {
                // 在红K上：箭头朝下 (表示在K线顶部买卖)
                shape = 'arrowDown';
            } else {
                // 平盘K线，默认朝上
                shape = 'arrowUp';
            }

        } else {
            // 如果找不到对应的K线数据，使用默认形状
            shape = marker.type === 'B' ? 'arrowDown' : 'arrowUp';
        }

        const cryptoStyle = marker.type === 'L'
            ? { position: 'belowBar', color: '#16a34a', shape: 'arrowUp' }
            : marker.type === 'X'
                ? { position: 'aboveBar', color: '#f59e0b', shape: 'circle' }
                : marker.type === 'S' && isCryptoMode()
                    ? { position: 'aboveBar', color: '#dc2626', shape: 'arrowDown' }
                    : null;
        return {
            time: alignTradeMarkerTimeToRenderedBar(marker.time),
            // marker 上的显式 position/color/shape 优先（实时看盘用：买入恒在下、卖出恒在上，
            // 不随 K 线涨跌翻转，避免同一笔成交的箭头位置忽上忽下）。
            position: marker.position || cryptoStyle?.position || (shape === 'arrowDown' ? 'aboveBar' : 'belowBar'),
            color: marker.color || cryptoStyle?.color || (marker.type === 'B' ? '#ff4d4f' : '#008000'),
            shape: marker.shape || cryptoStyle?.shape || shape,
            text: marker.label || marker.type,
            size: 1
        };
    });

    tradeMarkerSeries.setMarkers(markerData);
}

// 回放控制
function togglePlayback() {
    if (isPlaying) {
        pausePlayback();
    } else {
        startPlayback();
    }
}

async function playbackTick() {
    if (!isPlaying) return;
    const hasNext = await nextBar();
    if (!isPlaying || hasNext === false) return;
    const speed = parseFloat(document.getElementById('playback-speed').value);
    playbackInterval = setTimeout(playbackTick, speed * 1000);
}

function startPlayback() {
    if (isPlaying) return;
    isPlaying = true;
    document.querySelector('.play-icon').classList.add('hidden');
    document.querySelector('.pause-icon').classList.remove('hidden');

    const speed = parseFloat(document.getElementById('playback-speed').value);
    playbackInterval = setTimeout(playbackTick, speed * 1000);
}

function pausePlayback() {
    isPlaying = false;
    document.querySelector('.play-icon').classList.remove('hidden');
    document.querySelector('.pause-icon').classList.add('hidden');

    if (playbackInterval) {
        clearTimeout(playbackInterval);
        playbackInterval = null;
    }
}

function updatePlaybackSpeed() {
    if (isPlaying) {
        pausePlayback();
        startPlayback();
    }
}

function applyCryptoNextDelta(delta) {
    if (!delta) return;
    clearCryptoPeriodSnapshotCacheForPeriod(currentPeriod);
    if (delta.refresh_snapshot) {
        applyActiveSnapshotToChartWindow(delta.refresh_snapshot);
    } else {
        const bars = delta.bars || [];
        bars.forEach((bar) => {
            const chartBar = buildIntradayKlineChartData([bar])[0];
            const volumeBar = buildIntradayVolumeData([bar])[0];
            if (chartBar) {
                candlestickSeries.update(chartBar);
                upsertRenderedBar(chartBar);
                updateCurrentInfo({
                    time: chartBar.time,
                    open: Number(bar.open), high: Number(bar.high),
                    low: Number(bar.low), close: Number(bar.close),
                    volume: Number(bar.volume || 0),
                }, delta.progress || null);
            }
            if (volumeBar) volumeSeries.update(volumeBar);
        });
        if (bars.length && typeof requestAnimationFrame === 'function') {
            requestAnimationFrame(() => loadTechnicalIndicators());
        }
    }
    const replayProgress = delta.progress || delta;
    updateIntradayReplayStatus(replayProgress);
    if (currentTraining) {
        currentTraining.latestProgress = replayProgress;
        currentTraining.current_time = replayProgress.current_time || currentTraining.current_time;
        currentTraining.next_boundary = replayProgress.next_boundary || currentTraining.next_boundary;
    }
    if (delta.trade_markers) syncActiveTradeMarkers(delta.trade_markers);
    renderCryptoAccount(delta);
    renderCryptoTradeHistory(delta.fills || []);
    const liqFill = (delta.fills || []).find((f) => f.action === 'liquidation');
    if (liqFill) {
        setCryptoOrderStatus(`💀 仓位已触发强平（爆仓）！强平价格: ${formatCryptoValue(liqFill.price)} USDT`, 'error');
    }
}

async function nextCryptoBar() {
    if (!currentTraining?.id || cryptoNextInFlight) return false;
    const button = document.getElementById('next-bar-btn');
    const previousLogicalRange = chart?.timeScale().getVisibleLogicalRange();
    cryptoNextInFlight = true;
    if (button) {
        button.disabled = true;
        button.classList.add('loading');
        button.setAttribute('aria-busy', 'true');
    }
    try {
        const response = await fetch(API_BASE + '/training/' + encodeURIComponent(currentTraining.id) + '/next', {
            method: 'POST',
        });
        const payload = await response.json().catch(() => ({}));
        if (response.status === 409 && payload.code === 'advance_in_progress') return false;
        if (!response.ok) throw new Error(payload.error || '获取下一根 K 线失败');
        clearCryptoPeriodSnapshotCacheForPeriod(currentPeriod);
        const hadRefreshSnapshot = !!(payload.delta && payload.delta.refresh_snapshot);
        applyCryptoNextDelta(payload.delta);
        // 推进后智能保持用户当前的视口与右侧空白，避免图表强行跳动到最右端
        const dataLength = latestRenderedKlineData.length;
        const targetRange = computePreservedNextLogicalRange(previousLogicalRange, dataLength);
        if (targetRange) {
            setVisibleRangeAll(targetRange);
        }
        if (payload.finished) {
            pausePlayback();
            if (payload.report) showReport(payload.report);
            return false;
        }
        return true;
    } catch (error) {
        console.error('获取币圈下一根 K 线失败:', error);
        return false;
    } finally {
        cryptoNextInFlight = false;
        if (button) {
            button.disabled = false;
            button.classList.remove('loading');
            button.setAttribute('aria-busy', 'false');
        }
    }
}

async function nextBar() {
    if (isCryptoMode()) return nextCryptoBar();
    try {
        const previousLogicalRange = chart?.timeScale().getVisibleLogicalRange();

        // === intraday_30m 分支: /next 返回结构中 snapshot 位于 response.snapshot ===
        if (isIntradayMode()) {
            const response = await fetch(`${API_BASE}/training/${currentTraining.id}/next`, {
                method: 'POST'
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                console.error('intraday next 失败:', err);
                return false;
            }
            const data = await response.json();
            if (data.finished) {
                // 训练结束: 停止自动播放并展示报告
                pausePlayback();
                if (data.report) {
                    showReport(data.report);
                }
                return false;
            }
            const snapshot = extractIntradaySnapshot(data);
            applyActiveSnapshotToChartWindow(snapshot);
            const targetRange = computePreservedNextLogicalRange(previousLogicalRange, (latestRenderedKlineData || []).length);
            if (targetRange) {
                setVisibleRangeAll(targetRange);
            }
            renderPendingOrders(data.pending_orders);
            await updateAccountInfo();
            return true;
        }

        // === legacy_daily 分支 (原逻辑) ===
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/next`, {
            method: 'POST'
        });

        if (response.ok) {
            const data = await response.json();

            if (data.finished) {
                // 训练结束
                pausePlayback();
                showReport(data.report);
                return false;
            } else {
                // 更新图表数据
                if (data.new_bar) {
                    if (currentPeriod === 'weekly') {
                        await refreshTrainingView({ preserveRange: true });
                    } else {
                        candlestickSeries.update(data.new_bar);
                        upsertRenderedBar(data.new_bar);

                        const targetRange = computePreservedNextLogicalRange(previousLogicalRange, (latestRenderedKlineData || []).length);
                        if (data.requires_full_refresh) {
                            await updateAdjustment(targetRange);
                        } else {
                            if (data.new_volume) {
                                volumeSeries.update(data.new_volume);
                            }

                            updateCurrentInfo(data.new_bar, data.progress);
                            if (currentTraining) {
                                currentTraining.latestProgress = data.progress || null;
                            }

                            if (data.progress && data.progress.current_bar_id !== undefined) {
                                lastKnownBarId = data.progress.current_bar_id;
                            }

                            await updateMovingAverages();
                            await loadTechnicalIndicators();
                            if (targetRange) {
                                setVisibleRangeAll(targetRange);
                            }
                            await updateChipDistribution();
                        }
                    }

                    if (data.progress && data.progress.current_bar_id !== undefined) {
                        lastKnownBarId = data.progress.current_bar_id;
                    }
                }

                if (data.trade_markers) {
                    updateTradeMarkers(data.trade_markers);
                    lastKnownTradeCount = data.trade_markers.length;
                }
                renderPendingOrders(data.pending_orders);
                updateAccountInfo();
                return true;
            }
        } else {
            const error = await response.json();
            console.error('获取下一根K线失败:', error);
            return false;
        }
    } catch (error) {
        console.error('获取下一根K线失败:', error);
        return false;
    }
}

async function updateMovingAverages() {
    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/data?${getViewPeriodQuery()}`);
        const data = await response.json();

        if (data.ma_data) {
            // 只更新最新的数据点
            maPeriods.forEach(p => {
                const mData = data.ma_data[p];
                if (maSeries[p] && mData && mData.length > 0 && isMaLineVisible(p)) {
                    maSeries[p].update(mData[mData.length - 1]);
                }
            });
            showLatestChartInfo();
        }
    } catch (error) {
        console.error('更新移动平均线失败:', error);
    }
}

// ==================== 指标库系统 ====================
let maVisible = true;
let indicatorPanelVisible = true;
let lastIndicatorData = null;

// ==================== 指标设置（AiCoin 风格弹窗） ====================
const INDICATOR_SETTINGS_KEY = 'indicatorSettingsV2';
const MA_DEFAULT_COLORS = ['#7038db', '#2196f3', '#52c41a', '#26c6da', '#b85717', '#ff9800', '#e91e63', '#607d8b'];
const DEFAULT_INDICATOR_SETTINGS = {
    ma: {
        lines: [
            { period: 10, visible: false, color: '#7038db' },
            { period: 20, visible: true, color: '#2196f3' },
            { period: 40, visible: true, color: '#52c41a' },
            { period: 80, visible: true, color: '#26c6da' },
            { period: 160, visible: true, color: '#b85717' },
        ],
    },
    macd: { fast: 10, slow: 20, signal: 5, difColor: null, deaColor: null },
    macd2: { fast: 80, slow: 160, signal: 40, difColor: '#2196f3', deaColor: '#ff9800' },
    kdj: { n: 9, m1: 3, m2: 3, kColor: '#ff6b6b', dColor: '#4ecdc4', jColor: '#45b7d1' },
    rsi: { periods: [6, 12, 24], colors: ['#ff6b6b', '#4ecdc4', '#45b7d1'] },
    boll: { period: 20, stdDev: 2, upperColor: '#ff6b6b', middleColor: '#4ecdc4', lowerColor: '#45b7d1' },
};

function cloneIndicatorSettings(source) {
    return JSON.parse(JSON.stringify(source));
}

function loadIndicatorSettings() {
    const merged = cloneIndicatorSettings(DEFAULT_INDICATOR_SETTINGS);
    try {
        const raw = localStorage.getItem(INDICATOR_SETTINGS_KEY);
        if (!raw) {
            const legacyRaw = localStorage.getItem('indicatorSettingsV1');
            if (legacyRaw) {
                const savedLegacy = JSON.parse(legacyRaw);
                ['macd', 'macd2', 'kdj', 'boll'].forEach((id) => {
                    if (savedLegacy && savedLegacy[id] && typeof savedLegacy[id] === 'object') {
                        merged[id] = { ...merged[id], ...savedLegacy[id] };
                    }
                });
                if (savedLegacy && savedLegacy.rsi && typeof savedLegacy.rsi === 'object') {
                    if (Array.isArray(savedLegacy.rsi.periods) && savedLegacy.rsi.periods.length) merged.rsi.periods = savedLegacy.rsi.periods.slice(0, 6);
                    if (Array.isArray(savedLegacy.rsi.colors) && savedLegacy.rsi.colors.length) merged.rsi.colors = savedLegacy.rsi.colors.slice(0, 6);
                }
            }
            return merged;
        }
        const saved = JSON.parse(raw);
        ['macd', 'macd2', 'kdj', 'boll'].forEach((id) => {
            if (saved && saved[id] && typeof saved[id] === 'object') {
                merged[id] = { ...merged[id], ...saved[id] };
            }
        });
        if (saved && saved.rsi && typeof saved.rsi === 'object') {
            if (Array.isArray(saved.rsi.periods) && saved.rsi.periods.length) merged.rsi.periods = saved.rsi.periods.slice(0, 6);
            if (Array.isArray(saved.rsi.colors) && saved.rsi.colors.length) merged.rsi.colors = saved.rsi.colors.slice(0, 6);
        }
        if (saved && saved.ma && Array.isArray(saved.ma.lines) && saved.ma.lines.length) {
            merged.ma.lines = saved.ma.lines.slice(0, 8).map((line, index) => ({
                period: Math.min(999, Math.max(1, parseInt(line.period, 10) || DEFAULT_INDICATOR_SETTINGS.ma.lines[0].period)),
                visible: line.visible !== false,
                color: typeof line.color === 'string' ? line.color : MA_DEFAULT_COLORS[index % MA_DEFAULT_COLORS.length],
            }));
        }
    } catch (error) {
        // 配置损坏时回退默认值
    }
    return merged;
}

let indicatorSettings = loadIndicatorSettings();
let currentSettingsIndicatorId = null;

function saveIndicatorSettings() {
    try {
        localStorage.setItem(INDICATOR_SETTINGS_KEY, JSON.stringify(indicatorSettings));
    } catch (error) {
        // 忽略持久化失败
    }
}

function syncMaPeriodsFromSettings() {
    const periods = indicatorSettings.ma.lines
        .map((line) => Number(line.period))
        .filter((period) => Number.isFinite(period) && period > 0);
    if (periods.length) maPeriods = periods;
}

// 当 maPeriods 被外部（用户设置/旧版编辑器）修改后，按当前周期对齐行配置。
function syncMaLineSettingsWithPeriods() {
    const nextLines = [];
    maPeriods.forEach((period, index) => {
        const existing = indicatorSettings.ma.lines.find((line) => Number(line.period) === Number(period));
        nextLines.push(existing
            ? { ...existing }
            : { period: Number(period), visible: true, color: MA_DEFAULT_COLORS[index % MA_DEFAULT_COLORS.length] });
    });
    if (nextLines.length) indicatorSettings.ma.lines = nextLines;
}

function getMaLineConfig(period) {
    return indicatorSettings.ma.lines.find((line) => Number(line.period) === Number(period)) || null;
}

function isMaLineVisible(period) {
    const line = getMaLineConfig(period);
    return maVisible && (!line || line.visible !== false);
}

function getMaLineColor(period, index) {
    const line = getMaLineConfig(period);
    return line?.color || MA_DEFAULT_COLORS[index % MA_DEFAULT_COLORS.length];
}

// 把弹窗保存的参数同步到既有隐藏设置框，供 getTechnicalIndicatorConfig 等旧链路读取。
function syncIndicatorHiddenInputsFromSettings() {
    const setValue = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.value = value;
    };
    setValue('macd-fast', indicatorSettings.macd.fast);
    setValue('macd-slow', indicatorSettings.macd.slow);
    setValue('macd-signal', indicatorSettings.macd.signal);
    setValue('macd2-fast', indicatorSettings.macd2.fast);
    setValue('macd2-slow', indicatorSettings.macd2.slow);
    setValue('macd2-signal', indicatorSettings.macd2.signal);
    setValue('kdj-n', indicatorSettings.kdj.n);
    setValue('kdj-m1', indicatorSettings.kdj.m1);
    setValue('kdj-m2', indicatorSettings.kdj.m2);
    setValue('rsi-periods', indicatorSettings.rsi.periods.join(','));
    setValue('boll-period', indicatorSettings.boll.period);
    setValue('boll-std-dev', indicatorSettings.boll.stdDev);
}

// AiCoin 风格 MACD 自动色：DIF 用主题文字色（暗色下为白），DEA 用金色。
function getAutoMacdColors() {
    const palette = getThemePalette();
    const isDark = (isCryptoMode() || isAshareLiveMode ? (currentCryptoTheme || 'dark') : currentTheme) === 'dark';
    return {
        difColor: palette.text,
        deaColor: isDark ? '#f0b90b' : '#b98700',
    };
}

function resolveIndicatorColor(indId, field, stored) {
    if (typeof stored === 'string' && stored) return stored;
    if (indId === 'macd') return getAutoMacdColors()[field] || '#ffffff';
    if (indId === 'macd2') {
        if (field === 'difColor') return '#2196f3';
        if (field === 'deaColor') return '#ff9800';
    }
    return '#848e9c';
}

function macdColorsAreAuto() {
    return !indicatorSettings.macd.difColor || !indicatorSettings.macd.deaColor;
}

syncMaPeriodsFromSettings();

// ==================== AiCoin 风格指标设置弹窗 ====================
const INDICATOR_SETTINGS_FIELDS = {
    macd: {
        numbers: [['fast', 'Fast', 10], ['slow', 'Slow', 20], ['signal', 'Signal', 5]],
        colors: [['difColor', 'DIF 线颜色'], ['deaColor', 'DEA 线颜色']],
    },
    macd2: {
        numbers: [['fast', 'Fast (共振快线)', 80], ['slow', 'Slow (共振慢线)', 160], ['signal', 'Signal (信号线)', 40]],
        colors: [['difColor', 'DIF 线颜色'], ['deaColor', 'DEA 线颜色']],
    },
    kdj: {
        numbers: [['n', 'N', 9], ['m1', 'M1', 3], ['m2', 'M2', 3]],
        colors: [['kColor', 'K 线颜色'], ['dColor', 'D 线颜色'], ['jColor', 'J 线颜色']],
    },
    boll: {
        numbers: [['period', '周期', 20], ['stdDev', '标准差倍数', 2]],
        colors: [['upperColor', '上轨颜色'], ['middleColor', '中轨颜色'], ['lowerColor', '下轨颜色']],
    },
};
const MA_PERIOD_SUGGESTIONS = [5, 10, 20, 30, 40, 60, 80, 120, 160, 200, 320];

function openIndicatorSettings(indId) {
    const indicator = INDICATOR_REGISTRY.find((item) => item.id === indId);
    if (!indicator) return;
    currentSettingsIndicatorId = indId;
    renderIndicatorSettingsModal();
    document.getElementById('ind-settings-overlay')?.classList.remove('hidden');
}

function closeIndicatorSettings() {
    currentSettingsIndicatorId = null;
    document.getElementById('ind-settings-overlay')?.classList.add('hidden');
}

function renderIndicatorSettingsModal() {
    const indicator = INDICATOR_REGISTRY.find((item) => item.id === currentSettingsIndicatorId);
    const titleEl = document.getElementById('ind-settings-title');
    const descEl = document.getElementById('ind-settings-desc');
    const bodyEl = document.getElementById('ind-settings-body');
    const hideBtn = document.getElementById('ind-settings-hide');
    if (!indicator || !titleEl || !bodyEl) return;
    titleEl.textContent = indicator.name;
    if (descEl) descEl.textContent = indicator.desc || '';
    if (currentSettingsIndicatorId === 'ma') buildMaSettingsBody(bodyEl);
    else if (currentSettingsIndicatorId === 'rsi') buildRsiSettingsBody(bodyEl);
    else if (INDICATOR_SETTINGS_FIELDS[currentSettingsIndicatorId]) buildSimpleSettingsBody(bodyEl, currentSettingsIndicatorId);
    if (hideBtn) hideBtn.textContent = isIndicatorActive(indicator) ? '取消显示' : '恢复显示';
}

function createSettingsNumberField(labelText, value, field, options = {}) {
    const row = document.createElement('div');
    row.className = 'ind-set-row';
    const label = document.createElement('label');
    label.className = 'ind-set-field';
    label.appendChild(document.createTextNode(labelText + ' '));
    const input = document.createElement('input');
    input.type = 'number';
    input.className = 'ind-set-input';
    input.min = String(options.min !== undefined ? options.min : 1);
    input.max = String(options.max !== undefined ? options.max : 999);
    if (options.step !== undefined) input.step = String(options.step);
    input.dataset.field = field;
    input.value = String(value);
    label.appendChild(input);
    row.appendChild(label);
    return row;
}

function createSettingsColorField(labelText, value, field) {
    const row = document.createElement('div');
    row.className = 'ind-set-row';
    const label = document.createElement('label');
    label.className = 'ind-set-field';
    label.appendChild(document.createTextNode(labelText + ' '));
    const input = document.createElement('input');
    input.type = 'color';
    input.className = 'ind-set-color';
    input.dataset.field = field;
    input.value = value;
    label.appendChild(input);
    row.appendChild(label);
    return row;
}

function appendMaSettingsRow(list, line, index) {
    const row = document.createElement('div');
    row.className = 'ind-set-row ind-set-ma-row';

    const check = document.createElement('label');
    check.className = 'ind-set-check';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.dataset.field = 'visible';
    checkbox.checked = line.visible !== false;
    const name = document.createElement('span');
    name.className = 'ind-set-name';
    name.textContent = 'MA' + (index + 1);
    check.appendChild(checkbox);
    check.appendChild(name);

    const periodLabel = document.createElement('label');
    periodLabel.className = 'ind-set-field';
    periodLabel.appendChild(document.createTextNode('周期数 '));
    const periodInput = document.createElement('input');
    periodInput.type = 'number';
    periodInput.className = 'ind-set-input';
    periodInput.min = '1';
    periodInput.max = '999';
    periodInput.dataset.field = 'period';
    periodInput.value = String(line.period);
    periodLabel.appendChild(periodInput);

    const colorLabel = document.createElement('label');
    colorLabel.className = 'ind-set-field';
    colorLabel.appendChild(document.createTextNode('颜色 '));
    const colorInput = document.createElement('input');
    colorInput.type = 'color';
    colorInput.className = 'ind-set-color';
    colorInput.dataset.field = 'color';
    colorInput.value = line.color;
    colorLabel.appendChild(colorInput);

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'ind-set-remove';
    removeBtn.setAttribute('aria-label', '删除 MA' + (index + 1));
    removeBtn.textContent = '×';
    removeBtn.addEventListener('click', () => {
        if (list.querySelectorAll('.ind-set-ma-row').length <= 1) return;
        row.remove();
        renumberSettingsRows(list, 'MA');
    });

    row.appendChild(check);
    row.appendChild(periodLabel);
    row.appendChild(colorLabel);
    row.appendChild(removeBtn);
    list.appendChild(row);
    return row;
}

function renumberSettingsRows(list, prefix) {
    list.querySelectorAll('.ind-set-name').forEach((el, index) => {
        el.textContent = prefix + (index + 1);
    });
}

function readFormPeriods(list) {
    const periods = [];
    list.querySelectorAll('[data-field="period"]').forEach((input) => {
        const value = parseInt(input.value, 10);
        if (Number.isFinite(value) && value > 0) periods.push(value);
    });
    return periods;
}

function suggestNextMaPeriod(list) {
    const periods = readFormPeriods(list);
    const maxPeriod = periods.length ? Math.max(...periods) : 0;
    const next = MA_PERIOD_SUGGESTIONS.find((candidate) => candidate > maxPeriod && !periods.includes(candidate));
    return next || maxPeriod + 10;
}

function buildMaSettingsBody(container) {
    container.innerHTML = '';
    const list = document.createElement('div');
    list.className = 'ind-set-line-list';
    indicatorSettings.ma.lines.forEach((line, index) => appendMaSettingsRow(list, line, index));
    container.appendChild(list);

    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'ind-set-add';
    addBtn.textContent = '+ 添加均线';
    addBtn.addEventListener('click', () => {
        const rowCount = list.querySelectorAll('.ind-set-ma-row').length;
        if (rowCount >= 8) return;
        appendMaSettingsRow(list, {
            period: suggestNextMaPeriod(list),
            visible: true,
            color: MA_DEFAULT_COLORS[rowCount % MA_DEFAULT_COLORS.length],
        }, rowCount);
        if (rowCount + 1 >= 8) addBtn.remove();
    });
    container.appendChild(addBtn);
}

function appendRsiSettingsRow(list, period, color, index) {
    const row = document.createElement('div');
    row.className = 'ind-set-row ind-set-ma-row';

    const name = document.createElement('span');
    name.className = 'ind-set-check ind-set-name';
    name.textContent = 'RSI' + (index + 1);

    const periodLabel = document.createElement('label');
    periodLabel.className = 'ind-set-field';
    periodLabel.appendChild(document.createTextNode('周期数 '));
    const periodInput = document.createElement('input');
    periodInput.type = 'number';
    periodInput.className = 'ind-set-input';
    periodInput.min = '1';
    periodInput.max = '999';
    periodInput.dataset.field = 'period';
    periodInput.value = String(period);
    periodLabel.appendChild(periodInput);

    const colorLabel = document.createElement('label');
    colorLabel.className = 'ind-set-field';
    colorLabel.appendChild(document.createTextNode('颜色 '));
    const colorInput = document.createElement('input');
    colorInput.type = 'color';
    colorInput.className = 'ind-set-color';
    colorInput.dataset.field = 'color';
    colorInput.value = color;
    colorLabel.appendChild(colorInput);

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'ind-set-remove';
    removeBtn.setAttribute('aria-label', '删除 RSI' + (index + 1));
    removeBtn.textContent = '×';
    removeBtn.addEventListener('click', () => {
        if (list.querySelectorAll('.ind-set-ma-row').length <= 1) return;
        row.remove();
        renumberSettingsRows(list, 'RSI');
    });

    row.appendChild(name);
    row.appendChild(periodLabel);
    row.appendChild(colorLabel);
    row.appendChild(removeBtn);
    list.appendChild(row);
    return row;
}

function buildRsiSettingsBody(container) {
    container.innerHTML = '';
    const list = document.createElement('div');
    list.className = 'ind-set-line-list';
    const { periods, colors } = indicatorSettings.rsi;
    periods.forEach((period, index) => {
        appendRsiSettingsRow(list, period, colors[index] || MA_DEFAULT_COLORS[index % MA_DEFAULT_COLORS.length], index);
    });
    container.appendChild(list);

    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'ind-set-add';
    addBtn.textContent = '+ 添加 RSI 周期';
    addBtn.addEventListener('click', () => {
        const rowCount = list.querySelectorAll('.ind-set-ma-row').length;
        if (rowCount >= 6) return;
        const existing = readFormPeriods(list);
        const candidate = [6, 12, 14, 24, 36, 48].find((value) => !existing.includes(value)) || (Math.max(...existing, 0) + 6);
        appendRsiSettingsRow(list, candidate, MA_DEFAULT_COLORS[rowCount % MA_DEFAULT_COLORS.length], rowCount);
        if (rowCount + 1 >= 6) addBtn.remove();
    });
    container.appendChild(addBtn);
}

function buildSimpleSettingsBody(container, indId) {
    container.innerHTML = '';
    const spec = INDICATOR_SETTINGS_FIELDS[indId];
    const values = indicatorSettings[indId];
    if (!spec) return;
    spec.numbers.forEach(([field, labelText, fallback]) => {
        const options = field === 'stdDev' ? { step: 0.1, max: 10 } : {};
        container.appendChild(createSettingsNumberField(labelText, values[field] !== undefined ? values[field] : fallback, field, options));
    });
    spec.colors.forEach(([field, labelText]) => {
        container.appendChild(createSettingsColorField(labelText, resolveIndicatorColor(indId, field, values[field]), field));
    });
}

function collectMaSettingsFromForm() {
    const rows = document.querySelectorAll('#ind-settings-body .ind-set-ma-row');
    const lines = [];
    const seen = new Set();
    rows.forEach((row, index) => {
        const period = parseInt(row.querySelector('[data-field="period"]')?.value, 10);
        if (!Number.isFinite(period) || period <= 0 || seen.has(period)) return;
        seen.add(period);
        lines.push({
            period,
            visible: row.querySelector('[data-field="visible"]')?.checked !== false,
            color: row.querySelector('[data-field="color"]')?.value || MA_DEFAULT_COLORS[index % MA_DEFAULT_COLORS.length],
        });
    });
    return lines.length ? lines : cloneIndicatorSettings(indicatorSettings.ma.lines);
}

function collectRsiSettingsFromForm() {
    const rows = document.querySelectorAll('#ind-settings-body .ind-set-ma-row');
    const periods = [];
    const colors = [];
    const seen = new Set();
    rows.forEach((row, index) => {
        const period = parseInt(row.querySelector('[data-field="period"]')?.value, 10);
        if (!Number.isFinite(period) || period <= 0 || seen.has(period)) return;
        seen.add(period);
        periods.push(period);
        colors.push(row.querySelector('[data-field="color"]')?.value || MA_DEFAULT_COLORS[index % MA_DEFAULT_COLORS.length]);
    });
    return periods.length
        ? { periods, colors }
        : cloneIndicatorSettings({ periods: indicatorSettings.rsi.periods, colors: indicatorSettings.rsi.colors });
}

function collectSimpleSettingsFromForm(indId) {
    const spec = INDICATOR_SETTINGS_FIELDS[indId];
    const next = { ...indicatorSettings[indId] };
    if (!spec) return next;
    spec.numbers.forEach(([field, , fallback]) => {
        const input = document.querySelector('#ind-settings-body [data-field="' + field + '"]');
        const parsed = parseFloat(input?.value);
        next[field] = Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
    });
    spec.colors.forEach(([field]) => {
        const input = document.querySelector('#ind-settings-body [data-field="' + field + '"]');
        if (!input?.value) return;
        const autoColor = indId === 'macd' ? getAutoMacdColors()[field] : null;
        next[field] = autoColor && input.value.toLowerCase() === autoColor.toLowerCase() ? null : input.value;
    });
    return next;
}

function applyIndicatorSettingsEffects(indId) {
    if (indId === 'ma') {
        syncMaPeriodsFromSettings();
        rebuildMaSeries();
    } else {
        syncIndicatorHiddenInputsFromSettings();
        if (isSubchartPanelVisible() && activeSubcharts.includes(indId)) {
            loadTechnicalIndicators();
        } else if (currentIndicatorType === indId.toUpperCase() && indicatorPanelVisible) {
            loadTechnicalIndicator(indId.toUpperCase());
        }
    }
    renderIndicatorLibrary();
    renderActiveIndicatorTags();
    updateIndicatorHeaderLabel();
    showLatestChartInfo();
}

function applyIndicatorSettingsFromForm() {
    const indId = currentSettingsIndicatorId;
    if (!indId) return;
    if (indId === 'ma') indicatorSettings.ma.lines = collectMaSettingsFromForm();
    else if (indId === 'rsi') indicatorSettings.rsi = collectRsiSettingsFromForm();
    else if (INDICATOR_SETTINGS_FIELDS[indId]) indicatorSettings[indId] = collectSimpleSettingsFromForm(indId);
    saveIndicatorSettings();
    applyIndicatorSettingsEffects(indId);
    closeIndicatorSettings();
}

function resetCurrentIndicatorSettings() {
    const indId = currentSettingsIndicatorId;
    if (!indId || !DEFAULT_INDICATOR_SETTINGS[indId]) return;
    indicatorSettings[indId] = cloneIndicatorSettings(DEFAULT_INDICATOR_SETTINGS[indId]);
    saveIndicatorSettings();
    syncIndicatorHiddenInputsFromSettings();
    applyIndicatorSettingsEffects(indId);
    renderIndicatorSettingsModal();
}

function toggleSettingsIndicatorDisplay() {
    const indId = currentSettingsIndicatorId;
    if (!indId) return;
    toggleIndicatorVisibility(indId);
    const indicator = INDICATOR_REGISTRY.find((item) => item.id === indId);
    const hideBtn = document.getElementById('ind-settings-hide');
    if (hideBtn && indicator) hideBtn.textContent = isIndicatorActive(indicator) ? '取消显示' : '恢复显示';
}

const INDICATOR_REGISTRY = [
    {
        id: 'ma', name: 'MA', desc: '移动平均线',
        group: 'overlay',
        params: [{ key: 'periods', label: '周期', type: 'text', default: '10,20,40,80,160' }],
        badge: null,
    },
    {
        id: 'macd', name: 'MACD', desc: '指数平滑异同移动平均线',
        group: 'sub',
        params: [
            { key: 'fast', label: 'Fast', type: 'number', default: 10 },
            { key: 'slow', label: 'Slow', type: 'number', default: 20 },
            { key: 'signal', label: 'Signal', type: 'number', default: 5 },
        ],
        badge: null,
    },
    {
        id: 'macd2', name: 'MACD2', desc: '大周期共振MACD',
        group: 'sub',
        params: [
            { key: 'fast', label: 'Fast', type: 'number', default: 80 },
            { key: 'slow', label: 'Slow', type: 'number', default: 160 },
            { key: 'signal', label: 'Signal', type: 'number', default: 40 },
        ],
        badge: '共振',
    },
    {
        id: 'kdj', name: 'KDJ', desc: '随机指标',
        group: 'sub',
        params: [
            { key: 'n', label: 'N', type: 'number', default: 9 },
            { key: 'm1', label: 'M1', type: 'number', default: 3 },
            { key: 'm2', label: 'M2', type: 'number', default: 3 },
        ],
        badge: null,
    },
    {
        id: 'rsi', name: 'RSI', desc: '相对强弱指标',
        group: 'sub',
        params: [{ key: 'periods', label: '周期', type: 'text', default: '6,12,24' }],
        badge: null,
    },
    {
        id: 'boll', name: 'BOLL', desc: '布林带指标',
        group: 'overlay',
        params: [
            { key: 'period', label: '周期', type: 'number', default: 20 },
            { key: 'stdDev', label: '标准差', type: 'number', default: 2 },
        ],
        badge: null,
    },
];

function toggleIndicatorLibrary() {
    const panel = document.getElementById('indicator-library-panel');
    if (!panel) return;
    if (panel.classList.contains('hidden')) {
        renderIndicatorLibrary();
        panel.classList.remove('hidden');
    } else {
        panel.classList.add('hidden');
    }
}

function hideIndicatorLibrary() {
    document.getElementById('indicator-library-panel')?.classList.add('hidden');
}

function renderIndicatorLibrary() {
    const list = document.getElementById('ind-lib-list');
    if (!list) return;
    const favorites = JSON.parse(localStorage.getItem('indicatorFavorites') || '[]');
    let html = '';
    INDICATOR_REGISTRY.forEach((ind) => {
        const isActive = isIndicatorActive(ind);
        const isFav = favorites.includes(ind.id);
        const paramSummary = getIndicatorParamSummary(ind);
        const badgeHtml = ind.badge ? ' <span class="ind-badge" style="background:rgba(33,150,243,0.2);color:#2196f3;font-size:10px;padding:1px 5px;border-radius:3px;margin-left:4px;font-weight:600;vertical-align:middle;">' + ind.badge + '</span>' : '';
        html += '<div class="ind-lib-item' + (isActive ? ' active' : '') + '" data-ind-id="' + ind.id + '">'
            + '<span class="ind-star' + (isFav ? ' favorited' : '') + '" data-star="' + ind.id + '">' + (isFav ? '\u2605' : '\u2606') + '</span>'
            + '<div class="ind-info"><div class="ind-name">' + ind.name + (paramSummary ? '(' + paramSummary + ')' : '') + badgeHtml + '</div>'
            + '<div class="ind-desc">' + ind.desc + '</div></div>'
            + '<button class="ind-gear" data-gear="' + ind.id + '" type="button" title="设置" aria-label="设置' + ind.name + '">\u2699</button>'
            + '</div>';
    });
    list.innerHTML = html;
    list.querySelectorAll('.ind-lib-item').forEach((item) => {
        item.addEventListener('click', (e) => {
            if (e.target.closest('.ind-star') || e.target.closest('.ind-gear')) return;
            toggleIndicatorVisibility(item.dataset.indId);
        });
    });
    list.querySelectorAll('.ind-star').forEach((star) => {
        star.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleIndicatorFavorite(star.dataset.star);
        });
    });
    list.querySelectorAll('.ind-gear').forEach((gear) => {
        gear.addEventListener('click', (e) => {
            e.stopPropagation();
            openIndicatorSettings(gear.dataset.gear);
        });
    });
}

function isIndicatorActive(ind) {
    if (ind.id === 'ma') return maVisible && maPeriods.length > 0;
    if (ind.id === 'boll') return Boolean(bollVisible);
    if (['macd', 'macd2', 'kdj', 'rsi'].includes(ind.id)) {
        return isSubchartPanelVisible() && Array.isArray(activeSubcharts) && activeSubcharts.includes(ind.id);
    }
    return false;
}

function getIndicatorParamSummary(ind) {
    if (ind.id === 'ma') return maPeriods.join(',');
    if (ind.id === 'macd') {
        const f = document.getElementById('macd-fast')?.value || indicatorSettings.macd?.fast || 10;
        const s = document.getElementById('macd-slow')?.value || indicatorSettings.macd?.slow || 20;
        const sig = document.getElementById('macd-signal')?.value || indicatorSettings.macd?.signal || 5;
        return f + ',' + s + ',' + sig;
    }
    if (ind.id === 'macd2') {
        const f = document.getElementById('macd2-fast')?.value || indicatorSettings.macd2?.fast || 80;
        const s = document.getElementById('macd2-slow')?.value || indicatorSettings.macd2?.slow || 160;
        const sig = document.getElementById('macd2-signal')?.value || indicatorSettings.macd2?.signal || 40;
        return f + ',' + s + ',' + sig;
    }
    if (ind.id === 'kdj') {
        const n = document.getElementById('kdj-n')?.value || indicatorSettings.kdj?.n || 9;
        const m1 = document.getElementById('kdj-m1')?.value || indicatorSettings.kdj?.m1 || 3;
        const m2 = document.getElementById('kdj-m2')?.value || indicatorSettings.kdj?.m2 || 3;
        return n + ',' + m1 + ',' + m2;
    }
    if (ind.id === 'rsi') {
        return String(document.getElementById('rsi-periods')?.value || (indicatorSettings.rsi?.periods || [6, 12, 24]).join(','));
    }
    if (ind.id === 'boll') {
        const p = document.getElementById('boll-period')?.value || indicatorSettings.boll?.period || 20;
        const sd = document.getElementById('boll-std-dev')?.value || indicatorSettings.boll?.stdDev || 2;
        return p + ',' + sd;
    }
    return '';
}

function getIndicatorSettingsElement(indId, key) {
    if (indId === 'macd') return document.getElementById('macd-' + key);
    if (indId === 'macd2') return document.getElementById('macd2-' + key);
    if (indId === 'kdj') return document.getElementById('kdj-' + key);
    if (indId === 'rsi' && key === 'periods') return document.getElementById('rsi-periods');
    if (indId === 'boll') return document.getElementById('boll-' + (key === 'stdDev' ? 'std-dev' : key));
    return null;
}

function buildParamInputs(ind) {
    let html = '';
    ind.params.forEach((param) => {
        let currentVal = param.default;
        if (ind.id === 'ma' && param.key === 'periods') currentVal = maPeriods.join(',');
        else if (['macd', 'kdj', 'rsi', 'boll'].includes(ind.id)) {
            currentVal = getIndicatorSettingsElement(ind.id, param.key)?.value || param.default;
        }
        html += '<div class="ind-param-row"><label>' + param.label + '</label>'
            + '<input type="' + param.type + '" data-ind="' + ind.id + '" data-key="' + param.key + '" value="' + currentVal + '" min="1"></div>';
    });
    return html;
}

function syncLibraryParamsToSettings() {
    document.querySelectorAll('.ind-lib-params input').forEach((input) => {
        const indId = input.dataset.ind;
        const key = input.dataset.key;
        if (indId === 'ma' && key === 'periods') {
            const periods = input.value.split(',').map(s => parseInt(s.trim(), 10)).filter(n => n > 0);
            if (periods.length) maPeriods = periods;
        } else if (['macd', 'kdj', 'rsi', 'boll'].includes(indId)) {
            const el = getIndicatorSettingsElement(indId, key);
            if (el) el.value = input.value;
        }
    });
}

function toggleIndicatorVisibility(id) {
    if (id === 'ma') {
        maVisible = !maVisible;
        if (maVisible) { updateMaLinesFromRendered(); }
        else { maPeriods.forEach((p) => { if (maSeries[p]) maSeries[p].setData([]); }); }
    } else if (id === 'boll') {
        toggleBollIndicator();
    } else if (['macd', 'macd2', 'kdj', 'rsi'].includes(id)) {
        const index = activeSubcharts.indexOf(id);
        if (index >= 0) {
            // 已存在：取消勾选移除
            activeSubcharts.splice(index, 1);
            if (activeSubcharts.length === 0) {
                indicatorPanelVisible = false;
            }
            if (currentIndicatorType.toLowerCase() === id.toLowerCase()) {
                currentIndicatorType = activeSubcharts.length > 0 ? activeSubcharts[0].toUpperCase() : 'MACD';
            }
        } else {
            // 未激活：添加副图（支持多副图堆叠）
            activeSubcharts.push(id);
            indicatorPanelVisible = true;
            currentIndicatorType = id.toUpperCase();
        }
        saveActiveSubcharts();
        renderSubchartsDOM();
        applyChartPanelRatios();
        if (isSubchartPanelVisible()) {
            initSubcharts();
            loadTechnicalIndicators();
        } else {
            clearSubchartInstances();
        }
    }
    renderIndicatorLibrary();
    renderActiveIndicatorTags();
    updateIndicatorHeaderLabel();
}

function removeSubchart(subId) {
    const index = activeSubcharts.indexOf(subId);
    if (index >= 0) {
        activeSubcharts.splice(index, 1);
        if (activeSubcharts.length === 0) {
            indicatorPanelVisible = false;
        }
        if (currentIndicatorType.toLowerCase() === subId.toLowerCase()) {
            currentIndicatorType = activeSubcharts.length > 0 ? activeSubcharts[0].toUpperCase() : 'MACD';
        }
        saveActiveSubcharts();
        renderSubchartsDOM();
        applyChartPanelRatios();
        if (isSubchartPanelVisible()) {
            initSubcharts();
            loadTechnicalIndicators();
        } else {
            clearSubchartInstances();
        }
        renderIndicatorLibrary();
        renderActiveIndicatorTags();
        updateIndicatorHeaderLabel();
    }
}

function toggleIndicatorFavorite(id) {
    let favorites = JSON.parse(localStorage.getItem('indicatorFavorites') || '[]');
    if (favorites.includes(id)) favorites = favorites.filter(f => f !== id);
    else favorites.push(id);
    localStorage.setItem('indicatorFavorites', JSON.stringify(favorites));
    renderIndicatorLibrary();
}

// ===== 主图左上角指标标签 =====
function renderActiveIndicatorTags() {
    let container = document.getElementById('active-indicator-tags');
    if (!container) {
        const chartEl = document.getElementById('chart');
        if (!chartEl) return;
        container = document.createElement('div');
        container.id = 'active-indicator-tags';
        chartEl.appendChild(container);
    }
    let html = '';
    if (maPeriods.length > 0) {
        html += '<div class="active-ind-tag' + (maVisible ? '' : ' disabled') + '" data-tag="ma">'
            + '<span class="tag-dot" style="background:#ff9800"></span>MA(' + maPeriods.join(',') + ')</div>';
    }
    if (bollVisible) {
        const bDef = INDICATOR_REGISTRY.find(r => r.id === 'boll');
        const bSummary = bDef ? getIndicatorParamSummary(bDef) : '20,2';
        html += '<div class="active-ind-tag" data-tag="boll">'
            + '<span class="tag-dot" style="background:#ff6b6b"></span>BOLL(' + bSummary + ')</div>';
    }
    if (isSubchartPanelVisible() && Array.isArray(activeSubcharts)) {
        activeSubcharts.forEach((subId) => {
            const subInd = INDICATOR_REGISTRY.find(r => r.id === subId);
            const name = subInd ? subInd.name : subId.toUpperCase();
            const summary = subInd ? getIndicatorParamSummary(subInd) : '';
            const dotColor = subId === 'macd' ? '#4ecdc4' : (subId === 'macd2' ? '#2196f3' : (subId === 'kdj' ? '#ff9800' : '#f9c74f'));
            html += '<div class="active-ind-tag" data-tag="' + subId + '">'
                + '<span class="tag-dot" style="background:' + dotColor + '"></span>' + name
                + (summary ? '(' + summary + ')' : '') + '</div>';
        });
    }
    container.innerHTML = html;
    container.querySelectorAll('.active-ind-tag').forEach((tag) => {
        tag.addEventListener('click', () => toggleIndicatorVisibility(tag.dataset.tag));
    });
}

// 副图图例行左侧的指标名 + 参数标签（AiCoin 风格）
function updateIndicatorHeaderLabel() {
    const nameEl = document.getElementById('indicator-type-name');
    const paramsEl = document.getElementById('indicator-type-params');
    const displayType = activeSubcharts.length > 0 ? activeSubcharts[0].toUpperCase() : currentIndicatorType;
    const subIndicator = INDICATOR_REGISTRY.find((item) => item.name === displayType);
    if (nameEl) nameEl.textContent = displayType;
    if (paramsEl) {
        const summary = subIndicator ? getIndicatorParamSummary(subIndicator) : '';
        paramsEl.textContent = summary ? '(' + summary + ')' : '';
    }
    const indicatorSelect = document.getElementById('indicator-select');
    if (indicatorSelect && indicatorSelect.value !== displayType) {
        indicatorSelect.value = displayType;
    }
}

// ===== 副图图例行彩色数值（AiCoin 风格，支持 MACD/MACD2/KDJ/RSI）=====
function formatIndicatorValue(value) {
    const num = Number(value);
    if (value === undefined || value === null || !Number.isFinite(num)) return '--';
    return num.toFixed(2);
}

function collectSubchartValueItems(subId, point) {
    const items = [];
    if (!point) return items;
    const upperId = subId.toUpperCase();
    if (upperId === 'MACD' || upperId === 'MACD2') {
        const palette = getThemePalette();
        const histogram = Number(point.histogram);
        const difCol = resolveIndicatorColor(subId, 'difColor', indicatorSettings[subId]?.difColor);
        const deaCol = resolveIndicatorColor(subId, 'deaColor', indicatorSettings[subId]?.deaColor);
        items.push({ label: 'DIF', value: formatIndicatorValue(point.dif), color: difCol });
        items.push({ label: 'DEA', value: formatIndicatorValue(point.dea), color: deaCol });
        items.push({
            label: 'MACD',
            value: formatIndicatorValue(point.histogram),
            color: Number.isFinite(histogram) && histogram >= 0 ? palette.positive : palette.negative,
        });
    } else if (upperId === 'KDJ') {
        items.push({ label: 'K', value: formatIndicatorValue(point.k), color: indicatorSettings.kdj?.kColor || '#ff6b6b' });
        items.push({ label: 'D', value: formatIndicatorValue(point.d), color: indicatorSettings.kdj?.dColor || '#4ecdc4' });
        items.push({ label: 'J', value: formatIndicatorValue(point.j), color: indicatorSettings.kdj?.jColor || '#45b7d1' });
    } else if (upperId === 'RSI') {
        const periods = getTechnicalIndicatorConfig('RSI').periods;
        const colors = indicatorSettings.rsi?.colors || ['#ff6b6b', '#4ecdc4', '#45b7d1'];
        periods.forEach((period, index) => {
            items.push({
                label: 'RSI' + period,
                value: formatIndicatorValue(point['rsi' + period]),
                color: colors[index % colors.length] || '#f9c74f',
            });
        });
    }
    return items;
}

function updateSubchartLegendValues(subId, time = null) {
    const valEl = document.getElementById('subchart-values-' + subId);
    if (!valEl) return;
    const calcData = lastSubchartDataMap[subId];
    if (!calcData || !calcData.data || calcData.data.length === 0) {
        valEl.innerHTML = '';
        return;
    }
    let point = null;
    if (time !== null && time !== undefined) {
        point = calcData.data.find((item) => item.time === time);
    }
    if (!point) {
        point = calcData.data[calcData.data.length - 1];
    }
    const items = collectSubchartValueItems(subId, point);
    let html = '';
    items.forEach((item) => {
        html += '<span class="subchart-val-item" style="color:' + item.color + '">' + item.label + ':' + item.value + '</span> ';
    });
    valEl.innerHTML = html;
}

function updateAllSubchartLegendValues(time = null) {
    if (!activeSubcharts) return;
    activeSubcharts.forEach((subId) => {
        updateSubchartLegendValues(subId, time);
    });
}

function syncCrosshairToAllSubcharts(param) {
    if (!subchartInstances) return;
    const time = param && param.time ? param.time : null;
    Object.keys(subchartInstances).forEach((id) => {
        const inst = subchartInstances[id];
        if (!inst || !inst.chart) return;
        if (time && inst.primarySeries) {
            const dataMap = lastSubchartDataMap[id];
            const point = dataMap?.data ? dataMap.data.find(d => d.time === time) : null;
            if (point) {
                const val = point.dif !== undefined ? point.dif : (point.k !== undefined ? point.k : point.value || 0);
                inst.chart.setCrosshairPosition(val, time, inst.primarySeries);
            }
        } else {
            inst.chart.clearCrosshairPosition();
        }
    });
    updateAllSubchartLegendValues(time);
}

function rebuildMaSeries() {
    if (!chart) return;
    Object.keys(maSeries).forEach((key) => {
        try { chart.removeSeries(maSeries[key]); } catch (e) { /* ignore */ }
        delete maSeries[key];
    });
    maPeriods.forEach((p, index) => {
        maSeries[p] = chart.addSeries(LightweightCharts.LineSeries, {
            color: getMaLineColor(p, index),
            lineWidth: 1,
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
        });
    });
    updateMaLinesFromRendered();
    renderChartLegend();
}

function updateMaLinesFromRendered() {
    const data = latestRenderedKlineData;
    maPeriods.forEach((p) => {
        if (!maSeries[p]) return;
        if (!isMaLineVisible(p) || !data || data.length === 0) {
            maSeries[p].setData([]);
            return;
        }
        const maData = [];
        for (let i = p - 1; i < data.length; i++) {
            let sum = 0;
            for (let j = i - p + 1; j <= i; j++) sum += data[j].close;
            maData.push({ time: data[i].time, value: sum / p });
        }
        maSeries[p].setData(maData);
    });
}

function getTechnicalIndicatorConfig(indicatorType) {
    const type = String(indicatorType || '').toUpperCase();
    if (type === 'MACD') {
        return {
            fast: parseInt(document.getElementById('macd-fast')?.value, 10) || indicatorSettings.macd?.fast || 10,
            slow: parseInt(document.getElementById('macd-slow')?.value, 10) || indicatorSettings.macd?.slow || 20,
            signal: parseInt(document.getElementById('macd-signal')?.value, 10) || indicatorSettings.macd?.signal || 5,
        };
    }
    if (type === 'MACD2') {
        return {
            fast: parseInt(document.getElementById('macd2-fast')?.value, 10) || indicatorSettings.macd2?.fast || 80,
            slow: parseInt(document.getElementById('macd2-slow')?.value, 10) || indicatorSettings.macd2?.slow || 160,
            signal: parseInt(document.getElementById('macd2-signal')?.value, 10) || indicatorSettings.macd2?.signal || 40,
        };
    }
    if (type === 'KDJ') {
        return {
            n: parseInt(document.getElementById('kdj-n')?.value, 10) || indicatorSettings.kdj?.n || 9,
            m1: parseInt(document.getElementById('kdj-m1')?.value, 10) || indicatorSettings.kdj?.m1 || 3,
            m2: parseInt(document.getElementById('kdj-m2')?.value, 10) || indicatorSettings.kdj?.m2 || 3,
        };
    }
    if (type === 'RSI') {
        const periods = String(document.getElementById('rsi-periods')?.value || (indicatorSettings.rsi?.periods || [6, 12, 24]).join(','))
            .split(',')
            .map((value) => parseInt(value.trim(), 10))
            .filter((value) => Number.isFinite(value) && value > 0);
        return { periods: periods.length ? periods : [6, 12, 24] };
    }
    return {
        period: parseInt(document.getElementById('boll-period')?.value, 10) || indicatorSettings.boll?.period || 20,
        stdDev: parseFloat(document.getElementById('boll-std-dev')?.value) || indicatorSettings.boll?.stdDev || 2,
    };
}

function clearBollSeries() {
    Object.values(bollSeries).forEach((series) => {
        try { chart?.removeSeries(series); } catch (e) {}
    });
    bollSeries = {};
    renderChartLegend();
    showLatestChartInfo();
}

function updateBollSeries() {
    if (!chart || !window.KLineIndicatorMath || !latestRenderedKlineData || !latestRenderedKlineData.length) return;
    clearBollSeries();
    const config = getTechnicalIndicatorConfig('BOLL');
    const data = window.KLineIndicatorMath.calculate('BOLL', latestRenderedKlineData, config);
    if (!data || !data.data || !data.data.length) return;
    const colors = {
        upper: indicatorSettings.boll.upperColor,
        middle: indicatorSettings.boll.middleColor,
        lower: indicatorSettings.boll.lowerColor,
    };
    ['upper', 'middle', 'lower'].forEach((key) => {
        bollSeries[key] = chart.addSeries(LightweightCharts.LineSeries, {
            color: colors[key],
            lineWidth: 2,
            priceLineVisible: false,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
        });
        bollSeries[key].setData(data.data.map((item) => ({ time: item.time, value: item[key] })));
    });
    renderChartLegend();
    showLatestChartInfo();
}

function toggleBollIndicator() {
    bollVisible = !bollVisible;
    if (bollVisible) {
        updateBollSeries();
    } else {
        clearBollSeries();
    }
}

function clearSubchartInstances() {
    if (subchartInstances && typeof subchartInstances === 'object') {
        Object.keys(subchartInstances).forEach((id) => {
            const inst = subchartInstances[id];
            if (inst && inst.chart) {
                try {
                    inst.chart.remove();
                } catch (e) {}
            }
        });
    }
    subchartInstances = {};
    indicatorChart = null;
    currentIndicatorSeries = [];
}

function clearTechnicalIndicatorSeries() {
    Object.values(bollSeries).forEach((series) => {
        try {
            chart?.removeSeries(series);
        } catch (error) {}
    });
    bollSeries = {};

    currentIndicatorSeries.forEach((series) => {
        try {
            indicatorChart?.removeSeries(series);
        } catch (error) {}
    });
    currentIndicatorSeries = [];

    if (subchartInstances && typeof subchartInstances === 'object') {
        Object.values(subchartInstances).forEach((inst) => {
            if (inst && inst.chart && Array.isArray(inst.seriesList)) {
                inst.seriesList.forEach((series) => {
                    try { inst.chart.removeSeries(series); } catch (error) {}
                });
            }
            if (inst) {
                inst.seriesList = [];
                inst.primarySeries = null;
                inst.difSeries = null;
                inst.deaSeries = null;
                inst.histogramSeries = null;
                inst.kSeries = null;
                inst.dSeries = null;
                inst.jSeries = null;
                inst.rsiSeriesList = null;
                inst.seriesType = null;
            }
        });
    }

    renderChartLegend();
    renderIndicatorLegend();
}

let activeSubchartSplitter = null;
let subchartResizing = false;
let subchartRatios = null;
const SUBCHART_RATIOS_KEY = 'kline-subchart-ratios-v1';

function readSubchartRatios() {
    try {
        const stored = JSON.parse(localStorage.getItem(SUBCHART_RATIOS_KEY) || '{}');
        if (stored && typeof stored === 'object') return stored;
    } catch (e) {}
    return {};
}

function persistSubchartRatios() {
    if (!subchartRatios) return;
    try {
        localStorage.setItem(SUBCHART_RATIOS_KEY, JSON.stringify(subchartRatios));
    } catch (e) {}
}

function applySubchartHeights() {
    const wrapper = document.getElementById('subcharts-wrapper');
    if (!wrapper || !Array.isArray(activeSubcharts) || activeSubcharts.length === 0) return;
    const totalHeight = wrapper.clientHeight;
    if (totalHeight <= 0) return;

    const splitters = wrapper.querySelectorAll('.subchart-splitter');
    const splittersHeight = Array.from(splitters).reduce((sum, s) => sum + (s.offsetHeight || 6), 0);
    const availableHeight = Math.max(0, totalHeight - splittersHeight);
    if (availableHeight <= 0) return;

    if (!subchartRatios || Object.keys(subchartRatios).length === 0) {
        subchartRatios = readSubchartRatios();
    }

    const count = activeSubcharts.length;
    let sumWeight = 0;
    activeSubcharts.forEach((id) => {
        if (!Number.isFinite(subchartRatios[id]) || subchartRatios[id] <= 0) {
            subchartRatios[id] = 1 / count;
        }
        sumWeight += subchartRatios[id];
    });

    const minPaneH = 44;
    const heights = {};
    activeSubcharts.forEach((id) => {
        const h = Math.max(minPaneH, Math.round(availableHeight * (subchartRatios[id] / (sumWeight || 1))));
        heights[id] = h;
    });

    const currentTotal = Object.values(heights).reduce((a, b) => a + b, 0);
    const diff = availableHeight - currentTotal;
    if (diff !== 0 && activeSubcharts.length > 0) {
        const lastId = activeSubcharts[activeSubcharts.length - 1];
        heights[lastId] = Math.max(minPaneH, heights[lastId] + diff);
    }

    activeSubcharts.forEach((id) => {
        const pane = document.getElementById('subchart-pane-' + id);
        if (pane) {
            pane.style.flex = `0 0 ${heights[id]}px`;
            pane.style.height = `${heights[id]}px`;
        }
    });
}

function resizeSubchartPair(splitter, delta) {
    const beforePane = document.getElementById('subchart-pane-' + splitter.dataset.beforeSubchart);
    const afterPane = document.getElementById('subchart-pane-' + splitter.dataset.afterSubchart);
    if (!beforePane || !afterPane) return;
    const beforeStart = Number(splitter.dataset.beforeStart);
    const afterStart = Number(splitter.dataset.afterStart);
    if (!Number.isFinite(beforeStart) || !Number.isFinite(afterStart)) return;

    const pairHeight = beforeStart + afterStart;
    const minH = 44;
    const nextBefore = Math.min(pairHeight - minH, Math.max(minH, beforeStart + delta));
    const nextAfter = pairHeight - nextBefore;

    beforePane.style.flex = `0 0 ${Math.round(nextBefore)}px`;
    beforePane.style.height = `${Math.round(nextBefore)}px`;
    afterPane.style.flex = `0 0 ${Math.round(nextAfter)}px`;
    afterPane.style.height = `${Math.round(nextAfter)}px`;

    if (!subchartRatios) subchartRatios = {};
    activeSubcharts.forEach((id) => {
        const p = document.getElementById('subchart-pane-' + id);
        if (p && p.clientHeight > 0) {
            subchartRatios[id] = p.clientHeight;
        }
    });
    resizeCharts();
}

function setupSubchartSplitters() {
    const wrapper = document.getElementById('subcharts-wrapper');
    if (!wrapper) return;

    const finishSubchartResize = (e) => {
        if (!activeSubchartSplitter) return;
        activeSubchartSplitter.releasePointerCapture?.(e.pointerId);
        activeSubchartSplitter.classList.remove('is-dragging');
        document.body.classList.remove('chart-panel-resizing');
        activeSubchartSplitter = null;
        subchartResizing = false;
        persistSubchartRatios();
        resizeCharts();
    };

    wrapper.querySelectorAll('.subchart-splitter').forEach((splitter) => {
        splitter.addEventListener('pointerdown', (e) => {
            e.preventDefault();
            activeSubchartSplitter = splitter;
            subchartResizing = true;
            const beforePane = document.getElementById('subchart-pane-' + splitter.dataset.beforeSubchart);
            const afterPane = document.getElementById('subchart-pane-' + splitter.dataset.afterSubchart);
            if (!beforePane || !afterPane) return;

            splitter.dataset.dragStartY = String(e.clientY);
            splitter.dataset.beforeStart = String(beforePane.getBoundingClientRect().height);
            splitter.dataset.afterStart = String(afterPane.getBoundingClientRect().height);

            splitter.classList.add('is-dragging');
            document.body.classList.add('chart-panel-resizing');
            splitter.setPointerCapture?.(e.pointerId);
        });

        splitter.addEventListener('keydown', (e) => {
            if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
            e.preventDefault();
            const beforePane = document.getElementById('subchart-pane-' + splitter.dataset.beforeSubchart);
            const afterPane = document.getElementById('subchart-pane-' + splitter.dataset.afterSubchart);
            if (!beforePane || !afterPane) return;
            splitter.dataset.beforeStart = String(beforePane.getBoundingClientRect().height);
            splitter.dataset.afterStart = String(afterPane.getBoundingClientRect().height);
            resizeSubchartPair(splitter, e.key === 'ArrowDown' ? 16 : -16);
            persistSubchartRatios();
        });
    });

    if (!wrapper.dataset.listenersBound) {
        wrapper.dataset.listenersBound = 'true';
        window.addEventListener('pointermove', (e) => {
            if (!subchartResizing || !activeSubchartSplitter) return;
            resizeSubchartPair(
                activeSubchartSplitter,
                e.clientY - Number(activeSubchartSplitter.dataset.dragStartY)
            );
        });
        window.addEventListener('pointerup', finishSubchartResize);
        window.addEventListener('pointercancel', finishSubchartResize);
        window.addEventListener('blur', finishSubchartResize);
    }
}

function renderSubchartsDOM() {
    const wrapper = document.getElementById('subcharts-wrapper');
    if (!wrapper) return;
    if (!activeSubcharts || activeSubcharts.length === 0) {
        wrapper.innerHTML = '';
        clearSubchartInstances();
        return;
    }

    let html = '';
    activeSubcharts.forEach((subId, index) => {
        if (index > 0) {
            html += `
                <div class="subchart-splitter" data-before-subchart="${activeSubcharts[index - 1]}" data-after-subchart="${subId}" role="separator" aria-orientation="horizontal" aria-label="调整副图高度" tabindex="0"></div>
            `;
        }
        const indDef = INDICATOR_REGISTRY.find(r => r.id === subId);
        const name = indDef ? indDef.name : subId.toUpperCase();
        const paramSummary = indDef ? getIndicatorParamSummary(indDef) : '';
        html += `
            <div class="subchart-pane" id="subchart-pane-${subId}" data-subchart-id="${subId}">
                <div class="subchart-header">
                    <div class="subchart-title-box">
                        <span class="subchart-name">${name}</span>
                        <span class="subchart-params">(${paramSummary})</span>
                        <div class="subchart-values" id="subchart-values-${subId}"></div>
                    </div>
                    <div class="subchart-actions">
                        <button type="button" class="subchart-action-btn subchart-btn-gear" data-subchart-action="settings" data-subchart-id="${subId}" title="指标设置">⚙</button>
                        <button type="button" class="subchart-action-btn subchart-btn-close" data-subchart-action="close" data-subchart-id="${subId}" title="关闭副图">&times;</button>
                    </div>
                </div>
                <div class="subchart-canvas" id="subchart-canvas-${subId}"></div>
            </div>
        `;
    });
    wrapper.innerHTML = html;

    wrapper.querySelectorAll('[data-subchart-action="settings"]').forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            openIndicatorSettings(btn.dataset.subchartId);
        });
    });
    wrapper.querySelectorAll('[data-subchart-action="close"]').forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            removeSubchart(btn.dataset.subchartId);
        });
    });
    applySubchartHeights();
    setupSubchartSplitters();
}

function initSubcharts() {
    renderSubchartsDOM();
    if (!activeSubcharts || activeSubcharts.length === 0) {
        clearSubchartInstances();
        return;
    }

    clearSubchartInstances();
    const palette = getThemePalette();

    activeSubcharts.forEach((subId) => {
        const canvasEl = document.getElementById('subchart-canvas-' + subId);
        if (!canvasEl) return;
        const subChart = LightweightCharts.createChart(canvasEl, {
            width: canvasEl.clientWidth || 300,
            height: canvasEl.clientHeight || 80,
            layout: {
                background: { type: 'solid', color: palette.chartBg },
                textColor: palette.text,
            },
            grid: {
                vertLines: { color: palette.grid },
                horzLines: { color: palette.grid },
            },
            rightPriceScale: {
                borderColor: palette.border,
                minimumWidth: 80,
                scaleMargins: {
                    top: 0.12,
                    bottom: 0.12,
                },
            },
            timeScale: {
                borderColor: palette.border,
                visible: false,
            },
        });

        subChart.timeScale().subscribeVisibleLogicalRangeChange((timeRange) => {
            if (timeRange && !isSyncingRange) {
                isSyncingRange = true;
                if (chart) chart.timeScale().setVisibleLogicalRange(timeRange);
                if (volumeChart) volumeChart.timeScale().setVisibleLogicalRange(timeRange);
                syncSubchartsRange(timeRange, subChart);
                isSyncingRange = false;
            }
        });

        subChart.subscribeCrosshairMove((param) => {
            if (!param.time || param.point.x < 0 || param.point.y < 0) {
                if (chart && candlestickSeries) syncCrosshair(chart, candlestickSeries, null);
                if (volumeChart && volumeSeries) syncCrosshair(volumeChart, volumeSeries, null);
                syncCrosshairToAllSubcharts(null);
                return;
            }
            if (chart && candlestickSeries) {
                const candlePoint = latestRenderedKlineData.find(d => d.time === param.time);
                if (candlePoint) {
                    chart.setCrosshairPosition(candlePoint.close, param.time, candlestickSeries);
                }
            }
            if (volumeChart && volumeSeries) {
                const volPoint = latestRenderedVolumeData.find(d => d.time === param.time);
                if (volPoint) {
                    volumeChart.setCrosshairPosition(volPoint.value, param.time, volumeSeries);
                }
            }
            syncCrosshairToAllSubcharts(param);
        });

        subchartInstances[subId] = {
            id: subId,
            chart: subChart,
            primarySeries: null,
            seriesList: [],
        };
    });

    if (activeSubcharts.length > 0 && subchartInstances[activeSubcharts[0]]) {
        indicatorChart = subchartInstances[activeSubcharts[0]].chart;
    }
    applySubchartHeights();
}

function syncSubchartsRange(timeRange, excludeChart = null) {
    if (!timeRange || !subchartInstances) return;
    Object.values(subchartInstances).forEach((inst) => {
        if (inst && inst.chart && inst.chart !== excludeChart) {
            try {
                inst.chart.timeScale().setVisibleLogicalRange(timeRange);
            } catch (e) {}
        }
    });
}

function attachMacdZeroLine(series) {
    try {
        series.createPriceLine({
            price: 0,
            color: isCryptoMode() ? 'rgba(132, 142, 156, 0.45)' : 'rgba(93, 107, 130, 0.4)',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: false,
            title: '',
        });
    } catch (error) {}
}

function hexColorWithAlpha(hex, alpha) {
    if (typeof hex !== 'string' || hex.charAt(0) !== '#') return hex;
    let value = hex.slice(1);
    if (value.length === 3) value = value.split('').map((c) => c + c).join('');
    if (value.length !== 6) return hex;
    const r = parseInt(value.slice(0, 2), 16);
    const g = parseInt(value.slice(2, 4), 16);
    const b = parseInt(value.slice(4, 6), 16);
    if (![r, g, b].every((v) => Number.isFinite(v))) return hex;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

async function loadTechnicalIndicators() {
    if (!window.KLineIndicatorMath || !latestRenderedKlineData || latestRenderedKlineData.length === 0) return;
    if (!isSubchartPanelVisible() || !activeSubcharts || activeSubcharts.length === 0) {
        if (bollVisible) updateBollSeries();
        return;
    }

    const visibleLogicalRange = chart ? chart.timeScale().getVisibleLogicalRange() : null;
    const palette = getThemePalette();

    for (const subId of activeSubcharts) {
        let inst = subchartInstances[subId];
        if (!inst || !inst.chart) {
            initSubcharts();
            inst = subchartInstances[subId];
            if (!inst || !inst.chart) continue;
        }

        const upperType = subId.toUpperCase();
        const config = getTechnicalIndicatorConfig(upperType);
        const data = window.KLineIndicatorMath.calculate(upperType, latestRenderedKlineData, config);
        lastSubchartDataMap[subId] = data;

        if (!data || !data.data || data.data.length === 0) continue;

        if (upperType === 'MACD' || upperType === 'MACD2') {
            const difColor = resolveIndicatorColor(subId, 'difColor', indicatorSettings[subId]?.difColor);
            const deaColor = resolveIndicatorColor(subId, 'deaColor', indicatorSettings[subId]?.deaColor);
            const solidUp = palette.positive;
            const solidDown = palette.negative;
            const hollowUp = hexColorWithAlpha(solidUp, 0.4);
            const hollowDown = hexColorWithAlpha(solidDown, 0.4);

            let difSeries = inst.difSeries;
            let deaSeries = inst.deaSeries;
            let histogramSeries = inst.histogramSeries;

            if (inst.seriesType !== upperType || !difSeries || !deaSeries || !histogramSeries) {
                if (inst.seriesList && inst.seriesList.length > 0) {
                    inst.seriesList.forEach((s) => {
                        try { inst.chart.removeSeries(s); } catch (e) {}
                    });
                }
                histogramSeries = inst.chart.addSeries(LightweightCharts.HistogramSeries, {
                    crosshairMarkerVisible: false,
                    priceLineVisible: false,
                    lastValueVisible: false,
                });
                difSeries = inst.chart.addSeries(LightweightCharts.LineSeries, {
                    color: difColor,
                    lineWidth: 2,
                    crosshairMarkerVisible: false,
                    priceLineVisible: false,
                    lastValueVisible: false,
                });
                deaSeries = inst.chart.addSeries(LightweightCharts.LineSeries, {
                    color: deaColor,
                    lineWidth: 2,
                    crosshairMarkerVisible: false,
                    priceLineVisible: false,
                    lastValueVisible: false,
                });

                attachMacdZeroLine(difSeries);

                inst.seriesType = upperType;
                inst.difSeries = difSeries;
                inst.deaSeries = deaSeries;
                inst.histogramSeries = histogramSeries;
                inst.primarySeries = difSeries;
                inst.seriesList = [difSeries, deaSeries, histogramSeries];
            } else {
                difSeries.applyOptions({ color: difColor });
                deaSeries.applyOptions({ color: deaColor });
            }

            difSeries.setData(data.data.map((item) => ({ time: item.time, value: item.dif })));
            deaSeries.setData(data.data.map((item) => ({ time: item.time, value: item.dea })));
            histogramSeries.setData(data.data.map((item, index) => {
                const value = item.histogram;
                const prevValue = index > 0 ? data.data[index - 1].histogram : 0;
                const strengthening = value >= prevValue;
                let color;
                if (value >= 0) color = strengthening ? solidUp : hollowUp;
                else color = strengthening ? hollowDown : solidDown;
                return { time: item.time, value, color };
            }));
        } else if (upperType === 'KDJ') {
            const kColor = indicatorSettings.kdj.kColor || '#ff6b6b';
            const dColor = indicatorSettings.kdj.dColor || '#4ecdc4';
            const jColor = indicatorSettings.kdj.jColor || '#45b7d1';

            let kSeries = inst.kSeries;
            let dSeries = inst.dSeries;
            let jSeries = inst.jSeries;

            if (inst.seriesType !== 'KDJ' || !kSeries || !dSeries || !jSeries) {
                if (inst.seriesList && inst.seriesList.length > 0) {
                    inst.seriesList.forEach((s) => {
                        try { inst.chart.removeSeries(s); } catch (e) {}
                    });
                }
                kSeries = inst.chart.addSeries(LightweightCharts.LineSeries, {
                    color: kColor,
                    lineWidth: 1.5,
                    crosshairMarkerVisible: false,
                    priceLineVisible: false,
                    lastValueVisible: false,
                });
                dSeries = inst.chart.addSeries(LightweightCharts.LineSeries, {
                    color: dColor,
                    lineWidth: 1.5,
                    crosshairMarkerVisible: false,
                    priceLineVisible: false,
                    lastValueVisible: false,
                });
                jSeries = inst.chart.addSeries(LightweightCharts.LineSeries, {
                    color: jColor,
                    lineWidth: 1.5,
                    crosshairMarkerVisible: false,
                    priceLineVisible: false,
                    lastValueVisible: false,
                });

                inst.seriesType = 'KDJ';
                inst.kSeries = kSeries;
                inst.dSeries = dSeries;
                inst.jSeries = jSeries;
                inst.primarySeries = kSeries;
                inst.seriesList = [kSeries, dSeries, jSeries];
            } else {
                kSeries.applyOptions({ color: kColor });
                dSeries.applyOptions({ color: dColor });
                jSeries.applyOptions({ color: jColor });
            }

            kSeries.setData(data.data.map((item) => ({ time: item.time, value: item.k })));
            dSeries.setData(data.data.map((item) => ({ time: item.time, value: item.d })));
            jSeries.setData(data.data.map((item) => ({ time: item.time, value: item.j })));
        } else if (upperType === 'RSI') {
            const fallbackColors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#f9c74f', '#90be6d', '#f8961e'];
            const colors = (indicatorSettings.rsi.colors && indicatorSettings.rsi.colors.length ? indicatorSettings.rsi.colors : fallbackColors);
            const periods = data.periods || [];
            let rsiSeriesList = inst.rsiSeriesList;

            if (inst.seriesType !== 'RSI' || !rsiSeriesList || rsiSeriesList.length !== periods.length) {
                if (inst.seriesList && inst.seriesList.length > 0) {
                    inst.seriesList.forEach((s) => {
                        try { inst.chart.removeSeries(s); } catch (e) {}
                    });
                }
                rsiSeriesList = [];
                periods.forEach((period, index) => {
                    const s = inst.chart.addSeries(LightweightCharts.LineSeries, {
                        color: colors[index % colors.length],
                        lineWidth: 1.5,
                        crosshairMarkerVisible: false,
                        priceLineVisible: false,
                        lastValueVisible: false,
                    });
                    rsiSeriesList.push(s);
                });
                inst.seriesType = 'RSI';
                inst.rsiSeriesList = rsiSeriesList;
                inst.primarySeries = rsiSeriesList[0] || null;
                inst.seriesList = rsiSeriesList;
            } else {
                rsiSeriesList.forEach((s, index) => {
                    s.applyOptions({ color: colors[index % colors.length] });
                });
            }

            periods.forEach((period, index) => {
                rsiSeriesList[index].setData(data.data.map((item) => ({ time: item.time, value: item[`rsi${period}`] })));
            });
        }

        try {
            inst.chart.priceScale('right')?.applyOptions({ autoScale: true });
        } catch (e) {}

        updateSubchartLegendValues(subId);
        if (visibleLogicalRange !== null) {
            try { inst.chart.timeScale().setVisibleLogicalRange(visibleLogicalRange); } catch (e) {}
        }
    }

    if (activeSubcharts.length > 0 && subchartInstances[activeSubcharts[0]]) {
        indicatorChart = subchartInstances[activeSubcharts[0]].chart;
        currentIndicatorSeries = subchartInstances[activeSubcharts[0]].seriesList || [];
    }

    if (bollVisible) {
        updateBollSeries();
    }
}

async function loadTechnicalIndicator(indicatorType) {
    clearTechnicalIndicatorSeries();
    if (indicatorType) {
        const lower = String(indicatorType).toLowerCase();
        currentIndicatorType = lower.toUpperCase();
        if (['macd', 'macd2', 'kdj', 'rsi'].includes(lower)) {
            if (!activeSubcharts.includes(lower)) {
                activeSubcharts.push(lower);
                saveActiveSubcharts();
                renderSubchartsDOM();
                applyChartPanelRatios();
                initSubcharts();
            }
        }
    }
    await loadTechnicalIndicators();
}

function changeIndicator() {
    const select = document.getElementById('indicator-select');
    if (select) {
        currentIndicatorType = select.value;
        const lower = currentIndicatorType.toLowerCase();
        if (['macd', 'macd2', 'kdj', 'rsi'].includes(lower)) {
            if (!activeSubcharts.includes(lower)) {
                activeSubcharts.push(lower);
                saveActiveSubcharts();
                renderSubchartsDOM();
                applyChartPanelRatios();
                initSubcharts();
            }
        }
    }
    loadTechnicalIndicators();
    const panel = document.getElementById('indicator-library-panel');
    if (panel && !panel.classList.contains('hidden')) {
        renderIndicatorLibrary();
    }
    renderActiveIndicatorTags();
}

// 复权设置
async function updateAdjustment(targetRange = null) {
    // === intraday_30m 分支: 复权接口由 legacy kline_processor 支持，
    // intraday 模式不具备该后端依赖，因此直接返回，不发起请求 ===
    if (isIntradayMode()) {
        return;
    }

    const checkedAdjustment = document.querySelector('input[name="adjustment"]:checked');
    const adjustment = checkedAdjustment ? checkedAdjustment.value : 'forward';

    const maQuery = maPeriods.join(',');
    try {
        const visibleRange = targetRange || chart.timeScale().getVisibleLogicalRange();

        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/adjustment?ma_periods=${maQuery}&${getViewPeriodQuery()}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ adjustment })
        });

        if (response.ok) {
            const data = await response.json();
            applyTrainingSnapshot({
                ...data,
                progress: currentTraining?.latestProgress || null,
                trade_markers: currentPeriod === 'daily' ? (currentTraining?.tradeMarkers || []) : []
            });
            renderChartLegend();

            if (visibleRange !== null) {
                setVisibleRangeAll(visibleRange);
            }

            await updateChipDistribution();
        }
    } catch (error) {
        console.error('更新复权设置失败:', error);
    }
}

// 交易操作
function limitTradeQuantity() {
    const input = document.getElementById('trade-quantity');
    // const maxQuantity = parseInt(document.getElementById('max-quantity').textContent) || 0;

    // if (parseInt(input.value) > maxQuantity) {
    //     input.value = maxQuantity;
    // }
    if (parseInt(input.value) > input.max) {
        input.value = input.max;
    }
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatMoney(value) {
    const num = Number(value || 0);
    return `¥${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatReturn(value) {
    const num = Number(value || 0);
    return `${num.toFixed(2)}%`;
}

async function loadHistoryDashboard() {
    if (!currentUser) return;
    const list = document.getElementById('history-list');
    const summary = document.getElementById('history-summary-strip');
    if (!list || !summary) return;

    try {
        const response = await fetch(`${API_BASE}/users/${encodeURIComponent(currentUser)}/history?limit=50`);
        if (!response.ok) throw new Error(`history status ${response.status}`);
        const sessions = await response.json();

        const completed = sessions.filter(item => item.status === 'completed' || item.status === 'ended');
        const visibleSessions = sessions.filter((session) => {
            if (currentHistoryFilter === 'completed') return session.status === 'completed' || session.status === 'ended';
            if (currentHistoryFilter === 'summary') return !!(session.review_summary || '').trim();
            return true;
        });
        const recordCount = document.getElementById('history-record-count');
        if (recordCount) recordCount.textContent = `${visibleSessions.length} / ${sessions.length} 条记录`;
        const totalReturn = completed.reduce((sum, item) => sum + Number(item.total_return || 0), 0);
        const best = completed.reduce((max, item) => Math.max(max, Number(item.total_return || 0)), completed.length ? -Infinity : 0);
        const totalTrades = completed.reduce((sum, item) => sum + Number(item.total_trades || 0), 0);

        summary.innerHTML = `
            <div class="history-metric"><span class="label">完成复盘</span><span class="value">${completed.length}</span></div>
            <div class="history-metric"><span class="label">平均收益</span><span class="value ${totalReturn >= 0 ? 'positive' : 'negative'}">${formatReturn(completed.length ? totalReturn / completed.length : 0)}</span></div>
            <div class="history-metric"><span class="label">最佳收益</span><span class="value ${best >= 0 ? 'positive' : 'negative'}">${formatReturn(best)}</span></div>
            <div class="history-metric"><span class="label">交易次数</span><span class="value">${totalTrades}</span></div>
        `;

        if (!visibleSessions.length) {
            list.innerHTML = '<div class="history-empty">暂无历史训练，完成一次训练后会显示在这里。</div>';
            return;
        }

        list.innerHTML = visibleSessions.map(session => {
            const returnValue = Number(session.total_return || 0);
            const hasSummary = !!(session.review_summary || '').trim();
            return `
                <article class="history-card" data-session-id="${escapeHtml(session.session_id)}">
                    <div class="history-card-head">
                        <div class="history-instrument">
                            <span class="history-icon">↗</span>
                            <div>
                                <strong>${escapeHtml(session.stock_name || session.stock_code)}</strong>
                                <span>${escapeHtml(session.stock_code || '-')} · ${hasSummary ? '已写心得' : '待写心得'}</span>
                            </div>
                        </div>
                        <div class="history-return ${returnValue >= 0 ? 'positive' : 'negative'}">
                            <strong>${formatReturn(returnValue)}</strong>
                            <span>${session.total_trades || 0} 笔交易</span>
                        </div>
                    </div>
                    <div class="history-card-info">
                        <span>训练区间：${escapeHtml(session.start_date || '-')} 至 ${escapeHtml(session.end_date || '-')}</span>
                        <span>胜率：${formatReturn(session.trade_win_rate || 0)}</span>
                    </div>
                    <div class="history-card-actions">
                        <button class="btn btn-secondary history-open-btn" data-session-id="${escapeHtml(session.session_id)}" type="button">${hasSummary ? '查看复盘' : '写心得'}</button>
                        <button class="btn btn-primary history-open-btn" data-session-id="${escapeHtml(session.session_id)}" type="button">查看 K 线</button>
                        <button class="btn btn-quiet-danger history-delete-btn" data-session-id="${escapeHtml(session.session_id)}" type="button">删除</button>
                    </div>
                </article>
            `;
        }).join('');

        list.querySelectorAll('.history-open-btn').forEach(button => {
            button.addEventListener('click', () => openHistoryReport(button.dataset.sessionId));
        });
        list.querySelectorAll('.history-delete-btn').forEach(button => {
            button.addEventListener('click', () => deleteHistorySession(button.dataset.sessionId));
        });
    } catch (error) {
        console.error('加载历史看板失败:', error);
        list.innerHTML = '<div class="history-empty">历史看板加载失败，请稍后重试。</div>';
    }
}

async function deleteHistorySession(sessionId) {
    if (!currentUser || !sessionId) return;
    if (!confirm('确定删除这条训练记录吗？删除后无法恢复。')) return;

    try {
        const response = await fetch(`${API_BASE}/users/${encodeURIComponent(currentUser)}/history/${encodeURIComponent(sessionId)}`, {
            method: 'DELETE'
        });
        const result = await response.json();
        if (!response.ok) {
            alert(result.error || '删除训练记录失败');
            return;
        }
        await loadHistoryDashboard();
    } catch (error) {
        console.error('删除训练记录失败:', error);
        alert('删除训练记录失败');
    }
}

async function openHistoryReport(sessionId) {
    if (!currentUser || !sessionId) return;
    try {
        const response = await fetch(`${API_BASE}/users/${encodeURIComponent(currentUser)}/history/${encodeURIComponent(sessionId)}`);
        const report = await response.json();
        if (!response.ok) {
            alert(report.error || '打开历史复盘失败');
            return;
        }
        showReport(report);
    } catch (error) {
        console.error('打开历史复盘失败:', error);
        alert('打开历史复盘失败');
    }
}

function updateTradeReasonCount() {
    const input = document.getElementById('trade-reason-text');
    const count = document.getElementById('trade-reason-count');
    if (input && count) count.textContent = input.value.length;
}

function requestTradeWithReason(action, priceType) {
    if (isAshareLiveMode) {
        return action === 'buy' ? executeAshareLiveBuy() : executeAshareLiveSell();
    }
    if (skipTradeReasonPrompt) {
        return action === 'buy' ? executeBuy(priceType) : executeSell(priceType);
    }

    pendingTradeReasonAction = { action, priceType };
    const modal = document.getElementById('trade-reason-modal');
    const title = document.getElementById('trade-reason-title');
    const body = document.getElementById('trade-reason-body');
    const editor = document.getElementById('trade-reason-editor');
    const skipRow = document.getElementById('trade-reason-skip-row');
    const cancel = document.getElementById('cancel-trade-reason-btn');
    const close = document.getElementById('close-trade-reason-btn');
    const save = document.getElementById('save-trade-reason-btn');
    const input = document.getElementById('trade-reason-text');
    const skip = document.getElementById('trade-reason-skip');
    if (!modal || !title || !body || !editor || !skipRow || !cancel || !close || !save || !input || !skip) return;

    title.textContent = `你${action === 'buy' ? '买入' : '卖出'}的理由是什么？`;
    body.textContent = '填写理由有助于在复盘时回顾当时的判断，也可以直接跳过。';
    input.value = '';
    skip.checked = false;
    updateTradeReasonCount();
    editor.classList.remove('hidden');
    skipRow.classList.remove('hidden');
    cancel.classList.remove('hidden');
    save.classList.remove('hidden');
    close.classList.add('hidden');
    modal.classList.remove('hidden');
    input.focus();
}

function cancelTradeReasonPrompt() {
    const pending = pendingTradeReasonAction;
    const skip = document.getElementById('trade-reason-skip');
    skipTradeReasonPrompt = Boolean(skip?.checked);
    pendingTradeReasonAction = null;
    closeTradeReasonModal();
    if (pending) return pending.action === 'buy' ? executeBuy(pending.priceType) : executeSell(pending.priceType);
}

function submitTradeReasonPrompt() {
    const pending = pendingTradeReasonAction;
    const input = document.getElementById('trade-reason-text');
    const skip = document.getElementById('trade-reason-skip');
    const reason = input?.value.trim() || '';
    skipTradeReasonPrompt = Boolean(skip?.checked);
    pendingTradeReasonAction = null;
    closeTradeReasonModal();
    if (pending) return pending.action === 'buy' ? executeBuy(pending.priceType, reason) : executeSell(pending.priceType, reason);
}
function showTradeReasonModal(trade) {
    const modal = document.getElementById('trade-reason-modal');
    if (!modal || !trade) return;
    pendingTradeReasonAction = null;
    document.getElementById('trade-reason-editor')?.classList.add('hidden');
    document.getElementById('trade-reason-skip-row')?.classList.add('hidden');
    document.getElementById('cancel-trade-reason-btn')?.classList.add('hidden');
    document.getElementById('save-trade-reason-btn')?.classList.add('hidden');
    document.getElementById('close-trade-reason-btn')?.classList.remove('hidden');
    document.getElementById('trade-reason-title').textContent = `${trade.action === 'buy' ? '买入' : '卖出'}理由 · Bar ${trade.bar_id}`;
    document.getElementById('trade-reason-body').innerHTML = `
        <div>日期：${escapeHtml(trade.date || trade.trade_date || '-')}</div>
        <div>价格：${formatMoney(trade.price || 0)}，数量：${escapeHtml(trade.quantity || 0)} 手</div>
        <div class="trade-reason-text">${escapeHtml(trade.reason || '没有填写理由')}</div>
    `;
    modal.classList.remove('hidden');
}

function closeTradeReasonModal() {
    document.getElementById('trade-reason-modal')?.classList.add('hidden');
}

function createReviewSummaryEditor(parentElement, report) {
    const section = document.createElement('div');
    section.className = 'review-summary-editor';
    section.innerHTML = `
        <h3>我的复盘总结</h3>
        <textarea id="review-summary-text" rows="5" placeholder="写下这次训练的经验、失误、下次要注意什么">${escapeHtml(report.review_summary || '')}</textarea>
        <div class="modal-actions">
            <span id="review-summary-status" class="review-summary-status" role="status"></span>
            <button id="save-review-summary-btn" class="btn btn-primary">保存总结</button>
        </div>
    `;
    parentElement.appendChild(section);
    section.querySelector('#save-review-summary-btn').addEventListener('click', saveReviewSummary);
}

function setReviewSummaryStatus(message = '', type = '') {
    const status = document.getElementById('review-summary-status');
    if (!status) return;
    status.textContent = message;
    status.className = `review-summary-status ${type}`.trim();
}

async function saveReviewSummary() {
    const reportSessionId = currentReportData?.session_id || currentTraining?.id;
    if (!currentUser || !reportSessionId) {
        setReviewSummaryStatus('当前报告未关联训练会话，暂时无法保存。', 'error');
        return;
    }
    const summary = document.getElementById('review-summary-text')?.value || '';
    setReviewSummaryStatus('正在保存…', 'saving');
    try {
        const response = await fetch(`${API_BASE}/users/${encodeURIComponent(currentUser)}/history/${encodeURIComponent(reportSessionId)}/summary`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ summary })
        });
        const result = await response.json();
        if (!response.ok) {
            setReviewSummaryStatus(result.error || '保存总结失败，请稍后重试。', 'error');
            return;
        }
        currentReportData.review_summary = result.review_summary;
        await loadHistoryDashboard();
        setReviewSummaryStatus('总结已保存到本次训练记录。', 'success');
    } catch (error) {
        console.error('保存总结失败:', error);
        setReviewSummaryStatus('网络连接异常，保存失败。', 'error');
    }
}

function limitSellQuantity() {
    const input = document.getElementById('sell-quantity');
    if (!input) return;
    if (parseInt(input.value) > parseInt(input.max)) {
        input.value = input.max;
    }
}

function setOrderType(orderType) {
    currentOrderType = orderType || 'market';
    document.querySelectorAll('.order-type-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.orderType === currentOrderType);
    });

    const triggerGroup = document.getElementById('trigger-price-group');
    if (triggerGroup) {
        triggerGroup.classList.toggle('hidden', currentOrderType === 'market');
    }

    const buyBtn = document.getElementById('buy-btn');
    if (buyBtn) {
        buyBtn.textContent = currentOrderType === 'market'
            ? `买(${(isShiftClicked || isShiftKeyPressed) ? '开盘' : '收盘'})`
            : '挂买单';
        buyBtn.disabled = currentLimitStatus === 'limit_up' && currentOrderType === 'market';
    }
}

function getOptionalPriceInput(id) {
    const value = parseFloat(document.getElementById(id)?.value);
    return Number.isFinite(value) && value > 0 ? value : null;
}

function formatOrderType(orderType) {
    if (orderType === 'limit') return '限价买入';
    if (orderType === 'breakout') return '突破买入';
    if (orderType === 'take_profit') return '止盈卖出';
    if (orderType === 'stop_loss') return '止损卖出';
    return orderType;
}

function renderPendingOrders(pendingOrders) {
    const container = document.getElementById('pending-orders');
    if (!container) return;

    const buyOrders = pendingOrders?.buy_orders || [];
    const exitOrders = pendingOrders?.exit_orders || [];
    const orders = [...buyOrders, ...exitOrders];

    if (orders.length === 0) {
        container.classList.add('hidden');
        container.innerHTML = '';
        return;
    }

    container.classList.remove('hidden');
    container.innerHTML = orders.map(order => `
        <div class="pending-order-item">
            <div class="pending-order-main">
                <strong>${formatOrderType(order.order_type)} · ${order.quantity} 手</strong>
                <span class="pending-order-meta">触发价 ¥${Number(order.trigger_price).toFixed(2)}</span>
            </div>
            <button class="btn-cancel-order" data-order-id="${order.id}" type="button">撤单</button>
        </div>
    `).join('');

    container.querySelectorAll('.btn-cancel-order').forEach(button => {
        button.addEventListener('click', () => cancelPendingOrder(button.dataset.orderId));
    });
}

async function cancelPendingOrder(orderId) {
    if (!currentTraining || !orderId) return;

    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/orders/${orderId}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        if (!response.ok) {
            if (isCryptoMode()) {
                await updateAccountInfo();
                setCryptoOrderStatus(data.message || data.error || '撤单失败，请刷新后重试。', 'error');
                return;
            }
            alert(data.error || '撤单失败');
            return;
        }
        if (isCryptoMode()) {
            await updateAccountInfo();
            setCryptoOrderStatus(data.message || '挂单已撤销。', 'success');
        } else {
            renderPendingOrders(data.pending_orders);
        }
    } catch (error) {
        console.error('撤单失败:', error);
        if (isCryptoMode()) {
            setCryptoOrderStatus(error.message || '撤单失败，请检查连接后重试。', 'error');
            return;
        }
        alert('撤单失败');
    }
}

async function executeBuy(priceType = 'close', reason = '') {
    if (currentOrderType === 'market' && currentLimitStatus === 'limit_up') {
        alert('当前涨停，无法买入！');
        return;
    }

    // intraday 模式下成交价恒为当前 base bar close，不需要为 'open' 推进一根
    if (!isIntradayMode() && currentOrderType === 'market' && priceType === 'open') {
        const hasNext = await nextBar();
        if (!hasNext) {
            return; // 训练结束或出错
        }
    }

    const quantity = parseInt(document.getElementById('trade-quantity').value);
    const triggerPrice = getOptionalPriceInput('trigger-price');
    if (currentOrderType !== 'market' && !triggerPrice) {
        alert('请填写有效触发价');
        return;
    }
    if (!quantity || quantity <= 0) {
        alert('请输入有效的交易数量');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/trade`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'buy',
                quantity: quantity,
                price_type: priceType,
                order_type: currentOrderType,
                trigger_price: triggerPrice,
                take_profit_price: getOptionalPriceInput('take-profit-price'),
                stop_loss_price: getOptionalPriceInput('stop-loss-price'),
                reason
            })
        });

        if (response.ok) {
            const result = await response.json();
            renderPendingOrders(result.pending_orders);
            await updateAccountInfo();
            if (result.trade) {
                addTradeRecord(result.trade);
            }
            if (result.trade_markers) {
                syncActiveTradeMarkers(result.trade_markers);
            }
        } else {
            const error = await response.json();
            alert(error.message || '买入失败');
        }
    } catch (error) {
        console.error('买入失败:', error);
        alert('买入失败');
    }
}

async function executeSell(priceType = 'close', reason = '') {
    if (currentLimitStatus === 'limit_down') {
        alert('当前跌停，无法卖出！');
        return;
    }

    // intraday 模式下成交价恒为当前 base bar close，不需要为 'open' 推进一根
    if (!isIntradayMode() && priceType === 'open') {
        const hasNext = await nextBar();
        if (!hasNext) {
            return; // 训练结束或出错
        }
    }

    const quantity = parseInt(document.getElementById('sell-quantity')?.value || document.getElementById('trade-quantity').value);
    if (!quantity || quantity <= 0) {
        alert('请输入有效的交易数量');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/trade`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'sell',
                quantity: quantity,
                price_type: priceType,
                reason
            })
        });

        if (response.ok) {
            const result = await response.json();
            updateAccountInfo();
            addTradeRecord(result.trade);
            syncActiveTradeMarkers(result.trade_markers);
        } else {
            const error = await response.json();
            alert(error.message || '卖出失败');
        }
    } catch (error) {
        console.error('卖出失败:', error);
        alert('卖出失败');
    }
}

function setCryptoFeeStatus(message, state = '') {
    const status = document.getElementById('crypto-fee-status');
    if (!status) return;
    status.textContent = message || '';
    status.className = 'crypto-fee-status' + (state ? ' ' + state : '');
}

function formatCryptoFeePercent(rate) {
    const percent = Number(rate) * 100;
    return Number.isFinite(percent) ? String(Number(percent.toFixed(4))) : '';
}

function syncCryptoFeeRateInputs(constraints, canEdit = true) {
    const fields = [
        ['crypto-maker-fee-rate', 'maker_fee_rate'],
        ['crypto-taker-fee-rate', 'taker_fee_rate'],
    ];
    fields.forEach(([id, key]) => {
        const input = document.getElementById(id);
        if (!input) return;
        if (document.activeElement !== input && Number.isFinite(Number(constraints?.[key]))) {
            input.value = formatCryptoFeePercent(constraints[key]);
        }
        input.disabled = !canEdit || cryptoFeeSubmitting;
    });
    const button = document.getElementById('crypto-save-fee-rates');
    if (button) button.disabled = !canEdit || cryptoFeeSubmitting;
}

async function submitCryptoFeeRates() {
    if (!currentTraining?.id || !isCryptoMode() || cryptoFeeSubmitting) return;
    const submitButton = document.getElementById('crypto-save-fee-rates');
    const makerPercent = Number(document.getElementById('crypto-maker-fee-rate')?.value);
    const takerPercent = Number(document.getElementById('crypto-taker-fee-rate')?.value);
    if (![makerPercent, takerPercent].every(value => Number.isFinite(value) && value >= 0 && value <= 1)) {
        setCryptoFeeStatus('请输入 0% 到 1% 之间的有效费率。', 'error');
        return;
    }
    cryptoFeeSubmitting = true;
    if (submitButton) submitButton.disabled = true;
    setCryptoFeeStatus('正在应用手续费率…', 'loading');
    try {
        const response = await fetch(API_BASE + '/training/' + encodeURIComponent(currentTraining.id) + '/fee-rates', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ maker_fee_rate: makerPercent / 100, taker_fee_rate: takerPercent / 100 }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || '手续费率更新失败');
        renderCryptoAccount(payload);
        setCryptoFeeStatus(payload.message || '手续费率已更新，仅影响后续成交。', 'success');
    } catch (error) {
        console.error('更新合约手续费率失败:', error);
        setCryptoFeeStatus(error.message || '手续费率更新失败', 'error');
    } finally {
        cryptoFeeSubmitting = false;
        const position = currentTraining?.position || {};
        const pendingOrders = currentTraining?.pending_orders || [];
        const canEdit = (!position.side || position.side === 'flat') && pendingOrders.length === 0;
        syncCryptoFeeRateInputs(cryptoOrderConstraints, canEdit);
    }
}

// 账户信息更新
function renderCryptoAccount(accountPayload) {
    const account = accountPayload?.account || accountPayload || {};
    const position = accountPayload?.position || account.position || {};
    cryptoOrderConstraints = accountPayload?.order_constraints || account.order_constraints || cryptoOrderConstraints;
    const pendingOrders = accountPayload?.pending_orders || account.pending_orders || [];
    // 更新 currentCryptoSummary 供下单面板/磁吸/持仓计算使用
    currentCryptoSummary = {
        account_equity: account.equity ?? account.total_assets ?? null,
        balance: account.available_balance ?? account.available_cash ?? null,
        position: position,
        account: account,
    };
    if (currentTraining) {
        currentTraining.account = account;
        currentTraining.position = position;
        currentTraining.pending_orders = pendingOrders;
        currentTraining.order_constraints = cryptoOrderConstraints;
    }
    const canEditFees = (!position.side || position.side === 'flat') && pendingOrders.length === 0;
    syncCryptoFeeRateInputs(cryptoOrderConstraints, canEditFees);
    if (!canEditFees && !cryptoFeeSubmitting) {
        setCryptoFeeStatus('请先平仓并撤销挂单，再修改手续费率。');
    }
    const equity = Number(account.equity ?? account.total_assets ?? 0);
    const available = Number(account.available_balance ?? account.available_cash ?? 0);
    const positionValue = Number(position.notional ?? account.position_value ?? 0);
    const unrealized = Number(position.unrealized_pnl ?? account.unrealized_pnl ?? account.floating_pnl ?? 0);
    document.getElementById('crypto-total-assets').textContent = equity.toLocaleString() + ' USDT';
    document.getElementById('crypto-available-cash').textContent = available.toLocaleString() + ' USDT';
    document.getElementById('crypto-position-value').textContent = positionValue.toLocaleString() + ' USDT';
    document.getElementById('crypto-floating-pnl').textContent = unrealized.toLocaleString() + ' USDT';
    document.getElementById('crypto-position-side').textContent = position.side || '空仓';
    document.getElementById('crypto-mark-price').textContent = Number(account.mark_price ?? position.mark_price ?? 0).toLocaleString();
    const liqPrice = Number(position.liquidation_price || 0);
    document.getElementById('crypto-liquidation-price').textContent = liqPrice > 0
        ? Number(liqPrice).toLocaleString()
        : (position.side && position.side !== 'flat' ? '0.00' : '--');
    document.getElementById('crypto-margin-ratio').textContent = account.margin_ratio == null ? '--' : (Number(account.margin_ratio) * 100).toFixed(2) + '%';
    const fundingNet = Number(account.funding_net ?? accountPayload?.funding_net ?? 0);
    document.getElementById('crypto-funding-summary').textContent = '资金费净额：' + fundingNet.toFixed(4) + ' USDT';
    renderCryptoPendingOrders(pendingOrders);
    renderCryptoPositionCard(account, position, pendingOrders);
    refreshCryptoOrderPreview();
    updateChartTradePriceLines();
}

// ===== 主图持仓均价线与止盈止损/挂单线可视化 (AICoin / TradingView 风格) =====
function clearChartTradePriceLines() {
    if (typeof activeTradeLinePills !== 'undefined' && activeTradeLinePills.length) {
        activeTradeLinePills.forEach((pill) => pill.remove());
        activeTradeLinePills = [];
    }
    if (typeof candlestickSeries === 'undefined' || !candlestickSeries || typeof activeChartTradePriceLines === 'undefined' || !activeChartTradePriceLines || !activeChartTradePriceLines.length) {
        if (typeof activeChartTradePriceLines !== 'undefined') activeChartTradePriceLines = [];
        return;
    }
    activeChartTradePriceLines.forEach((item) => {
        const line = item?.line || item;
        try {
            if (line && typeof candlestickSeries?.removePriceLine === 'function') {
                candlestickSeries.removePriceLine(line);
            }
        } catch (e) {
            // 忽略图表重置时的移除异常
        }
    });
    activeChartTradePriceLines = [];
}

let chartTradeLineDragBound = false;
let currentDraggedTradeLine = null;
let chartDragTooltipEl = null;

function getChartDragTooltip() {
    if (!chartDragTooltipEl) {
        chartDragTooltipEl = document.createElement('div');
        chartDragTooltipEl.className = 'chart-price-line-tooltip';
        document.body.appendChild(chartDragTooltipEl);
    }
    return chartDragTooltipEl;
}

function initChartTradeLineDragging() {
    if (typeof document === 'undefined' || !document || typeof window === 'undefined') return;
    if (chartTradeLineDragBound) return;
    const chartEl = document.getElementById('chart');
    if (!chartEl) return;
    chartTradeLineDragBound = true;

    function getHoveredTradeLine(e) {
        if (!candlestickSeries || !activeChartTradePriceLines.length) return null;
        if (drawingController?.activeTool && drawingController.activeTool !== 'select') return null;
        const rect = chartEl.getBoundingClientRect();
        const mouseY = e.clientY - rect.top;
        const mouseX = e.clientX - rect.left;
        if (mouseX < 0 || mouseX > rect.width || mouseY < 0 || mouseY > rect.height) return null;

        for (const item of activeChartTradePriceLines) {
            // 占位保护线没有 orderId，但同样可拖：拖动 = 按新价创建真实止盈/止损单
            if (!item?.price || (!item.orderId && !item.isPlaceholder)) continue;
            try {
                const lineY = candlestickSeries.priceToCoordinate(item.price);
                if (lineY != null && Math.abs(mouseY - lineY) <= 8) {
                    return item;
                }
            } catch (err) {}
        }
        return null;
    }

    chartEl.addEventListener('pointermove', (e) => {
        if (currentDraggedTradeLine) {
            e.preventDefault();
            const rect = chartEl.getBoundingClientRect();
            const mouseY = Math.max(0, Math.min(rect.height, e.clientY - rect.top));
            const newPrice = candlestickSeries.coordinateToPrice(mouseY);
            if (newPrice != null && newPrice > 0 && Number.isFinite(newPrice)) {
                currentDraggedTradeLine.tempPrice = Number(newPrice.toFixed(2));
                const item = currentDraggedTradeLine.item;
                const priceFormatted = formatCryptoValue(currentDraggedTradeLine.tempPrice);
                let typeClass = 'limit';
                if (item.type === 'tp') typeClass = 'tp';
                else if (item.type === 'sl') typeClass = 'sl';

                try {
                    // AICoin 观感：拖动过程中也不往线上写文字，提示只出现在跟随光标的气泡里
                    item.line.applyOptions({
                        price: currentDraggedTradeLine.tempPrice,
                        title: '',
                    });
                } catch (err) {}

                const tooltip = getChartDragTooltip();
                tooltip.className = `chart-price-line-tooltip ${typeClass}`;
                tooltip.style.display = 'block';
                tooltip.style.left = `${e.clientX + 14}px`;
                tooltip.style.top = `${e.clientY}px`;

                let pnlText = '';
                if (item.entryPrice > 0) {
                    const isLong = item.side === 'open_long' || item.side === 'long' || (item.order?.action === 'open_long');
                    const diff = isLong ? (currentDraggedTradeLine.tempPrice - item.entryPrice) : (item.entryPrice - currentDraggedTradeLine.tempPrice);
                    const pct = (diff / item.entryPrice) * 100;
                    const pnlUsdt = (item.quantity || 0) * diff;
                    pnlText = ` (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}% | ${pnlUsdt >= 0 ? '+' : ''}${formatCryptoValue(pnlUsdt, 2)} USDT)`;
                }
                tooltip.textContent = `松开修改为: $${priceFormatted}${pnlText}`;
            }
            return;
        }

        const hovered = getHoveredTradeLine(e);
        if (hovered) {
            chartEl.style.cursor = 'ns-resize';
        } else if (chartEl.style.cursor === 'ns-resize') {
            chartEl.style.cursor = 'crosshair';
        }
    });

    chartEl.addEventListener('pointerdown', (e) => {
        if (e.button !== 0) return;
        const hovered = getHoveredTradeLine(e);
        if (!hovered) return;

        e.preventDefault();
        e.stopPropagation();
        try { chartEl.setPointerCapture(e.pointerId); } catch (err) {}

        currentDraggedTradeLine = {
            item: hovered,
            pointerId: e.pointerId,
            startPrice: hovered.price,
            tempPrice: hovered.price,
        };
        document.body.classList.add('chart-dragging-order');
    });

    async function finishDrag(e) {
        if (!currentDraggedTradeLine) return;
        const dragInfo = currentDraggedTradeLine;
        currentDraggedTradeLine = null;
        document.body.classList.remove('chart-dragging-order');
        if (chartDragTooltipEl) chartDragTooltipEl.style.display = 'none';
        try { chartEl.releasePointerCapture(dragInfo.pointerId); } catch (err) {}

        const finalPrice = dragInfo.tempPrice;
        const item = dragInfo.item;

        // 从「止盈/止损」徽标拖出来的临时线：无论有没有移动过都按当前价创建保护单
        // （点一下 = 按默认 ±2% 放置；拖动了 = 按拖到的价位）
        if (item.isPlaceholder) {
            const created = await createProtectiveOrderFromDrag(item, finalPrice || dragInfo.startPrice);
            if (created) updateChartTradePriceLines();
            else removeProtectivePlaceholderLine(item);
            return;
        }

        if (!finalPrice || Math.abs(finalPrice - dragInfo.startPrice) < 0.01) {
            try { item.line.applyOptions({ price: dragInfo.startPrice }); } catch (err) {}
            return;
        }

        try {
            setCryptoOrderStatus(`⏳ 正在同步修改挂单价格至 ${formatCryptoValue(finalPrice)}...`, 'loading');
            const response = await fetch(`${API_BASE}/training/${currentTraining.id}/orders/${item.orderId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ price: finalPrice }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);

            item.price = finalPrice;
            if (Array.isArray(data.pending_orders)) {
                currentTraining.pending_orders = data.pending_orders;
                renderCryptoPendingOrders(data.pending_orders);
            }
            updateChartTradePriceLines();
            setCryptoOrderStatus(`⚡ 已成功将挂单修改为 ${formatCryptoValue(finalPrice)} USDT`, 'ready');
        } catch (err) {
            console.error('修改挂单价格失败:', err);
            setCryptoOrderStatus(`❌ 改单失败: ${err.message}`, 'error');
            try { item.line.applyOptions({ price: dragInfo.startPrice }); } catch (e) {}
        }
    }

    chartEl.addEventListener('pointerup', finishDrag);
    chartEl.addEventListener('pointercancel', finishDrag);
}

/**
 * AICoin 风格的价格线文案：止盈/止损 价格 + 距现价% + 预估收益。
 * 让用户拖动时直接看懂"拖到这里会赚/亏多少"。
 */
function buildChartProtectiveLineTitle(label, price, side, quantity, entryPrice) {
    const target = Number(price);
    let text = label + ': ' + formatCryptoValue(target);
    const current = Number(typeof getCryptoCurrentPrice === 'function' ? getCryptoCurrentPrice() : 0);
    if (Number.isFinite(current) && current > 0) {
        const distancePct = ((target - current) / current) * 100;
        text += ' 距现价 ' + (distancePct >= 0 ? '+' : '') + distancePct.toFixed(2) + '%';
    }
    const qty = Number(quantity || 0);
    const entry = Number(entryPrice || 0);
    if (qty > 0 && entry > 0) {
        const isLongSide = side === 'long' || side === 'open_long';
        const pnl = (isLongSide ? (target - entry) : (entry - target)) * qty;
        text += ' 预估 ' + (pnl >= 0 ? '+' : '') + formatCryptoValue(pnl, 2) + ' USDT';
    }
    return text;
}

/**
 * 平仓保护单（止盈/止损）该用哪种挂单类型 —— 这是"止损线还没到就被平仓"的根因。
 *
 * 引擎对"卖出限价"的撮合条件是 high >= 限价，所以挂在现价**下方**的平仓限价
 * 属于可立即成交的单子，下一根 K 线就会当场成交；它只能当止盈，不能当止损。
 * 止损必须用突破单（价格穿越触发价才成交）。规则：
 *   多头（平仓方向 sell）：价在上 = 止盈(限价)；价在下 = 止损(突破)
 *   空头（平仓方向 buy ）：价在下 = 止盈(限价)；价在上 = 止损(突破)
 */
function resolveCloseOrderType(price, currentPrice, closeSide) {
    const target = Number(price);
    const mark = Number(currentPrice);
    if (!Number.isFinite(target) || !Number.isFinite(mark) || !(mark > 0)) return 'limit';
    return closeSide === 'buy'
        ? (target < mark ? 'limit' : 'breakout')
        : (target > mark ? 'limit' : 'breakout');
}

/**
 * 拖动「止盈/止损」徽标放到某价位 = 创建一张真实的平仓保护单。
 * 类型由价位自动判定：止盈走限价（等价格涨/跌到），止损走突破（价格穿越才触发）。
 * 挂单会一直等到价格触及，天然支持只平一部分（数量可在下单区调整后再拖）。
 */
async function createProtectiveOrderFromDrag(item, price) {
    if (!currentTraining?.id || cryptoOrderSubmitting) return false;
    const target = Number(price);
    if (!Number.isFinite(target) || target <= 0) return false;
    const closeSide = getCryptoPendingSide('close');
    if (!closeSide) {
        setCryptoOrderStatus('❌ 当前没有可平仓的持仓。', 'error');
        return false;
    }
    const mark = Number(typeof getCryptoCurrentPrice === 'function' ? getCryptoCurrentPrice() : 0);
    if (!(mark > 0)) {
        setCryptoOrderStatus('❌ 暂时无法取得标记价，请刷新账户后重试。', 'error');
        return false;
    }
    if (Math.abs(target - mark) < Math.max(1e-8, mark * 1e-6)) {
        setCryptoOrderStatus('❌ 保护价不能等于当前标记价，请拖到其他价位。', 'error');
        return false;
    }
    // 关键：止损必须发突破单（价格穿越触发才成交）。若发限价单，引擎按 high>=限价 撮合，
    // 挂在现价下方的止损下一根 K 线就会当场成交平仓。
    const orderType = resolveCloseOrderType(target, mark, closeSide);
    const isTakeProfit = orderType === 'limit';
    const roleText = isTakeProfit ? '止盈' : '止损';
    const typeText = isTakeProfit ? '限价' : '突破';
    cryptoOrderSubmitting = true;
    try {
        setCryptoOrderStatus(`⏳ 正在创建${roleText}单（${typeText}） @ ${formatCryptoValue(target)}...`, 'loading');
        const response = await fetch(API_BASE + '/training/' + encodeURIComponent(currentTraining.id) + '/trade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderType === 'limit'
                ? { action: 'close', order_type: 'limit', limit_price: target }
                : { action: 'close', order_type: 'breakout', trigger_price: target }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
        if (Array.isArray(payload.pending_orders)) {
            currentTraining.pending_orders = payload.pending_orders;
            renderCryptoPendingOrders(payload.pending_orders);
        }
        setCryptoOrderStatus(`⚡ 已创建${roleText}单（${typeText}）：${formatCryptoValue(target)} USDT（可在图上继续拖动改价）`, 'ready');
        return true;
    } catch (error) {
        console.error('创建止盈止损单失败:', error);
        setCryptoOrderStatus(`❌ 创建失败: ${error.message}`, 'error');
        return false;
    } finally {
        cryptoOrderSubmitting = false;
    }
}

// ===== AICoin 风格价格线药丸（贴价格轴，可拖动 / 可撤单 / 可切换止盈止损）=====

/**
 * 保护线的浮动盈亏：优先按保证金收益率（与 AICoin 一致），没有保证金信息时退化为价格涨跌幅。
 */
function computeProtectiveLinePnl(item) {
    const price = Number(item?.price || 0);
    const entry = Number(item?.entryPrice || 0);
    if (!(price > 0) || !(entry > 0)) return null;
    // 盈亏方向必须按"持仓方向"算，不能按订单方向：平仓单的 side 是 sell/buy，
    // 拿它判断多空会把多头的止盈算成亏损。
    const positionSide = (typeof currentTraining !== 'undefined' && currentTraining?.position?.side) || item.side;
    const isLongSide = positionSide === 'long' || positionSide === 'open_long';
    const diff = isLongSide ? (price - entry) : (entry - price);
    const quantity = Number(item.quantity || 0);
    const margin = Number((typeof currentTraining !== 'undefined' && currentTraining?.position?.isolated_margin) || 0);
    let ratePct = null;
    if (margin > 0 && quantity > 0) ratePct = (diff * quantity / margin) * 100;
    else ratePct = (diff / entry) * 100;
    return { diff: diff, pnl: quantity > 0 ? diff * quantity : null, ratePct: ratePct };
}

/** 药丸上的 ✕：真实挂单走撤单接口，占位线则本次会话不再显示 */
function dismissTradeLinePill(item) {
    if (!item) return;
    if (item.orderId) {
        cancelPendingOrder(item.orderId);
        return;
    }
    suppressedProtectivePlaceholders.add(item.type);
    updateChartTradePriceLines();
}

/** 切换保护线角色（止盈↔止损）：把线镜像到成本价另一侧 */
async function flipProtectiveLineRole(item) {
    const entry = Number(item?.entryPrice || 0);
    if (!(entry > 0)) return;
    const isLongSide = item.side !== 'short';
    const distance = Math.abs(Number(item.price) - entry) || entry * 0.02;
    const nextIsTp = item.type === 'sl';
    const nextPrice = Number((nextIsTp ? entry + distance : entry - distance).toFixed(2));
    if (!(nextPrice > 0)) return;
    item.type = nextIsTp ? 'tp' : 'sl';
    if (item.orderId) {
        try {
            const response = await fetch(`${API_BASE}/training/${currentTraining.id}/orders/${item.orderId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ price: nextPrice }),
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            item.price = nextPrice;
        } catch (error) {
            setCryptoOrderStatus(`❌ 切换止盈/止损失败: ${error.message}`, 'error');
        }
    } else {
        item.price = nextPrice;
    }
    updateChartTradePriceLines();
}

/** 挂单描述：限价卖出开空 / 突破买入开多 …（对齐 AICoin 行内文案） */
function describeCryptoPendingOrder(order) {
    if (!order) return '';
    const typeText = { limit: '限价', breakout: '突破', market: '市价' }[order.order_type] || '挂单';
    const sideText = order.side === 'sell' ? '卖出' : '买入';
    const actionText = { open_long: '开多', open_short: '开空', close: '平仓' }[order.action] || '';
    return typeText + sideText + actionText;
}

/** 保护线相对当前标记价的百分比（AICoin 的「距当前价」） */
function computeProtectiveDistancePct(item) {
    const current = Number(typeof getCryptoCurrentPrice === 'function' ? getCryptoCurrentPrice() : 0);
    const price = Number(item?.price || 0);
    if (!(current > 0) || !(price > 0)) return null;
    return ((price - current) / current) * 100;
}

const CHART_TP_COLOR = '#0ecb81';
const CHART_SL_COLOR = '#f0a020';

function createPillSegment(text, className) {
    const span = document.createElement('span');
    span.className = 'pill-seg' + (className ? ' ' + className : '');
    span.textContent = text;
    return span;
}

/**
 * AICoin 的「止盈 / 止损」小徽标：按住并拖动即可放置对应保护线。
 * 也是"订单已成交但还没设止盈止损"时的入口（用户反馈：不能凭空给我画出止盈止损线）。
 */
function buildProtectivePlacementChip(item, kind) {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'pill-chip ' + (kind === 'tp' ? 'chip-tp' : 'chip-sl');
    chip.textContent = kind === 'tp' ? '止盈' : '止损';
    chip.title = kind === 'tp' ? '按住拖动放置止盈线（松开即挂单）' : '按住拖动放置止损线（松开即挂单）';
    chip.addEventListener('pointerdown', (event) => {
        event.preventDefault();
        event.stopPropagation();
        beginProtectiveLinePlacement(item, kind);
    });
    chip.addEventListener('click', (event) => event.stopPropagation());
    return chip;
}

/**
 * 从「止盈/止损」徽标开始放置保护线：先按默认距离（±2%）建一条临时线，
 * 随即接管拖动——用户按住拖动，松手时由 finishDrag 走"创建保护单"分支。
 */
function beginProtectiveLinePlacement(sourceItem, kind) {
    if (typeof document === 'undefined' || !document || !candlestickSeries) return;
    const entry = Number(sourceItem?.entryPrice
        || (typeof getCryptoCurrentPrice === 'function' ? getCryptoCurrentPrice() : 0)) || 0;
    if (!(entry > 0)) return;
    const isLongSide = sourceItem?.side !== 'short';
    const preset = kind === 'tp'
        ? entry * (isLongSide ? 1.02 : 0.98)
        : entry * (isLongSide ? 0.98 : 1.02);
    const presetPrice = Number(preset.toFixed(2));
    if (!(presetPrice > 0)) return;
    const lineStyle = (typeof LightweightCharts !== 'undefined' && LightweightCharts?.LineStyle?.Dotted != null)
        ? LightweightCharts.LineStyle.Dotted : 1;
    let tempLine = null;
    try {
        tempLine = candlestickSeries.createPriceLine({
            price: presetPrice,
            color: kind === 'tp' ? CHART_TP_COLOR : CHART_SL_COLOR,
            lineWidth: 1,
            lineStyle: lineStyle,
            axisLabelVisible: true,
            title: '',
        });
    } catch (error) {
        return;
    }
    const tempItem = {
        line: tempLine,
        type: kind,
        price: presetPrice,
        side: sourceItem?.side || 'long',
        quantity: Number(sourceItem?.quantity || 0),
        entryPrice: entry,
        isPlaceholder: true,
    };
    activeChartTradePriceLines.push(tempItem);
    buildChartTradeLinePill(tempItem);
    positionChartTradeLinePills();
    currentDraggedTradeLine = {
        item: tempItem,
        pointerId: null,
        startPrice: presetPrice,
        tempPrice: presetPrice,
    };
    document.body.classList.add('chart-dragging-order');
    setCryptoOrderStatus(`拖动放置${kind === 'tp' ? '止盈' : '止损'}线，松开即挂单`, 'loading');
}

/** 取消放置：把临时线与对应浮层一并清掉 */
function removeProtectivePlaceholderLine(item) {
    if (!item) return;
    try { candlestickSeries?.removePriceLine?.(item.line); } catch (error) {}
    if (item.pillEl) {
        item.pillEl.remove();
        activeTradeLinePills = activeTradeLinePills.filter((el) => el !== item.pillEl);
        item.pillEl = null;
    }
    activeChartTradePriceLines = activeChartTradePriceLines.filter((entry) => entry !== item);
}

function buildChartTradeLinePill(item) {
    // 纯计算/Node 测试环境下没有 DOM：直接跳过（价格线本身仍然正常创建）
    if (typeof document === 'undefined' || !document) return;
    const chartEl = document.getElementById('chart');
    if (!chartEl || !item || !item.line || item.pillEl) return;

    const pill = document.createElement('div');
    const isTp = item.type === 'tp';
    const isSl = item.type === 'sl';
    const isEntry = item.type === 'limit' || item.type === 'breakout';
    pill.className = 'trade-line-pill'
        + (isTp ? ' is-tp' : '')
        + (isSl ? ' is-sl' : '')
        + (item.type === 'position' ? ' is-position' : '')
        + (isEntry ? ' is-entry' : '')
        + (item.isPlaceholder ? ' is-placeholder' : '');

    const hasProtective = (type) => activeChartTradePriceLines.some((entry) => entry.type === type);

    if (item.type === 'position') {
        // 持仓行：多/空 数量 @ 均价 | 浮动盈亏 | 缺止盈/止损时给出放置徽标
        const sideText = item.side === 'long' ? '多' : '空';
        pill.appendChild(createPillSegment(`${sideText} ${formatCryptoValue(item.quantity)} @ ${formatCryptoValue(item.entryPrice)}`, 'seg-strong'));
        const position = (typeof currentTraining !== 'undefined' && currentTraining?.position) || {};
        const unrealized = Number(position.unrealized_pnl || 0);
        const margin = Number(position.isolated_margin || 0);
        const unrealizedPct = margin > 0 ? (unrealized / margin) * 100 : 0;
        pill.appendChild(createPillSegment(
            `${unrealized >= 0 ? '+' : ''}${formatCryptoValue(unrealized, 2)} USDT (${unrealizedPct >= 0 ? '+' : ''}${unrealizedPct.toFixed(2)}%)`,
            unrealized >= 0 ? 'seg-up' : 'seg-down'
        ));
        if (!hasProtective('tp')) pill.appendChild(buildProtectivePlacementChip(item, 'tp'));
        if (!hasProtective('sl')) pill.appendChild(buildProtectivePlacementChip(item, 'sl'));
    } else if (isTp || isSl) {
        // 保护线行：止盈/止损 | 限价/突破 | 预估收益(收益率) | 距当前价 | 数量 | ✕
        // 类型必须显示真实类型：止盈=限价（等价格到达）、止损=突破（价格穿越才触发），
        // 之前这里写死了「市价」，会让人误以为挂单会立即以市价成交。
        pill.appendChild(createPillSegment(isTp ? '止盈' : '止损', 'seg-role'));
        const protectiveTypeText = { limit: '限价', breakout: '突破', market: '市价' }[item.order?.order_type]
            || (isTp ? '限价' : '突破');
        pill.appendChild(createPillSegment(protectiveTypeText, 'seg-muted'));
        const pnl = computeProtectiveLinePnl(item);
        if (pnl) {
            const sign = pnl.pnl != null && pnl.pnl >= 0 ? '+' : '';
            pill.appendChild(createPillSegment(
                '预估收益 ' + (pnl.pnl != null ? `${sign}${formatCryptoValue(pnl.pnl, 2)} ` : '')
                + `(${sign}${pnl.ratePct.toFixed(2)}%)`,
                pnl.ratePct >= 0 ? 'seg-up' : 'seg-down'
            ));
        }
        const distancePct = computeProtectiveDistancePct(item);
        if (distancePct != null) {
            pill.appendChild(createPillSegment(`距当前价 ${distancePct >= 0 ? '+' : ''}${distancePct.toFixed(2)}%`, 'seg-muted'));
        }
        if (Number(item.quantity) > 0) pill.appendChild(createPillSegment(formatCryptoValue(item.quantity), 'seg-qty'));
    } else if (isEntry) {
        // 挂单行：缺保护时的放置徽标 | 限价卖出开空 | 数量 | ✕
        if (!hasProtective('tp')) pill.appendChild(buildProtectivePlacementChip(item, 'tp'));
        if (!hasProtective('sl')) pill.appendChild(buildProtectivePlacementChip(item, 'sl'));
        if (item.order) pill.appendChild(createPillSegment(describeCryptoPendingOrder(item.order), 'seg-strong'));
        if (Number(item.quantity) > 0) pill.appendChild(createPillSegment(formatCryptoValue(item.quantity), 'seg-qty'));
    }

    if (isTp || isSl || isEntry) {
        const closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'pill-close';
        closeBtn.textContent = '✕';
        closeBtn.title = '撤销这张单';
        closeBtn.addEventListener('pointerdown', (event) => event.stopPropagation());
        closeBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            dismissTradeLinePill(item);
        });
        pill.appendChild(closeBtn);
    }

    // 按住浮层本体 = 拖动改价：直接复用既有的挂单拖拽状态机（chart 上的 move/up 处理器会接手）
    if (item.orderId || item.isPlaceholder) {
        pill.addEventListener('pointerdown', (event) => {
            if (event.button !== 0 || event.target?.classList?.contains('pill-chip')) return;
            event.preventDefault();
            event.stopPropagation();
            try { chartEl.setPointerCapture(event.pointerId); } catch (error) {}
            currentDraggedTradeLine = {
                item: item,
                pointerId: event.pointerId,
                startPrice: item.price,
                tempPrice: item.price,
            };
            document.body.classList.add('chart-dragging-order');
        });
    }

    pill.style.display = 'none';
    chartEl.appendChild(pill);
    item.pillEl = pill;
    activeTradeLinePills.push(pill);
}

function positionChartTradeLinePills() {
    if (typeof document === 'undefined' || !document) return;
    const chartEl = document.getElementById('chart');
    if (!chartEl || !candlestickSeries || !activeChartTradePriceLines.length) return;
    const width = chartEl.clientWidth;
    const height = chartEl.clientHeight;
    let scaleWidth = 0;
    try { scaleWidth = chart.priceScale('right')?.width?.() || 0; } catch (error) { scaleWidth = 0; }
    activeChartTradePriceLines.forEach((item) => {
        const pill = item.pillEl;
        if (!pill) return;
        const coordinate = candlestickSeries.priceToCoordinate(item.price);
        if (coordinate === null || coordinate === undefined || !Number.isFinite(coordinate)) {
            pill.style.display = 'none';
            return;
        }
        pill.style.display = 'flex';
        pill.style.top = `${Math.round(Math.max(11, Math.min(height - 11, coordinate)))}px`;
        pill.style.left = `${Math.max(0, Math.round(width - scaleWidth - (pill.offsetWidth || 150) - 8))}px`;
    });
}

function updateChartTradePriceLines() {
    clearChartTradePriceLines();
    if (typeof candlestickSeries === 'undefined' || !candlestickSeries || typeof isCryptoMode !== 'function' || !isCryptoMode() || typeof currentTraining === 'undefined' || !currentTraining?.id) return;
    initChartTradeLineDragging();
    // 换训练会话后，之前"本次不再显示"的占位线记录作废
    if (typeof suppressedProtectivePlaceholders !== 'undefined' && typeof suppressedPlaceholderContext !== 'undefined') {
        if (suppressedPlaceholderContext !== currentTraining.id) {
            suppressedPlaceholderContext = currentTraining.id;
            suppressedProtectivePlaceholders.clear();
        }
    }

    const position = currentTraining.position || {};
    const pendingOrders = Array.isArray(currentTraining.pending_orders) ? currentTraining.pending_orders : [];
    const side = String(position.side || 'flat');
    const quantity = Number(position.quantity || 0);
    const entryPrice = Number(position.entry_price || 0);

    const lineStyleSolid = (typeof LightweightCharts !== 'undefined' && LightweightCharts?.LineStyle?.Solid != null) ? LightweightCharts.LineStyle.Solid : 0;
    const lineStyleDashed = (typeof LightweightCharts !== 'undefined' && LightweightCharts?.LineStyle?.Dashed != null) ? LightweightCharts.LineStyle.Dashed : 2;
    const lineStyleDotted = (typeof LightweightCharts !== 'undefined' && LightweightCharts?.LineStyle?.Dotted != null) ? LightweightCharts.LineStyle.Dotted : 1;

    // 1. 主图持仓均价线 (Position Entry Price Line)
    if (side !== 'flat' && quantity > 0 && entryPrice > 0) {
        const isLong = side === 'long';
        const lineColor = isLong ? '#2196f3' : '#f6465d';

        try {
            const posLine = candlestickSeries.createPriceLine({
                price: entryPrice,
                color: lineColor,
                lineWidth: 2,
                lineStyle: lineStyleSolid,
                axisLabelVisible: true,
                title: '',
            });
            activeChartTradePriceLines.push({
                line: posLine,
                type: 'position',
                price: entryPrice,
                side: side,
                quantity: quantity,
                entryPrice: entryPrice,
            });
        } catch (e) {
            console.warn('创建持仓均价线失败:', e);
        }
    }

    // 2. 挂单价格线（止盈 TP、止损 SL、限价 Limit、突破 Breakout）
    const actionMap = { open_long: '买入', open_short: '卖出', close: '平仓' };
    const drawnPrices = new Set();

    pendingOrders.forEach((order) => {
        if (!order || order.status === 'filled' || order.status === 'cancelled') return;
        const isProtective = !!order.parent_order_id;
        let isTp = isProtective && order.protection_type === 'tp';
        let isSl = isProtective && order.protection_type === 'sl';
        const price = Number(order.limit_price ?? order.trigger_price ?? 0);
        if (!Number.isFinite(price) || price <= 0) return;

        // 手工挂出的平仓单（从图上拖出来的止盈/止损）没有 protection_type，
        // 角色以订单类型为准：平仓限价=止盈、平仓突破=止损（引擎对两者的撮合条件不同）。
        // 只有类型也不明确时才退化为"按成本价上下侧"判断——注意不能用标记价判断，
        // 否则持仓浮盈时"高于成本价的止损"会被误标成止盈。
        if (order.action === 'close' && !isTp && !isSl) {
            if (order.order_type === 'breakout') isSl = true;
            else if (order.order_type === 'limit') isTp = true;
            else if (entryPrice > 0) {
                const isLongPosition = side === 'long';
                const isAboveEntry = price >= entryPrice;
                if (isLongPosition ? isAboveEntry : !isAboveEntry) isTp = true;
                else isSl = true;
            }
        }

        let lineColor = '#848e9c';
        let lineStyle = lineStyleDashed;
        let title = '';

        // AICoin 观感：线上一律不写文字（信息全部在右侧浮层 + 轴上的价格框里）
        if (isTp) {
            lineColor = CHART_TP_COLOR;
        } else if (isSl) {
            lineColor = CHART_SL_COLOR;
        } else {
            lineColor = order.order_type === 'breakout' ? '#f0b90b' : '#2962ff';
        }

        try {
            const orderLine = candlestickSeries.createPriceLine({
                price: price,
                color: lineColor,
                lineWidth: 1,
                lineStyle: lineStyle,
                axisLabelVisible: true,
                title: title,
            });
            activeChartTradePriceLines.push({
                line: orderLine,
                orderId: order.order_id,
                order: order,
                type: isTp ? 'tp' : isSl ? 'sl' : 'limit',
                price: price,
                side: order.side,
                quantity: Number(order.quantity || 0),
                entryPrice: entryPrice,
            });
            drawnPrices.add(price);
        } catch (e) {
            console.warn('创建挂单价格线失败:', e);
        }
    });

    // 3. 兜底持仓保护价（若 pendingOrders 中未体现但 position 有独立 tp/sl 属性）
    //    这些线没有 orderId（无法改单），标记为占位线：拖动它们会按新价创建一张真实平仓单。
    const protective = getCryptoProtectivePrices(pendingOrders);
    const tpPrice = Number(protective.tp || position.tp_price || 0);
    const slPrice = Number(protective.sl || position.sl_price || 0);
    if (tpPrice > 0 && !drawnPrices.has(tpPrice)) {
        try {
            const tpLine = candlestickSeries.createPriceLine({
                price: tpPrice,
                color: CHART_TP_COLOR,
                lineWidth: 1,
                lineStyle: lineStyleDashed,
                axisLabelVisible: true,
                title: '',
            });
            activeChartTradePriceLines.push({
                line: tpLine,
                type: 'tp',
                price: tpPrice,
                side: side,
                quantity: quantity,
                entryPrice: entryPrice,
                isPlaceholder: true,
            });
        } catch (e) {}
    }
    if (slPrice > 0 && !drawnPrices.has(slPrice)) {
        try {
            const slLine = candlestickSeries.createPriceLine({
                price: slPrice,
                color: CHART_SL_COLOR,
                lineWidth: 1,
                lineStyle: lineStyleDashed,
                axisLabelVisible: true,
                title: '',
            });
            activeChartTradePriceLines.push({
                line: slLine,
                type: 'sl',
                price: slPrice,
                side: side,
                quantity: quantity,
                entryPrice: entryPrice,
                isPlaceholder: true,
            });
        } catch (e) {}
    }

    // 3.5 持仓/挂单尚未设置止盈止损时，**不再凭空画虚线占位线**（用户反馈那样很误导：
    //     "我没设置为什么会有止盈止损线"）。改由浮层上的「止盈 / 止损」徽标提供入口，
    //     按住拖动即放置，见 buildProtectivePlacementChip()。

    // 4. 强平价线 (Liquidation Price Line / 爆仓线) - 与止损线明显区分（警戒深红 + 虚线/点线 + 骷髅标识）
    const liquidationPrice = Number(position.liquidation_price || 0);
    if (side !== 'flat' && quantity > 0 && liquidationPrice > 0 && !drawnPrices.has(liquidationPrice)) {
        try {
            const liqLine = candlestickSeries.createPriceLine({
                price: liquidationPrice,
                color: '#d50000',
                lineWidth: 2,
                lineStyle: lineStyleDotted,
                axisLabelVisible: true,
                title: '💀 强平 (Liq): ' + formatCryptoValue(liquidationPrice) + ' [爆仓线]',
            });
            activeChartTradePriceLines.push({
                line: liqLine,
                type: 'liquidation',
                price: liquidationPrice,
                side: side,
                quantity: quantity,
                entryPrice: entryPrice,
            });
            drawnPrices.add(liquidationPrice);
        } catch (e) {
            console.warn('创建强平价格线失败:', e);
        }
    }

    // 5. AICoin 风格浮层：持仓线 / 挂单线 / 止盈止损线各贴一枚右侧浮层，
    //    按住浮层即可拖动改价（复用上面已绑定的挂单拖拽状态机）
    activeChartTradePriceLines.forEach((item) => {
        if (item.type === 'liquidation') return;
        buildChartTradeLinePill(item);
    });
    positionChartTradeLinePills();
}

// ===== AiCoin 风格持仓卡片 =====
function getCryptoProtectivePrices(pendingOrders) {
    let tp = 0;
    let sl = 0;
    (Array.isArray(pendingOrders) ? pendingOrders : []).forEach((order) => {
        if (!order || order.action !== 'close') return;
        const price = Number(order.limit_price ?? order.trigger_price ?? order.tp_price ?? order.sl_price ?? 0);
        if (!(price > 0)) return;
        // 角色以类型为准：平仓限价 = 止盈、平仓突破 = 止损（显式保护子单看 protection_type）。
        // 这样图上手工拖出来的保护单也能出现在持仓卡片的「止盈 / 止损」一行里。
        const isTp = order.protection_type ? order.protection_type === 'tp' : order.order_type === 'limit';
        const isSl = order.protection_type ? order.protection_type === 'sl' : order.order_type === 'breakout';
        if (isTp && !tp) tp = price;
        if (isSl && !sl) sl = price;
    });
    return { tp, sl };
}

function renderCryptoPositionCard(account, position, pendingOrders) {
    const container = document.getElementById('current-positions');
    if (!container) return;
    const side = String(position?.side || 'flat');
    if (side === 'flat' || !Number(position?.quantity)) {
        container.innerHTML = '<div class="no-positions">暂无持仓</div>';
        return;
    }
    const isLong = side === 'long';
    const symbol = currentTraining?.symbol || 'USDT永续';
    const coin = String(symbol).replace(/USDT$/i, '') || '币';
    const leverage = Number(position?.leverage || 1);
    const quantity = Number(position?.quantity || 0);
    const entryPrice = Number(position?.entry_price || 0);
    const markPrice = Number(account?.mark_price ?? position?.mark_price ?? 0);
    const margin = Number(position?.isolated_margin || 0);
    const unrealized = Number(position?.unrealized_pnl || 0);
    const pnlPercent = margin > 0 ? (unrealized / margin) * 100 : null;
    const marginRatio = account?.margin_ratio == null ? null : Number(account.margin_ratio) * 100;
    const liquidation = Number(position?.liquidation_price || 0);
    const protective = getCryptoProtectivePrices(pendingOrders);
    const pnlClass = unrealized >= 0 ? 'positive' : 'negative';
    const marginModeText = position?.margin_mode === 'isolated' ? '逐仓' : '全仓';

    container.innerHTML = '<div class="crypto-pos-card">'
        + '<div class="crypto-pos-card-header">'
        + '<div class="crypto-pos-tags-wrap">'
        + '<span class="crypto-pos-symbol">' + escapeHtml(symbol) + '</span>'
        + '<span class="crypto-pos-side ' + (isLong ? 'long' : 'short') + '">' + (isLong ? '做多' : '做空') + '</span>'
        + '<span class="crypto-pos-tag">' + marginModeText + '</span>'
        + '<span class="crypto-pos-tag">' + leverage + 'x</span>'
        + '</div>'
        + '<strong class="crypto-pos-pnl ' + pnlClass + '">' + (unrealized >= 0 ? '+' : '') + formatCryptoValue(unrealized, 2) + ' USDT'
        + (pnlPercent === null ? '' : ' (' + (pnlPercent >= 0 ? '+' : '') + pnlPercent.toFixed(2) + '%)') + '</strong>'
        + '</div>'
        + '<div class="crypto-pos-grid">'
        + '<div><span>开仓均价</span><strong>' + formatCryptoValue(entryPrice) + '</strong></div>'
        + '<div><span>标记价格</span><strong>' + formatCryptoValue(markPrice) + '</strong></div>'
        + '<div><span>持仓数量</span><strong>' + formatCryptoValue(quantity) + ' ' + escapeHtml(coin) + '</strong></div>'
        + '<div><span>持仓保证金</span><strong>' + formatCryptoValue(margin, 2) + ' USDT</strong></div>'
        + '<div><span>预估强平价</span><strong style="color: #ff3b30; font-weight: 700;">' + (liquidation > 0 ? formatCryptoValue(liquidation) : '0.00 (全仓安全)') + '</strong></div>'
        + '<div><span>止盈 / 止损</span><strong>' + (protective.tp > 0 ? formatCryptoValue(protective.tp) : '--') + ' / ' + (protective.sl > 0 ? formatCryptoValue(protective.sl) : '--') + '</strong></div>'
        + '</div>'
        + '<div class="crypto-pos-actions">'
        + '<button type="button" data-crypto-pos-action="tpsl" class="btn-pos-action">止盈止损</button>'
        + '<button type="button" data-crypto-pos-action="close" class="btn-pos-action">平仓</button>'
        + '<button type="button" data-crypto-pos-action="close-all" class="btn-pos-action btn-pos-close-all">市价全平</button>'
        + '</div>'
        + '</div>';

    container.querySelector('[data-crypto-pos-action="tpsl"]')?.addEventListener('click', focusCryptoTpSlPanel);
    container.querySelector('[data-crypto-pos-action="close"]')?.addEventListener('click', () => {
        selectCryptoOrderAction('close');
        setCryptoOrderType('market', { preservePrice: true });
        setCryptoOrderStatus('已切换为市价平仓，可修改后提交。', 'success');
    });
    container.querySelector('[data-crypto-pos-action="close-all"]')?.addEventListener('click', cryptoMarketCloseAll);
}

function focusCryptoTpSlPanel() {
    const checkbox = document.getElementById('crypto-tpsl-enabled');
    if (checkbox && !checkbox.checked) {
        checkbox.checked = true;
        document.getElementById('crypto-tpsl-fields')?.classList.remove('hidden');
    }
    document.querySelector('.order-console-section .crypto-tpsl-section')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    document.getElementById('crypto-tp-price')?.focus({ preventScroll: true });
}

async function cryptoMarketCloseAll() {
    if (!currentTraining?.id || !isCryptoMode() || cryptoOrderSubmitting) return;
    const side = String(currentTraining?.position?.side || 'flat');
    if (side === 'flat') {
        setCryptoOrderStatus('当前没有可平仓的持仓。', 'error');
        return;
    }
    cryptoOrderSubmitting = true;
    setCryptoOrderStatus('正在提交市价全平…', 'loading');
    try {
        const body = {
            action: 'close',
            order_type: 'market',
            margin: 0,
            leverage: Number(currentTraining?.position?.leverage || currentTraining?.leverage || 1),
        };
        const response = await fetch(API_BASE + '/training/' + encodeURIComponent(currentTraining.id) + '/trade', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.message || payload.error || getCryptoOrderErrorMessage(payload));
        if (payload.trade_markers) syncActiveTradeMarkers(payload.trade_markers);
        if (payload.account || payload.position) renderCryptoAccount(payload);
        else await updateAccountInfo();
        renderCryptoTradeHistory(payload.fills || []);
        setCryptoOrderStatus('市价全平已提交。', 'success');
    } catch (error) {
        setCryptoOrderStatus(error.message || '市价全平失败，请重试。', 'error');
    } finally {
        cryptoOrderSubmitting = false;
    }
}

function getCryptoCurrentPrice() {
    const account = currentTraining?.account || {};
    const position = currentTraining?.position || {};
    const latestBar = Array.isArray(latestRenderedKlineData) ? latestRenderedKlineData[latestRenderedKlineData.length - 1] : null;
    const price = Number(cryptoOrderConstraints?.current_price ?? account.mark_price ?? position.mark_price ?? latestBar?.close ?? 0);
    return Number.isFinite(price) && price > 0 ? price : 0;
}

function getCryptoPendingSide(action) {
    if (action === 'open_long') return 'buy';
    if (action === 'open_short') return 'sell';
    const positionSide = String(currentTraining?.position?.side || '').toLowerCase();
    if (positionSide === 'long') return 'sell';
    if (positionSide === 'short') return 'buy';
    return '';
}

function getCryptoRequiredPriceDirection(orderType, action) {
    const side = getCryptoPendingSide(action);
    if (!side || orderType === 'market') return '';
    if (orderType === 'limit') return side === 'buy' ? 'below' : 'above';
    return side === 'buy' ? 'above' : 'below';
}

function formatCryptoValue(value, maximumDigits = 8) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '--';
    return number.toLocaleString(undefined, { maximumFractionDigits: maximumDigits });
}

function formatCryptoInputPrice(value) {
    const number = Number(value);
    if (!Number.isFinite(number) || number <= 0) return '';
    const digits = number >= 1000 ? 2 : number >= 1 ? 4 : 8;
    return number.toFixed(digits).replace(/\.?0+$/, '');
}

function floorCryptoQuantity(quantity, step) {
    if (!Number.isFinite(quantity) || quantity <= 0) return 0;
    if (!Number.isFinite(step) || step <= 0) return quantity;
    return Math.floor((quantity + Number.EPSILON) / step) * step;
}

function validateCryptoPendingPrice(orderType, action, price, currentPrice) {
    if (orderType === 'market') return '';
    if (!Number.isFinite(price) || price <= 0) return orderType === 'limit' ? '请输入有效的限价。' : '请输入有效的突破触发价。';
    if (!Number.isFinite(currentPrice) || currentPrice <= 0) return '暂时无法取得标记价格，请刷新账户后重试。';
    // 平仓保护单：限价 = 止盈（只能挂在不会立即成交的一侧），突破 = 止损（价格穿越才触发）。
    // 挂错一侧的话，撮合会在下一根 K 线立刻成交（= 静默市价平仓），必须拦下来。
    if (action === 'close') {
        const closeSide = getCryptoPendingSide(action);
        if (!closeSide) return '当前没有可平仓的持仓。';
        const isLongPosition = closeSide === 'sell';
        if (orderType === 'limit') {
            if (isLongPosition && price <= currentPrice) {
                return '平多限价必须高于当前标记价，否则会立即成交；低于标记价的止损请改用突破单。';
            }
            if (!isLongPosition && price >= currentPrice) {
                return '平空限价必须低于当前标记价，否则会立即成交；高于标记价的止损请改用突破单。';
            }
            return '';
        }
        if (isLongPosition && price >= currentPrice) return '平多止损触发价必须低于当前标记价。';
        if (!isLongPosition && price <= currentPrice) return '平空止损触发价必须高于当前标记价。';
        return '';
    }
    const direction = getCryptoRequiredPriceDirection(orderType, action);
    if (!direction) return '当前没有可平仓的持仓。';
    if (direction === 'below' && price >= currentPrice) {
        return orderType === 'limit' ? '该方向限价必须低于当前标记价格。' : '该方向突破价必须低于当前标记价格。';
    }
    if (direction === 'above' && price <= currentPrice) {
        return orderType === 'limit' ? '该方向限价必须高于当前标记价格。' : '该方向突破价必须高于当前标记价格。';
    }
    return '';
}

function validateCryptoTpSl(action, entryPrice, tpPrice, slPrice) {
    if (action === 'close' || !document.getElementById('crypto-tpsl-enabled')?.checked) return '';
    if (!Number.isFinite(entryPrice) || entryPrice <= 0) return '请先填写有效的开仓价格，再设置止盈止损。';
    const hasTp = Number.isFinite(tpPrice) && tpPrice > 0;
    const hasSl = Number.isFinite(slPrice) && slPrice > 0;
    if (!hasTp && !hasSl) return '已开启止盈止损，请至少填写一个价格。';
    if (action === 'open_long') {
        if (hasTp && tpPrice <= entryPrice) return '开多止盈价必须高于预计开仓价。';
        if (hasSl && slPrice >= entryPrice) return '开多止损价必须低于预计开仓价。';
    } else {
        if (hasTp && tpPrice >= entryPrice) return '开空止盈价必须低于预计开仓价。';
        if (hasSl && slPrice <= entryPrice) return '开空止损价必须高于预计开仓价。';
    }
    return '';
}

function getCryptoOrderPreview() {
    const orderType = document.getElementById('crypto-order-type')?.value || 'market';
    const action = document.getElementById('crypto-order-action')?.value || 'open_long';
    const leverage = Math.max(1, Number(document.getElementById('crypto-order-leverage')?.value || currentTraining?.leverage || 1));
    const margin = Number(document.getElementById('crypto-margin')?.value || 0);
    const currentPrice = getCryptoCurrentPrice();
    const pendingPrice = Number(document.getElementById('crypto-limit-price')?.value || 0);
    const entryPrice = orderType === 'market' ? currentPrice : pendingPrice;
    const step = Number(cryptoOrderConstraints?.quantity_step || 0);
    const positionQuantity = Math.abs(Number(currentCryptoSummary?.position?.quantity ?? currentTraining?.position?.quantity ?? currentTraining?.account?.position?.quantity ?? 0));
    const positionMargin = Number(currentCryptoSummary?.position?.isolated_margin ?? currentTraining?.position?.isolated_margin ?? currentTraining?.account?.position?.isolated_margin ?? 0);
    let quantity = 0;
    if (action === 'close') {
        if (positionQuantity > 0) {
            if (positionMargin > 0 && margin > 0 && margin < positionMargin) {
                const ratio = Math.min(1, margin / positionMargin);
                quantity = floorCryptoQuantity(positionQuantity * ratio, step);
                if (quantity <= 0) quantity = positionQuantity;
            } else {
                quantity = positionQuantity;
            }
        }
    } else {
        quantity = floorCryptoQuantity((margin * leverage) / entryPrice, step);
    }
    const feeRate = Number(orderType === 'limit' ? cryptoOrderConstraints?.maker_fee_rate : cryptoOrderConstraints?.taker_fee_rate) || 0;
    const notional = quantity * entryPrice;
    return { orderType, action, leverage, margin, currentPrice, entryPrice, quantity, notional, feeRate, fee: notional * feeRate };
}

function refreshCryptoOrderPreview() {
    const preview = getCryptoOrderPreview();
    const minimumQuantity = Number(cryptoOrderConstraints?.min_quantity || 0);
    const minimumNotional = Number(cryptoOrderConstraints?.min_notional || 0);
    const quantityEl = document.getElementById('crypto-estimated-quantity');
    const feeEl = document.getElementById('crypto-estimated-fee');
    const minQuantityEl = document.getElementById('crypto-min-quantity');
    const minNotionalEl = document.getElementById('crypto-min-notional');
    const entryEl = document.getElementById('crypto-estimated-entry-price');
    if (quantityEl) quantityEl.textContent = preview.quantity > 0 ? formatCryptoValue(preview.quantity) : '--';
    if (feeEl) feeEl.textContent = preview.fee > 0 ? formatCryptoValue(preview.fee, 4) + ' USDT' : '--';
    if (minQuantityEl) minQuantityEl.textContent = minimumQuantity > 0 ? formatCryptoValue(minimumQuantity) : '--';
    if (minNotionalEl) minNotionalEl.textContent = minimumNotional > 0 ? formatCryptoValue(minimumNotional) + ' USDT' : '--';
    if (entryEl) entryEl.textContent = preview.entryPrice > 0 ? formatCryptoValue(preview.entryPrice) + ' USDT' : '--';
    // 市价单的以损定仓开仓价跟随实时价（限价/突破单保持可编辑）
    syncCryptoRiskCalcEntryPrice();
    updateCryptoPriceShortcuts();
}

function updateCryptoPriceShortcuts() {
    const orderType = document.getElementById('crypto-order-type')?.value || 'market';
    const action = document.getElementById('crypto-order-action')?.value || 'open_long';
    const direction = getCryptoRequiredPriceDirection(orderType, action);
    const tools = document.getElementById('crypto-price-tools');
    tools?.classList.toggle('hidden', orderType === 'market');
    const rule = document.getElementById('crypto-price-rule');
    if (rule) {
        if (!direction) rule.textContent = '当前没有可平仓的持仓。';
        else rule.textContent = (orderType === 'limit' ? '限价' : '突破价') + '必须' + (direction === 'above' ? '高于' : '低于') + '当前标记价。';
    }
    const sign = direction === 'above' ? '+' : '-';
    document.querySelectorAll('[data-crypto-price-offset]').forEach((button) => {
        button.textContent = sign + (Number(button.dataset.cryptoPriceOffset || 0) * 100).toFixed(1).replace('.0', '') + '%';
        button.disabled = !direction || getCryptoCurrentPrice() <= 0;
    });
}

function applyCryptoPriceOffset(button) {
    const input = document.getElementById('crypto-limit-price');
    if (!input || !button) return;
    const orderType = document.getElementById('crypto-order-type')?.value || 'market';
    const action = document.getElementById('crypto-order-action')?.value || 'open_long';
    const direction = getCryptoRequiredPriceDirection(orderType, action);
    const currentPrice = getCryptoCurrentPrice();
    if (!direction || currentPrice <= 0) return;
    const offset = Number(button.dataset.cryptoPriceOffset || 0);
    input.value = formatCryptoInputPrice(currentPrice * (direction === 'above' ? 1 + offset : 1 - offset));
    refreshCryptoOrderPreview();
    refreshCryptoTpSlPnl();
    input.focus();
}

function renderCryptoPendingOrders(orders) {
    const container = document.getElementById('crypto-pending-orders');
    if (!container) return;
    const activeOrders = Array.isArray(orders) ? orders : [];
    container.classList.toggle('hidden', activeOrders.length === 0);
    if (activeOrders.length === 0) {
        container.innerHTML = '';
        return;
    }
    const typeMap = { market: '市价', limit: '限价', breakout: '突破' };
    const actionMap = { open_long: '开多', open_short: '开空', close: '平仓' };
    container.innerHTML = '<div class="crypto-pending-heading"><strong>当前挂单</strong><span>' + activeOrders.length + ' 笔</span></div>' + activeOrders.map((order) => {
        const isProtective = !!order.parent_order_id;
        const role = isProtective ? (order.protection_type === 'tp' ? '止盈' : '止损') : (actionMap[order.action] || order.action || '订单');
        const type = typeMap[order.order_type] || order.order_type || '--';
        const price = Number(order.limit_price ?? order.trigger_price ?? 0);
        const tp = Number(order.tp_price || 0);
        const sl = Number(order.sl_price || 0);
        const status = order.status === 'active' ? '等待触发' : (order.status || '--');
        return '<div class="pending-order-item crypto-pending-order' + (isProtective ? ' tpsl-order' : '') + '">' +
            '<div class="crypto-pending-order-main"><div class="crypto-pending-order-title"><strong>' + escapeHtml(role) + '</strong><span>' + escapeHtml(type) + '</span><em>' + escapeHtml(status) + '</em></div>' +
            '<div class="crypto-pending-order-grid"><span>价格 <b>' + (price > 0 ? escapeHtml(formatCryptoValue(price)) : '市价') + '</b></span><span>数量 <b>' + escapeHtml(formatCryptoValue(order.quantity || 0)) + '</b></span>' +
            '<span>TP <b>' + (tp > 0 ? escapeHtml(formatCryptoValue(tp)) : '--') + '</b></span><span>SL <b>' + (sl > 0 ? escapeHtml(formatCryptoValue(sl)) : '--') + '</b></span></div></div>' +
            '<div class="crypto-pending-order-actions"><button type="button" class="crypto-copy-order" data-order-id="' + escapeHtml(order.order_id || '') + '">复制参数</button>' +
            '<button type="button" class="crypto-cancel-order" data-order-id="' + escapeHtml(order.order_id || '') + '">撤单</button></div></div>';
    }).join('');
    container.querySelectorAll('.crypto-copy-order').forEach((button) => {
        button.addEventListener('click', () => copyCryptoOrderParameters(button.dataset.orderId));
    });
    container.querySelectorAll('.crypto-cancel-order').forEach((button) => {
        button.addEventListener('click', () => cancelPendingOrder(button.dataset.orderId));
    });
}

function copyCryptoOrderParameters(orderId) {
    const order = (currentTraining?.pending_orders || []).find((candidate) => candidate.order_id === orderId);
    if (!order) {
        setCryptoOrderStatus('挂单已变化，请刷新后重试。', 'error');
        return;
    }
    const action = order.parent_order_id ? 'close' : order.action;
    selectCryptoOrderAction(action || 'open_long');
    setCryptoOrderType(order.order_type || 'market', { preservePrice: true });
    const leverage = document.getElementById('crypto-order-leverage');
    const margin = document.getElementById('crypto-margin');
    const price = document.getElementById('crypto-limit-price');
    if (leverage && order.leverage) leverage.value = String(order.leverage);
    if (margin && !order.parent_order_id && Number(order.margin) > 0) margin.value = String(order.margin);
    if (price) price.value = formatCryptoInputPrice(order.limit_price ?? order.trigger_price ?? 0);
    const tp = document.getElementById('crypto-tp-price');
    const sl = document.getElementById('crypto-sl-price');
    const hasProtection = !order.parent_order_id && (Number(order.tp_price) > 0 || Number(order.sl_price) > 0);
    const checkbox = document.getElementById('crypto-tpsl-enabled');
    if (checkbox) checkbox.checked = hasProtection;
    document.getElementById('crypto-tpsl-fields')?.classList.toggle('hidden', !hasProtection);
    if (tp) tp.value = hasProtection && order.tp_price ? formatCryptoInputPrice(order.tp_price) : '';
    if (sl) sl.value = hasProtection && order.sl_price ? formatCryptoInputPrice(order.sl_price) : '';
    refreshCryptoOrderPreview();
    refreshCryptoTpSlPnl();
    setCryptoOrderStatus('参数已复制到订单表单，确认后再提交。', 'success');
}

function getCryptoMaxOpenMargin(orderType, leverage) {
    const action = document.getElementById('crypto-order-action')?.value || 'open_long';
    if (action === 'close') {
        const positionMargin = Number(currentCryptoSummary?.position?.isolated_margin ?? currentTraining?.position?.isolated_margin ?? currentTraining?.account?.position?.isolated_margin ?? 0);
        return Math.max(0, Math.floor(positionMargin * 100) / 100);
    }
    const constraints = cryptoOrderConstraints || currentTraining?.order_constraints || {};
    const account = currentTraining?.account || {};
    const normalizedType = ['market', 'limit', 'breakout'].includes(orderType) ? orderType : 'market';
    const normalizedLeverage = Math.max(1, Number(leverage || constraints.leverage || currentTraining?.leverage || 1));
    const configuredLeverage = Number(constraints.leverage || normalizedLeverage);
    const configuredMaximum = Number(
        normalizedType === 'limit' ? constraints.max_limit_margin :
            normalizedType === 'breakout' ? constraints.max_breakout_margin : constraints.max_market_margin
    );
    let maximum = configuredMaximum;
    if (!Number.isFinite(maximum) || normalizedLeverage !== configuredLeverage) {
        const available = Math.max(0, Number(account.available_balance ?? currentTraining?.available_balance ?? 0) - Number(constraints.reserved_margin || 0));
        const feeRate = Number(normalizedType === 'limit' ? constraints.maker_fee_rate : constraints.taker_fee_rate);
        maximum = Number.isFinite(feeRate) ? available / (1 + normalizedLeverage * feeRate) : available;
    }
    return Math.max(0, Math.floor((Number(maximum) || 0) * 100) / 100);
}

function applyCryptoMarginFraction(button) {
    const input = document.getElementById('crypto-margin');
    if (!input || !button) return;
    const orderType = document.getElementById('crypto-order-type')?.value || 'market';
    const leverage = Number(document.getElementById('crypto-order-leverage')?.value || currentTraining?.leverage || 1);
    const fraction = Number(button.dataset.cryptoMarginFraction || 0);
    const maximum = getCryptoMaxOpenMargin(orderType, leverage);
    input.value = (Math.floor(maximum * fraction * 100) / 100).toFixed(2);
    input.max = maximum.toFixed(2);
    document.querySelectorAll('[data-crypto-margin-fraction]').forEach((candidate) => {
        const active = candidate === button;
        candidate.classList.toggle('active', active);
        candidate.setAttribute('aria-pressed', String(active));
    });
    refreshCryptoOrderPreview();
    refreshCryptoTpSlPnl();
}

function refreshCryptoMarginFraction() {
    const activeButton = document.querySelector('[data-crypto-margin-fraction].active');
    if (activeButton) applyCryptoMarginFraction(activeButton);
}

function setCryptoOrderType(orderType, options) {
    options = options || {};
    const normalized = ['market', 'limit', 'breakout'].includes(orderType) ? orderType : 'market';
    const value = document.getElementById('crypto-order-type');
    const previous = value?.value || 'market';
    if (value) value.value = normalized;
    document.querySelectorAll('[data-crypto-order-type]').forEach((button) => {
        const active = button.dataset.cryptoOrderType === normalized;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
    });
    document.getElementById('crypto-limit-price-group')?.classList.toggle('hidden', normalized === 'market');
    const priceLabel = document.getElementById('crypto-limit-price-label');
    if (priceLabel) priceLabel.textContent = normalized === 'limit' ? '限价' : '触发价';
    const priceInput = document.getElementById('crypto-limit-price');
    if (priceInput && normalized !== 'market' && previous !== normalized && !options.preservePrice) priceInput.value = '';
    if (priceInput && normalized === 'market') priceInput.value = '';
    refreshCryptoMarginFraction();
    updateCryptoPriceShortcuts();
    refreshCryptoOrderPreview();
    refreshCryptoTpSlPnl();
}

function setCryptoOrderStatus(message, state = '') {
    const status = document.getElementById('crypto-order-status');
    if (!status) return;
    status.textContent = message || '';
    status.className = 'crypto-order-status' + (state ? ' ' + state : '');
}

function refreshCryptoTpSlPnl() {
    const tpPnlEl = document.getElementById('crypto-tp-pnl');
    const slPnlEl = document.getElementById('crypto-sl-pnl');
    if (!tpPnlEl || !slPnlEl) return;
    const enabled = document.getElementById('crypto-tpsl-enabled')?.checked;
    if (!enabled) { tpPnlEl.textContent = ''; slPnlEl.textContent = ''; return; }
    const bars = latestRenderedKlineData;
    if (!Array.isArray(bars) || bars.length === 0) { tpPnlEl.textContent = ''; slPnlEl.textContent = ''; return; }
    const currentPrice = Number(bars[bars.length - 1].close);
    if (!Number.isFinite(currentPrice) || currentPrice <= 0) { tpPnlEl.textContent = ''; slPnlEl.textContent = ''; return; }
    const margin = Number(document.getElementById('crypto-margin')?.value || 0);
    const leverage = Number(document.getElementById('crypto-order-leverage')?.value || 5);
    const action = document.getElementById('crypto-order-action')?.value || 'open_long';
    const isLong = action !== 'open_short';
    const quantity = (margin * leverage) / currentPrice;
    const tpPrice = Number(document.getElementById('crypto-tp-price')?.value || 0);
    const slPrice = Number(document.getElementById('crypto-sl-price')?.value || 0);
    if (Number.isFinite(tpPrice) && tpPrice > 0 && quantity > 0) {
        const pnl = isLong ? quantity * (tpPrice - currentPrice) : quantity * (currentPrice - tpPrice);
        tpPnlEl.textContent = (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + ' U';
        tpPnlEl.classList.toggle('positive', pnl >= 0);
        tpPnlEl.classList.toggle('negative', pnl < 0);
    } else {
        tpPnlEl.textContent = '';
    }
    if (Number.isFinite(slPrice) && slPrice > 0 && quantity > 0) {
        const pnl = isLong ? quantity * (slPrice - currentPrice) : quantity * (currentPrice - slPrice);
        slPnlEl.textContent = (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + ' U';
        slPnlEl.classList.toggle('positive', pnl >= 0);
        slPnlEl.classList.toggle('negative', pnl < 0);
    } else {
        slPnlEl.textContent = '';
    }
}

function resetCryptoTpSl() {
    const checkbox = document.getElementById('crypto-tpsl-enabled');
    if (checkbox) checkbox.checked = false;
    document.getElementById('crypto-tpsl-fields')?.classList.add('hidden');
    const tpInput = document.getElementById('crypto-tp-price');
    const slInput = document.getElementById('crypto-sl-price');
    if (tpInput) tpInput.value = '';
    if (slInput) slInput.value = '';
    refreshCryptoTpSlPnl();
}

// ===== 以损定仓（按最大亏损反推开仓数量） =====
function toggleCryptoRiskCalcFields() {
    const enabled = document.getElementById('crypto-riskcalc-enabled')?.checked;
    document.getElementById('crypto-riskcalc-fields')?.classList.toggle('hidden', !enabled);
    if (enabled) refreshCryptoRiskCalcResult();
}

function getCryptoRiskCalcParams() {
    const preview = getCryptoOrderPreview();
    const entryInput = Number(document.getElementById('crypto-riskcalc-entry')?.value || 0);
    const stopInput = Number(document.getElementById('crypto-riskcalc-stop')?.value || 0);
    const syncedStop = Number(document.getElementById('crypto-sl-price')?.value || 0);
    const action = preview.action === 'close' ? 'open_long' : preview.action;
    // 市价单的成交价就是下单瞬间的标记价，不存在"自己填的开仓价"。
    // 此前只要这个输入框被填过一次，那个旧价就会永远覆盖实时价，
    // 用户必须每次手动改一遍才能算对。
    const isMarketOrder = preview.orderType === 'market';
    return {
        entryPrice: isMarketOrder || !(entryInput > 0) ? preview.entryPrice : entryInput,
        stopPrice: stopInput > 0 ? stopInput : syncedStop,
        maxLoss: Number(document.getElementById('crypto-riskcalc-maxloss')?.value || 0),
        leverage: preview.leverage,
        action,
    };
}

/**
 * 市价单：以损定仓的「开仓价」跟随实时标记价并置为只读（成交价不由用户指定）；
 * 限价/突破单则恢复可编辑，由用户填预计成交价。
 */
function syncCryptoRiskCalcEntryPrice() {
    const entryEl = document.getElementById('crypto-riskcalc-entry');
    if (!entryEl) return;
    const orderType = document.getElementById('crypto-order-type')?.value || 'market';
    const isMarketOrder = orderType === 'market';
    entryEl.readOnly = isMarketOrder;
    entryEl.title = isMarketOrder
        ? '市价单按当前标记价成交，无需填写'
        : '限价/突破单：可填预计成交价';
    if (!isMarketOrder) return;
    const currentPrice = getCryptoCurrentPrice();
    if (!Number.isFinite(currentPrice) || currentPrice <= 0) return;
    const shown = Number(entryEl.value || 0);
    if (Math.abs(shown - currentPrice) > 1e-9) {
        entryEl.value = formatCryptoInputPrice(currentPrice);
        // 价格变了，按以损定仓反推的数量也要跟着刷新
        refreshCryptoRiskCalcResult();
    }
}

function refreshCryptoRiskCalcResult() {
    const resultEl = document.getElementById('crypto-riskcalc-result');
    if (!resultEl || !window.RiskCalc) return null;
    if (!document.getElementById('crypto-riskcalc-enabled')?.checked) return null;
    const params = getCryptoRiskCalcParams();
    const result = window.RiskCalc.computeRiskPosition(params);
    if (!result.valid) {
        resultEl.textContent = result.reason === 'stop-too-close'
            ? '开仓价与止损价不能相同，请检查价格。'
            : '填写开仓价（或计算价格）、止损价与最大亏损后自动计算。';
        return null;
    }
    const warning = result.directionOk ? '' : (params.action === 'open_short'
        ? '（注意：开空的止损价应高于开仓价）'
        : '（注意：开多的止损价应低于开仓价）');
    resultEl.textContent = '数量 ≈ ' + formatCryptoValue(result.quantity)
        + ' · 名义 ' + formatCryptoValue(result.notional, 2) + ' USDT'
        + ' · 保证金(' + result.leverage + 'x) ' + formatCryptoValue(result.margin, 2) + ' USDT'
        + ' · 止损幅度 ' + (result.stopRate * 100).toFixed(2) + '%'
        + ' · 触发止损时保证金亏损 ' + (result.marginLossRate * 100).toFixed(1) + '%'
        + warning;
    return result;
}

function applyCryptoRiskCalc() {
    const result = refreshCryptoRiskCalcResult();
    if (!result || !result.valid) return;
    const marginInput = document.getElementById('crypto-margin');
    if (marginInput) {
        marginInput.value = String(Number(result.margin.toFixed(4)));
        document.querySelectorAll('[data-crypto-margin-fraction]').forEach((button) => {
            button.classList.remove('active');
            button.setAttribute('aria-pressed', 'false');
        });
    }
    const stopInput = document.getElementById('crypto-riskcalc-stop');
    const slInput = document.getElementById('crypto-sl-price');
    if (stopInput && slInput && Number(stopInput.value) > 0 && !Number(slInput.value)) {
        slInput.value = stopInput.value;
        const tpslEnabled = document.getElementById('crypto-tpsl-enabled');
        if (tpslEnabled && !tpslEnabled.checked) {
            tpslEnabled.checked = true;
            document.getElementById('crypto-tpsl-fields')?.classList.remove('hidden');
        }
    }
    refreshCryptoOrderPreview();
    refreshCryptoTpSlPnl();
}

function getCryptoOrderErrorMessage(payload) {
    if (payload?.message) return payload.message;
    if (payload?.error) return payload.error;
    const messages = {
        invalid_action: '请选择有效的开仓或平仓方向。',
        invalid_order_type: '订单类型必须是市价、限价或突破。',
        invalid_limit_price: '请输入有效的限价。',
        missing_limit_price: '限价单必须填写限价。',
        invalid_trigger_price: '请输入有效的突破触发价。',
        missing_trigger_price: '突破单必须填写触发价。',
        invalid_limit_direction: '限价方向不正确，请按当前标记价重新设置。',
        invalid_trigger_direction: '突破方向不正确，请按当前标记价重新设置。',
        duplicate_pending_order: '该开仓方向已有挂单，请先撤单或等待成交。',
        min_quantity: '预计数量低于合约最低数量，请增加保证金或杠杆。',
        min_notional: '预计名义价值低于合约最低要求，请增加保证金。',
        insufficient_margin: '可用保证金不足，请降低保证金并预留手续费。',
        invalid_margin: '请输入有效的开仓保证金。',
        no_position: '当前没有可平仓的持仓。',
        leverage_locked: '存在持仓或挂单时不能修改杠杆。',
        invalid_tp_sl: '止盈止损价格不符合当前开仓方向。',
        invalid_order: '订单参数未通过校验，请检查价格、数量和止盈止损。',
    };
    return messages[payload?.code] || '合约订单提交失败，请检查参数后重试。';
}

async function submitCryptoOrder() {
    if (!currentTraining?.id || !isCryptoMode() || cryptoOrderSubmitting) return;
    const submitButton = document.getElementById('crypto-submit-order');
    const preview = getCryptoOrderPreview();
    const { orderType, action, leverage, margin, currentPrice, entryPrice, quantity, notional } = preview;
    if (action !== 'close') {
        const maximum = getCryptoMaxOpenMargin(orderType, leverage);
        if (!Number.isFinite(margin) || margin <= 0) {
            setCryptoOrderStatus('请输入有效的开仓保证金。', 'error');
            return;
        }
        if (margin > maximum) {
            setCryptoOrderStatus('保证金超过可用额度，请选择较小比例。', 'error');
            return;
        }
        const minimumQuantity = Number(cryptoOrderConstraints?.min_quantity || 0);
        const minimumNotional = Number(cryptoOrderConstraints?.min_notional || 0);
        if (minimumQuantity > 0 && quantity < minimumQuantity) {
            setCryptoOrderStatus('预计数量 ' + formatCryptoValue(quantity) + ' 低于最低数量 ' + formatCryptoValue(minimumQuantity) + '，请增加保证金或杠杆。', 'error');
            return;
        }
        if (minimumNotional > 0 && notional < minimumNotional) {
            setCryptoOrderStatus('预计名义价值低于 ' + formatCryptoValue(minimumNotional) + ' USDT，请增加保证金。', 'error');
            return;
        }
    } else if (!getCryptoPendingSide(action)) {
        setCryptoOrderStatus('当前没有可平仓的持仓。', 'error');
        return;
    }
    // 平仓保护单：用户只管填价位，类型由价位自动判定（高于现价=止盈限价、低于现价=止损突破）。
    // 否则"平仓限价挂在现价下方"会被引擎当成可立即成交的单子，下一根 K 线就静默平仓。
    let submitOrderType = orderType;
    let autoTypeNote = '';
    if (action === 'close' && orderType !== 'market') {
        const closeSide = getCryptoPendingSide(action);
        if (!closeSide) {
            setCryptoOrderStatus('当前没有可平仓的持仓。', 'error');
            return;
        }
        submitOrderType = resolveCloseOrderType(entryPrice, currentPrice, closeSide);
        if (submitOrderType !== orderType) {
            autoTypeNote = submitOrderType === 'limit'
                ? '（已按价位自动选为限价止盈）'
                : '（已按价位自动选为突破止损）';
        }
    }
    const body = { action, order_type: submitOrderType, margin, leverage };
    if (action === 'close') {
        if (margin > 0) body.margin = margin;
        if (quantity > 0) body.quantity = quantity;
    }
    if (submitOrderType !== 'market') {
        const directionError = validateCryptoPendingPrice(submitOrderType, action, entryPrice, currentPrice);
        if (directionError) {
            setCryptoOrderStatus(directionError, 'error');
            return;
        }
        if (submitOrderType === 'limit') body.limit_price = entryPrice;
        else body.trigger_price = entryPrice;
    }
    if (action !== 'close' && document.getElementById('crypto-tpsl-enabled')?.checked) {
        const tpVal = Number(document.getElementById('crypto-tp-price')?.value || 0);
        const slVal = Number(document.getElementById('crypto-sl-price')?.value || 0);
        const protectionError = validateCryptoTpSl(action, entryPrice, tpVal, slVal);
        if (protectionError) {
            setCryptoOrderStatus(protectionError, 'error');
            return;
        }
        if (Number.isFinite(tpVal) && tpVal > 0) body.tp_price = tpVal;
        if (Number.isFinite(slVal) && slVal > 0) body.sl_price = slVal;
    }
    cryptoOrderSubmitting = true;
    if (submitButton) submitButton.disabled = true;
    setCryptoOrderStatus('正在提交订单…', 'loading');
    try {
        const response = await fetch(API_BASE + '/training/' + encodeURIComponent(currentTraining.id) + '/trade', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.message || payload.error || getCryptoOrderErrorMessage(payload));
        if (payload.trade_markers) syncActiveTradeMarkers(payload.trade_markers);
        if (payload.account || payload.position) renderCryptoAccount(payload);
        else await updateAccountInfo();
        renderCryptoTradeHistory(payload.fills || []);
        const submittedOrder = payload.order || {};
        const successMessage = orderType === 'market'
            ? (action === 'close' ? '市价平仓已提交。' : '市价开仓已提交。')
            : '挂单已提交，将从下一根已揭示 K 线开始检查。' + autoTypeNote;
        setCryptoOrderStatus(submittedOrder.status === 'filled' ? '订单已成交。' : successMessage, 'success');
        refreshCryptoMarginFraction();
        resetCryptoTpSl();
    } catch (error) {
        console.error('提交合约订单失败:', error);
        setCryptoOrderStatus(error.message || '合约订单提交失败', 'error');
    } finally {
        cryptoOrderSubmitting = false;
        if (submitButton) submitButton.disabled = false;
    }
}

async function updateAccountInfo() {
    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/account`);
        const account = await response.json();

        if (isCryptoMode()) {
            renderCryptoAccount(account);
            await updateTradeHistory();
            return;
        }

        document.getElementById('total-assets').textContent = `¥${account.total_assets.toLocaleString()}`;
        document.getElementById('available-cash').textContent = `¥${account.available_cash.toLocaleString()}`;
        document.getElementById('position-value').textContent = `¥${account.position_value.toLocaleString()}`;
        document.getElementById('floating-pnl').textContent = `¥${account.floating_pnl.toLocaleString()}`;
        document.getElementById('floating-pnl').style.color = account.floating_pnl > 0 ? getThemePalette().positive : account.floating_pnl < 0 ? getThemePalette().negative : getThemePalette().text;

        // 更新最大可交易数量
        document.getElementById('max-buy-quantity').textContent = account.max_buyable_quantity;
        document.getElementById('trade-quantity').max = account.max_buyable_quantity;
        if (account.position_summary) {
            let max_sell_qty = account.position_summary.available_shares / 100
            document.getElementById('max-sell-quantity').textContent = max_sell_qty;
            document.getElementById('sell-quantity').max = max_sell_qty;
        }
        else {
            document.getElementById('max-sell-quantity').textContent = '0';
            document.getElementById('sell-quantity').max = 0;
        }

        // 更新持仓信息
        limitTradeQuantity();
        limitSellQuantity();
        renderPendingOrders(account.pending_orders);
        updatePositionInfo(account.position_summary);

        // 同步拉取交易记录（解决 AI / 后台自动交易所缺失的面板历史记录）
        await updateTradeHistory();

    } catch (error) {
        console.error('更新账户信息失败:', error);
    }
}

// 获取并刷新整个交易历史列表
function renderCryptoTradeHistory(records) {
    const container = document.getElementById('crypto-trade-history');
    if (!container) return;
    if (!records || records.length === 0) {
        container.innerHTML = '<div class="no-trades">暂无合约成交</div>';
        return;
    }
    const actionLabels = {
        open_long: '开多',
        open_short: '开空',
        close: '平仓',
        liquidation: '强平',
    };
    container.innerHTML = records.slice().reverse().slice(0, 10).map((trade) => {
        const realized = Number(trade.realized_pnl || 0);
        return '<div class="trade-item ' + escapeHtml(trade.action || '') + '">' +
            '<div class="trade-header"><span class="trade-action">' +
            escapeHtml(actionLabels[trade.action] || trade.action || '-') +
            '</span><span class="trade-time">' + escapeHtml(trade.timestamp || '') + '</span></div>' +
            '<div class="trade-details"><div>数量: ' + Number(trade.quantity || 0).toLocaleString() + '</div>' +
            '<div>价格: ' + Number(trade.price || 0).toLocaleString() + ' USDT</div>' +
            '<div>手续费: ' + Number(trade.fee || 0).toFixed(4) + ' USDT</div>' +
            '<div class="' + (realized >= 0 ? 'positive' : 'negative') + '">已实现: ' +
            realized.toFixed(4) + ' USDT</div></div></div>';
    }).join('');
}

async function updateTradeHistory() {
    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/trade_records`);
        if (!response.ok) return;
        const records = await response.json();
        if (isCryptoMode()) {
            renderCryptoTradeHistory(records);
            return;
        }
        
        const container = document.getElementById('trade-history');
        if (!records || records.length === 0) {
            container.innerHTML = '<div class="no-trades">暂无交易记录</div>';
            return;
        }

        container.innerHTML = '';
        // 倒序排列，新的在上面
        const displayRecords = records.reverse().slice(0, 10);
        
        displayRecords.forEach(trade => {
            const tradeItem = document.createElement('div');
            tradeItem.className = `trade-item ${trade.action} clickable`;
            tradeItem.innerHTML = `
                <div class="trade-header">
                    <span class="trade-action">${trade.action === 'buy' ? '买入' : '卖出'}</span>
                    <span class="trade-time">${trade.trade_date}</span>
                </div>
                <div class="trade-details">
                    <div>Bar ID: ${trade.bar_id}</div>
                    <div>数量: ${trade.quantity} 手</div>
                    <div>价格: ¥${trade.price.toFixed(2)}</div>
                    <div>金额: ¥${trade.net_amount.toFixed(2)}</div>
                </div>
            `;
            tradeItem.addEventListener('click', () => showTradeReasonModal({
                ...trade,
                date: trade.trade_date
            }));
            container.appendChild(tradeItem);
        });
    } catch (e) {
        console.error('获取交易历史失败', e);
    }
}

// 自动同步状态
function startAutoSync() {
    // === intraday_30m 分支: /sync_status 由 legacy kline_processor 支持，
    // intraday 模式不具备该后端依赖，因此不启动后台轮询，避免反复 500 ===
    if (isIntradayMode()) {
        stopAutoSync();
        return;
    }
    if (autoSyncInterval) clearInterval(autoSyncInterval);
    lastKnownBarId = null;
    lastKnownTradeCount = null;

    autoSyncInterval = setInterval(async () => {
        if (!currentTraining || isPlaying) return;

        const isTrainingInterfaceVisible = !document.getElementById('training-interface').classList.contains('hidden');
        if (!isTrainingInterfaceVisible) return;

        try {
            const resp = await fetch(`${API_BASE}/training/${currentTraining.id}/sync_status`);
            if (resp.status === 404) {
                stopAutoSync();
                return;
            }
            if (resp.ok) {
                const data = await resp.json();
                let needsRefresh = false;

                if (lastKnownBarId !== null && data.current_bar_id !== lastKnownBarId) {
                    needsRefresh = true;
                }
                if (lastKnownTradeCount !== null && data.trade_markers_count !== lastKnownTradeCount) {
                    needsRefresh = true;
                }

                if (needsRefresh) {
                    await loadInitialData();
                }

                lastKnownBarId = data.current_bar_id;
                lastKnownTradeCount = data.trade_markers_count;
            }
        } catch (e) { }
    }, 500);
}

function stopAutoSync() {
    if (autoSyncInterval) {
        clearInterval(autoSyncInterval);
        autoSyncInterval = null;
    }
}

function updatePositionInfo(positionSummary) {
    if (isCryptoMode()) return;
    const container = document.getElementById('current-positions');

    if (!positionSummary || positionSummary.total_shares === 0) {
        container.innerHTML = '<div class="no-positions">暂无持仓</div>';
        return;
    }

    container.innerHTML = `
        <div class="position-summary">
            <div class="position-item">
                <span>总持股:</span>
                <span>${(positionSummary.total_shares / 100).toFixed(2).toLocaleString()} 手</span>
            </div>
            <div class="position-item">
                <span>可卖:</span>
                <span>${(positionSummary.available_shares / 100).toFixed(2).toLocaleString()} 手</span>
            </div>
            <div class="position-item">
                <span>成本价:</span>
                <span>¥${positionSummary.average_cost.toFixed(2)}</span>
            </div>
            <div class="position-item">
                <span>现价:</span>
                <span>¥${positionSummary.current_price.toFixed(2)}</span>
            </div>
            <div class="position-item">
                <span>盈亏:</span>
                <span class="${positionSummary.pnl_percent >= 0 ? 'positive' : 'negative'}">${positionSummary.pnl_percent.toFixed(2)}%</span>
            </div>
        </div>
    `;
}

function addTradeRecord(trade) {
    // 改为直接调用全量更新
    updateTradeHistory();
}

// 训练控制

/**
 * 强制平仓函数
 * 会持续尝试卖出所有持仓，直到持仓清空。
 * 如果当天有T+1限制，会自动进入下一天再尝试。
 * @returns {Promise<boolean>} - 返回一个Promise，成功清仓则resolve(true)，否则resolve(false)。
 */
async function forceLiquidatePosition() {
    console.log("开始执行强制平仓流程...");

    // 设置一个最大尝试天数，防止无限循环
    const maxAttempts = 10;
    let attempts = 0;

    while (attempts < maxAttempts) {
        try {
            // 1. 获取最新的账户信息
            const accountResponse = await fetch(`${API_BASE}/training/${currentTraining.id}/account`);
            if (!accountResponse.ok) {
                alert('强制平仓失败：无法获取账户信息。');
                return false;
            }
            const account = await accountResponse.json();

            const totalShares = account.position_summary?.total_shares || 0;
            const availableShares = account.position_summary?.available_shares || 0;

            // 2. 如果持仓已清空，则成功退出循环
            if (totalShares === 0) {
                console.log("持仓已全部清空。");
                return true;
            }

            // 3. 如果有可卖的股票，就卖掉它们
            if (availableShares > 0) {
                console.log(`检测到可卖持仓 ${availableShares} 股，正在执行卖出...`);
                const sellQuantity = Math.floor(availableShares / 100); // 转换为“手”

                const sellResponse = await fetch(`${API_BASE}/training/${currentTraining.id}/trade`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'sell', quantity: sellQuantity })
                });

                if (!sellResponse.ok) {
                    const error = await sellResponse.json();
                    alert(`强制卖出部分持仓失败: ${error.message}`);
                    return false;
                }

                const result = await sellResponse.json();
                updateAccountInfo();
                addTradeRecord(result.trade);
                syncActiveTradeMarkers(result.trade_markers);
                console.log(`成功卖出 ${sellQuantity} 手。`);

                // 卖出后再次检查，如果已经全部卖完，直接成功返回
                if (account.position_summary.total_shares - availableShares === 0) {
                    console.log("持仓已全部清空。");
                    return true;
                }
            }

            // 4. 如果还有持仓但当天不可卖，则进入下一天
            console.log("当天有T+1限制或已无更多可卖股票，进入下一个交易日...");
            await nextBar(); // 调用 nextBar 进入下一天

            // 增加一个小的延时，等待UI和后端状态更新
            await new Promise(resolve => setTimeout(resolve, 100));

        } catch (error) {
            console.error('强制平仓过程中发生错误:', error);
            alert('强制平仓过程中发生错误，请检查控制台。');
            return false;
        }
        attempts++;
    }

    alert('强制平仓失败：已超过最大尝试天数，仍有持仓未卖出。');
    return false;
}

async function endTraining() {
    if (isAshareLiveMode) {
        exitAshareLiveWatch();
        return;
    }
    // 1. 首先获取当前账户状态，检查是否有持仓
    const accountResponse = await fetch(`${API_BASE}/training/${currentTraining.id}/account`);
    if (!accountResponse.ok) {
        alert('无法获取账户信息，结束训练失败。');
        return;
    }
    const account = await accountResponse.json();
    const hasPosition = account.position_summary?.total_shares > 0;

    // 2. 如果有持仓，进行二次确认
    if (hasPosition) {
        if (!confirm('您当前仍有持仓，系统将自动为您强制平仓。确定要结束训练吗？')) {
            return; // 用户取消，则不执行任何操作
        }

        // 用户确认，开始强制平仓流程
        const liquidationSuccess = await forceLiquidatePosition();

        // 如果平仓失败，则中止结束流程
        if (!liquidationSuccess) {
            alert('自动平仓失败，无法结束训练。请手动处理或重置训练。');
            return;
        }
    }
    // 如果没有持仓，或者平仓成功后，继续执行原来的结束逻辑
    else {
        // 对于没有持仓的情况，也进行一次确认
        if (!confirm('确定要结束当前训练吗？')) {
            return;
        }
    }

    // 3. 所有持仓已清空，正式调用后端的 end 接口
    let response;
    try {
        console.log("所有持仓已清空，正在生成最终报告...");
        response = await fetch(`${API_BASE}/training/${currentTraining.id}/end`, {
            method: 'POST'
        });
    } catch (networkError) {
        console.error('结束训练请求失败:', networkError);
        alert(`结束训练失败：网络请求异常（${networkError.message || '无法连接服务器'}），请检查服务是否运行。`);
        return;
    }

    const rawText = await response.text();
    let payload = null;
    try {
        payload = rawText ? JSON.parse(rawText) : null;
    } catch (parseError) {
        console.error('结束训练返回非 JSON:', rawText?.slice(0, 500));
        alert(`结束训练失败：服务器返回异常（HTTP ${response.status}）。详细错误已输出到浏览器控制台（F12）。`);
        return;
    }

    if (!response.ok) {
        const message = payload?.error || payload?.message || `HTTP ${response.status}`;
        console.error('结束训练失败:', payload);
        alert(`结束训练失败：${message}`);
        return;
    }

    try {
        pausePlayback();
        clearSessionDrawings();
        clearCryptoPeriodSnapshotCache();
        showReport(payload);
    } catch (renderError) {
        console.error('结束成功但报告渲染失败:', renderError);
        alert(`训练已结束，但报告页面渲染失败：${renderError.message || renderError}。可刷新页面后从历史训练查看。`);
    }
}

async function resetTraining() {
    if (!confirm('确定要重置当前训练吗？所有交易记录将被清除。')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/reset`, {
            method: 'POST'
        });

        if (response.ok) {
            pausePlayback();
            clearSessionDrawings();
            clearCryptoPeriodSnapshotCache();

            // === intraday_30m 分支: reset 返回的 snapshot 位于 response.snapshot，
            // 重置后重新渲染并同步 active_period ===
            if (isIntradayMode()) {
                const data = await response.json();
                const snapshot = extractIntradaySnapshot(data);
                if (snapshot) {
                    applyIntradaySnapshot(snapshot, { fitContent: false });
                    await reloadChartWindowForPeriod(
                        snapshot.active_period || currentPeriod,
                        snapshot.current_time,
                        { replace: true, fitContent: true, successMessage: '训练已重置，历史上下文保持不变。' }
                    );
                }
                await updateAccountInfo();
                document.getElementById('trade-history').innerHTML = '<div class="no-trades">暂无交易记录</div>';
                return;
            }

            // === legacy_daily 分支 (原逻辑) ===
            await loadInitialData();

            // 清除交易记录显示
            document.getElementById('trade-history').innerHTML = '<div class="no-trades">暂无交易记录</div>';
        }
    } catch (error) {
        console.error('重置训练失败:', error);
        alert('重置训练失败');
    }
}

/**
 * 更新报告摘要区域的辅助函数
 * @param {HTMLElement} parentElement - 父容器元素
 * @param {object} report - 报告数据对象
 */
function updateReportSummary(parentElement, report) {
    const isCryptoReport = report.market_type === CRYPTO_MARKET_TYPE;
    const money = (value) => isCryptoReport
        ? Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' USDT'
        : '¥' + Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const dateRange = [report.start_date, report.end_date].filter(Boolean).join(' 至 ') || '-';
    const summaryItems = [
        [isCryptoReport ? '合约' : '股票代码', report.symbol || report.stock_code || '-'],
        ['训练期间', dateRange],
        ['初始资金', money(report.initial_capital)],
        ['最终资产', money(report.final_capital)],
        ['总交易次数', `${Number(report.total_trades || 0)} 次`],
        ['交易胜率', `${Number(report.trade_win_rate || 0).toFixed(2)}%`],
        ['总收益率', `${Number(report.total_return || 0).toFixed(2)}%`, Number(report.total_return || 0) >= 0 ? 'positive' : 'negative']
    ];

    parentElement.innerHTML = '<div class="summary-grid"></div>';
    const grid = parentElement.querySelector('.summary-grid');
    summaryItems.forEach(([label, value, state]) => {
        const item = document.createElement('div');
        item.className = 'summary-item';
        item.innerHTML = `<span class="label">${escapeHtml(label)}</span><span class="value ${state || ''}">${escapeHtml(value)}</span>`;
        grid.appendChild(item);
    });
}

/**
 * 创建并填充交易明细表格的辅助函数
 * @param {HTMLElement} parentElement - 父容器元素
 * @param {Array} tradeDetails - 交易明细数组
 */
function createTradeDetailsTable(parentElement, tradeDetails) {
    parentElement.innerHTML = `
        <h3>交易明细</h3>
        <div class="trade-details-table">
            <table>
                <thead>
                    <tr>
                        <th>Bar</th>
                        <th>日期</th>
                        <th>操作</th>
                        <th>价格</th>
                        <th>数量</th>
                        <th>金额</th>
                        <th>税费</th>
                        <th>净金额</th>
                    </tr>
                </thead>
                <tbody></tbody>
                <tfoot></tfoot>
            </table>
        </div>
    `;

    const tbody = parentElement.querySelector('tbody');
    const tfoot = parentElement.querySelector('tfoot');

    // 初始化合计数据
    const totals = {
        totalAmount: 0,
        totalCommission: 0,
        totalProfit: 0,
    };

    // 动态创建表格行
    tradeDetails.forEach(trade => {
        const row = tbody.insertRow(); // 创建新行

        row.className = 'clickable';
        const isBuy = trade.action === 'buy';
        const totalFee = trade.commission + trade.stamp_tax;
        const profit = isBuy ? -(trade.amount + totalFee) : (trade.amount - totalFee);

        // 填充单元格
        row.innerHTML = `
            <td>${trade.bar_id}</td>
            <td>${trade.date}</td>
            <td class="${trade.action}">${isBuy ? '买入' : '卖出'}</td>
            <td>¥${trade.price.toFixed(2)}</td>
            <td>${trade.quantity}</td>
            <td>${isBuy ? '-' : ''}¥${trade.amount.toFixed(2)}</td>
            <td>-¥${totalFee.toFixed(2)}</td>
            <td>${profit >= 0 ? '¥' : '-¥'}${Math.abs(profit).toFixed(2)}</td>
        `;

        // 累加合计值
        row.addEventListener('click', () => showTradeReasonModal(trade));
        if (!isBuy) {
            totals.totalAmount += trade.amount;
        }
        else {
            totals.totalAmount -= trade.amount;
        }
        totals.totalProfit += profit;
        totals.totalCommission += totalFee;
    });

    // 创建并插入合计行
    const totalRow = tfoot.insertRow();
    totalRow.className = 'total-row'; // 添加样式类以便高亮
    totalRow.innerHTML = `
        <td colspan="5"><strong>合计</strong></td>
        <td><strong>¥${totals.totalAmount.toFixed(2)}</strong></td>
        <td><strong>-¥${totals.totalCommission.toFixed(2)}</strong></td>
        <td><strong>${totals.totalProfit >= 0 ? '¥' : '-¥'}${Math.abs(totals.totalProfit).toFixed(2)}</strong></td>
    `;
}

function createCryptoTradeDetailsTable(parentElement, tradeDetails) {
    parentElement.innerHTML = '<h3>合约成交明细</h3><div class="trade-details-table"><table><thead><tr>' +
        '<th>时间</th><th>操作</th><th>价格</th><th>数量</th><th>手续费</th><th>已实现盈亏</th>' +
        '</tr></thead><tbody></tbody></table></div>';
    const labels = { open_long: '开多', open_short: '开空', close: '平仓', liquidation: '强平' };
    const tbody = parentElement.querySelector('tbody');
    (tradeDetails || []).forEach((trade) => {
        const row = tbody.insertRow();
        const realized = Number(trade.realized_pnl || 0);
        row.innerHTML = '<td>' + escapeHtml(trade.timestamp || '') + '</td>' +
            '<td>' + escapeHtml(labels[trade.action] || trade.action || '-') + '</td>' +
            '<td>' + Number(trade.price || 0).toLocaleString() + ' USDT</td>' +
            '<td>' + Number(trade.quantity || 0).toLocaleString() + '</td>' +
            '<td>' + Number(trade.fee || 0).toFixed(4) + ' USDT</td>' +
            '<td class="' + (realized >= 0 ? 'positive' : 'negative') + '">' + realized.toFixed(4) + ' USDT</td>';
    });
}


/**
 * 请求 AI 智能复盘点评
 */
async function requestAIAnalysis() {
    const aiBtn = document.getElementById('ai-analyze-btn');
    const originalText = aiBtn.innerHTML;
    
    try {
        aiBtn.disabled = true;
        aiBtn.innerHTML = '⏳ 正在请求AI分析，请稍候...';
        
        const response = await fetch(`${API_BASE}/training/analyze_report`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                report: currentReportData,
                user: currentUser
            })
        });

        if (response.ok) {
            const result = await response.json();
            
            // Render the AI commentary
            const reportContent = document.getElementById('report-content');
            
            // Check if section already exists
            let aiSection = document.querySelector('.ai-commentary-section');
            if (!aiSection) {
                aiSection = document.createElement('div');
                aiSection.className = 'ai-commentary-section';
                // Insert after summary but before details
                const detailsSection = document.querySelector('.trade-details-section');
                if (detailsSection) {
                    reportContent.insertBefore(aiSection, detailsSection);
                } else {
                    reportContent.appendChild(aiSection);
                }
            }
            
            // Format markdown using marked.js if available, otherwise simple formatting
            let formattedContent = '';
            if (typeof marked !== 'undefined') {
                formattedContent = marked.parse(result.ai_commentary);
            } else {
                formattedContent = result.ai_commentary.replace(/\n/g, '<br>');
            }
            
            aiSection.innerHTML = `
                <h3>🤖 AI 复盘点评</h3>
                <div class="ai-content">${formattedContent}</div>
            `;
            
            // Scroll to the AI section
            aiSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // Hide the button since we got the result
            aiBtn.classList.add('hidden');
        } else {
            const error = await response.json();
            alert(`AI 分析失败: ${error.error || '未知错误'}`);
        }
    } catch (error) {
        console.error('AI 分析请求失败:', error);
        alert('网络请求失败，请检查服务连接。');
    } finally {
        aiBtn.disabled = false;
        aiBtn.innerHTML = originalText;
    }
}

/**
 * 主函数：显示完整的报告界面
 * @param {object} report - 包含所有报告数据的对象
 */
function showReport(report) {
    if (!report.session_id && currentTraining?.id) {
        report.session_id = currentTraining.id;
    }
    // 保存当前报告数据供 AI 分析使用
    currentReportData = report;
    setTrainingViewOnlyMode(false, { showBackToReport: false });
    document.getElementById('history-dashboard')?.classList.add('hidden');
    
    // 切换界面可见性
    document.getElementById('training-interface').classList.add('hidden');
    const reportInterface = document.getElementById('report-interface');
    reportInterface.classList.remove('hidden');
    reportInterface.scrollTop = 0;

    // 恢复工具栏状态
    toggleToolbarForTraining(false);

    // 获取报告内容的容器
    const reportContent = document.getElementById('report-content');
    reportContent.innerHTML = ''; // 清空旧内容

    // 检查用户是否开启了 AI API
    checkAIStatusAndShowButton();

    // 创建并添加摘要和交易详情
    const summarySection = document.createElement('div');
    summarySection.className = 'report-summary';
    updateReportSummary(summarySection, report); // 使用辅助函数填充摘要

    const detailsSection = document.createElement('div');
    detailsSection.className = 'trade-details-section';
    if (report.market_type === CRYPTO_MARKET_TYPE) {
        createCryptoTradeDetailsTable(detailsSection, report.trade_details);
    } else {
        createTradeDetailsTable(detailsSection, report.trade_details);
    }

    // 将生成好的模块添加到主容器中
    reportContent.appendChild(summarySection);
    createReviewSummaryEditor(reportContent, report);

    reportContent.appendChild(detailsSection);

    // 更新用户统计
    loadUserStatistics();
}

/**
 * 检查AI状态并显示/隐藏AI分析按钮
 */
async function checkAIStatusAndShowButton() {
    const aiBtn = document.getElementById('ai-analyze-btn');
    if (!currentUser || !aiBtn) return;
    
    try {
        const response = await fetch(`${API_BASE}/users/${currentUser}/settings`);
        if (response.ok) {
            const settings = await response.json();
            if (settings.enable_ai_api) {
                aiBtn.classList.remove('hidden');
            } else {
                aiBtn.classList.add('hidden');
            }
        }
    } catch (e) {
        console.error('Failed to check AI status:', e);
    }
}

async function viewFullChart() {
    if (!currentReportData?.session_id) {
        alert('找不到已完成的历史训练记录，无法查看完整走势');
        return;
    }
    const trainingStart = currentReportData.training_start || currentReportData.start_date;
    const trainingEnd = currentReportData.training_end || currentReportData.end_date;
    if (!trainingStart || !trainingEnd) {
        alert('历史训练缺少走势图重建时间，无法查看完整走势');
        return;
    }

    const historySessionId = currentReportData.session_id;
    const requestedPeriod = CRYPTO_PERIODS.includes(currentReportData.period)
        ? currentReportData.period
        : (INTRADAY_PERIODS.includes(currentReportData.period) ? currentReportData.period : 'daily');
    const rangeStart = shiftChartWindowYear(trainingStart, -2);
    const rangeEnd = trainingEnd;

    stopAutoSync();
    pausePlayback();
    showLoading('正在加载历史复盘走势');
    try {
        document.getElementById('report-interface').classList.add('hidden');
        document.getElementById('training-interface').classList.remove('hidden');
        toggleToolbarForTraining(true);
        initializeChart();
        resetChartWindowState();
        chartWindowState = {
            ...createEmptyChartWindowState(),
            session_id: historySessionId,
            read_only: true,
            period: requestedPeriod,
            training_start: trainingStart,
            training_end: trainingEnd,
            window_start: rangeStart,
            window_end: rangeEnd,
        };
        updatePeriodBadge(requestedPeriod);
        setTrainingViewOnlyMode(true, { showBackToReport: true });
        updateChartWindowControls();
        setChartWindowStatus('正在加载训练前两年到训练结束的只读走势...', 'loading');

        await enqueueChartWindowRequest((requestGeneration) => requestChartWindow(rangeStart, rangeEnd, {
            period: requestedPeriod,
            requestGeneration,
            replace: true,
            fitContent: true,
            successMessage: '历史复盘走势已加载，可继续向前或向后查看。',
        }));
    } catch (error) {
        console.error('查看历史完整走势失败:', error);
        setChartWindowStatus(error.message || '获取历史完整走势数据失败。', 'error');
        alert(error.message || '获取历史完整走势数据失败');
    } finally {
        hideLoading();
    }
}

// 工具函数
function formatNumber(num) {
    return num.toLocaleString();
}

function formatCurrency(num) {
    return `¥${num.toLocaleString()}`;
}

function formatPercent(num) {
    return `${num.toFixed(2)}%`;
}

// ==========================================
// A股 1分钟实时看盘与 T+1 模拟下单交易系统
// ==========================================
let isAshareLiveMode = false;
// 进入 A股实时看盘前用户在回放训练中的副图/指标 UI 状态快照（launch 写入、exit 恢复后置 null）
let asharePreLiveUiState = null;

// ===== A股实时看盘 价格预警（AICoin 风格）=====
// 预警线只作用于实时看盘；按标的持久化，仅保存"仍生效且未触发"的项。
let ashareAlerts = [];
// alertId -> Lightweight Charts priceLine 句柄
let ashareAlertPriceLines = new Map();
// alertId -> 右侧可拖标签 DOM
let ashareAlertChipEls = new Map();
// 上一轮快照价：穿越判定必须用"上一价 → 当前价"，否则 3 秒轮询之间的跳空会漏报
let ashareAlertLastPrice = null;
// 「预警」按钮的落线模式（点击图区放置预警线）
let ashareAlertAdding = false;
let ashareAlertAudioCtx = null;
let ashareAlertChipDrag = null;
let ashareAlertChipFrame = null;
const ASHARE_ALERT_POPUP_TTL_MS = 12000;
const ASHARE_ALERT_TOAST_TTL_MS = 1800;
let currentAshareSymbol = '600519';
let currentAshareName = '贵州茅台';
let currentAsharePeriod = '1m';
let currentAsharePrice = 0;
let ashareLivePollTimer = null;
// A股实时看盘委托方式（买入/卖出各自独立记忆）：market = 市价即时成交；limit = 限价挂单
let ashareBuyOrderType = 'market';
let ashareSellOrderType = 'market';
// 各标的最近一次快照价（内存缓存，用于跨标的持仓盈亏展示；刷新后由行情重建）
const asharePriceCache = {};

function recordAshareLastPrice(symbol, price) {
    if (!symbol || !(Number(price) > 0)) return;
    asharePriceCache[symbol] = Number(price);
}

function getAshareLiveAccount() {
    let acc = null;
    try {
        const raw = localStorage.getItem('ashare_live_account_v1');
        if (raw) acc = JSON.parse(raw);
    } catch (e) {}
    if (!acc || typeof acc !== 'object') {
        acc = {
            cash: 100000,
            positions: {},
            trade_history: [],
            last_date: new Date().toISOString().slice(0, 10)
        };
    }
    // 统一补齐限价挂单相关字段（cash_frozen / pending_orders / frozen_sell / last_prices）
    acc = normalizeAshareAccountFields ? normalizeAshareAccountFields(acc) : acc;

    // T+1 跨日自动解冻：如果跨越了交易日/自然日，将上一交易日买入冻结股数自动转为可用；
    // 同时跨日的限价挂单在读取时即标记失效并退回冻结资金/持仓（撮合兜底在轮询内）
    const todayStr = new Date().toISOString().slice(0, 10);
    if (acc.last_date && acc.last_date !== todayStr) {
        let thawed = false;
        for (const sym in acc.positions) {
            const pos = acc.positions[sym];
            if (pos && pos.frozen_today > 0) {
                pos.frozen_today = 0;
                thawed = true;
            }
        }
        // 跨日挂单全部失效退冻结（与 matchLimitOrders 的 expired 语义一致，这里直接一次性清理）
        (acc.pending_orders || []).forEach((order) => {
            if (order.status !== 'open') return;
            if (order.side === 'buy') {
                const refund = Number(order.frozen_amount) || (Number(order.price) || 0) * (Number(order.shares) || 0);
                acc.cash += refund;
                acc.cash_frozen = Math.max(0, (Number(acc.cash_frozen) || 0) - refund);
            }
            else {
                const pos = (acc.positions || {})[order.code];
                if (pos) pos.frozen_sell = Math.max(0, (Number(pos.frozen_sell) || 0) - (Number(order.shares) || 0));
            }
            order.status = 'expired';
            thawed = true;
        });
        acc.last_date = todayStr;
        if (thawed) saveAshareLiveAccount(acc);
    } else if (!acc.last_date) {
        acc.last_date = todayStr;
    }
    return acc;
}

function saveAshareLiveAccount(acc) {
    try {
        localStorage.setItem('ashare_live_account_v1', JSON.stringify(acc));
        pushStateToBackend({ ashare_account: acc });
    } catch (e) {}
}

function findAsharePositionKey(acc, symbolOrCode) {
    if (!acc || !acc.positions) return null;
    const raw = String(symbolOrCode || currentAshareSymbol || '').trim();
    if (!raw) return null;
    if (acc.positions[raw]) return raw;
    const normCode = raw.replace(/^(sh|sz|bj)/i, '');
    if (acc.positions[normCode]) return normCode;
    const fullSym = normalizeAshareSymbol(raw);
    if (fullSym && acc.positions[fullSym]) return fullSym;
    return null;
}

function getAsharePosition(acc, symbolOrCode) {
    const key = findAsharePositionKey(acc, symbolOrCode);
    if (key && acc.positions[key]) return acc.positions[key];
    return { total_shares: 0, frozen_today: 0, frozen_sell: 0, avg_cost: 0 };
}

function formatAshareVolText(shares) {
    if (!shares || isNaN(shares)) return '--';
    const lots = shares / 100;
    if (lots >= 10000) return (lots / 10000).toFixed(2) + '万手';
    return Math.round(lots).toLocaleString() + '手';
}

function isAshareTradingHours() {
    const now = new Date();
    const day = now.getDay();
    if (day === 0 || day === 6) return false;
    const mins = now.getHours() * 60 + now.getMinutes();
    return (mins >= 9 * 60 + 30 && mins <= 11 * 60 + 30) || (mins >= 13 * 60 && mins <= 15 * 60);
}

function formatAshareSnapshotTime(timeStr) {
    if (!timeStr) return '--:--:--';
    const s = String(timeStr).trim();
    if (s.length === 14) {
        return `${s.slice(8, 10)}:${s.slice(10, 12)}:${s.slice(12, 14)}`;
    }
    if (s.length === 6) {
        return `${s.slice(0, 2)}:${s.slice(2, 4)}:${s.slice(4, 6)}`;
    }
    if (s.includes(' ')) {
        const parts = s.split(' ');
        return parts[1] || s;
    }
    return s;
}

function formatAshareTurnoverText(turnoverWan) {
    if (turnoverWan === undefined || turnoverWan === null || isNaN(turnoverWan)) return '--';
    const val = Number(turnoverWan);
    if (val >= 10000) {
        return `${(val / 10000).toFixed(2)}亿`;
    }
    return `${val.toFixed(0)}万`;
}

function getAshareMarketStatusText() {
    const now = new Date();
    const day = now.getDay();
    if (day === 0 || day === 6) return { text: '休市', isOpen: false };
    const mins = now.getHours() * 60 + now.getMinutes();
    if (mins >= 9 * 60 + 15 && mins < 9 * 60 + 30) {
        return { text: '集合竞价', isOpen: true };
    }
    if ((mins >= 9 * 60 + 30 && mins <= 11 * 60 + 30) || (mins >= 13 * 60 && mins <= 15 * 60)) {
        return { text: '盘中交易', isOpen: true };
    }
    if (mins > 11 * 60 + 30 && mins < 13 * 60) {
        return { text: '午间休市', isOpen: false };
    }
    return { text: '已收盘', isOpen: false };
}

function updateAshareHeaderTicker(snap) {
    if (!snap) return;
    // 1. 股票名称与代码
    const stockNameEl = document.getElementById('stock-name');
    if (stockNameEl && snap.name) {
        stockNameEl.textContent = `${snap.name} (${snap.code || ''})`;
    }

    // 2. 最新价格
    const curPriceEl = document.getElementById('current-price');
    const isUp = (snap.change || 0) >= 0;
    const priceColor = isUp ? 'var(--crypto-up, #eb4d5b)' : 'var(--crypto-down, #0ecb81)';
    if (curPriceEl && typeof snap.price === 'number' && snap.price > 0) {
        curPriceEl.textContent = snap.price.toFixed(2);
        curPriceEl.style.color = priceColor;
    }

    // 3. 涨跌额与百分比
    const changeEl = document.getElementById('ashare-header-change');
    if (changeEl) {
        const sign = isUp ? '+' : '';
        const chgVal = typeof snap.change === 'number' ? snap.change.toFixed(2) : '0.00';
        const chgPct = typeof snap.change_percent === 'number' ? snap.change_percent.toFixed(2) : '0.00';
        changeEl.textContent = `${sign}${chgVal} (${sign}${chgPct}%)`;
        changeEl.style.color = priceColor;
    }

    // 4. 交易状态
    const statusEl = document.getElementById('ashare-live-market-status');
    if (statusEl) {
        const statusInfo = getAshareMarketStatusText();
        statusEl.textContent = statusInfo.text;
        statusEl.classList.toggle('closed', !statusInfo.isOpen);
    }

    // 5. 格式化时间
    const curDateEl = document.getElementById('current-date');
    if (curDateEl) {
        curDateEl.textContent = formatAshareSnapshotTime(snap.time_str);
    }

    // 6. 关键统计指标 (高/低/开/昨收/量/额/振幅)
    const metricsStrip = document.getElementById('ashare-live-header-metrics');
    if (metricsStrip) {
        metricsStrip.classList.remove('hidden');
        const highEl = document.getElementById('ashare-live-metric-high');
        if (highEl) highEl.textContent = snap.high ? snap.high.toFixed(2) : '--';
        const lowEl = document.getElementById('ashare-live-metric-low');
        if (lowEl) lowEl.textContent = snap.low ? snap.low.toFixed(2) : '--';
        const openEl = document.getElementById('ashare-live-metric-open');
        if (openEl) openEl.textContent = snap.open ? snap.open.toFixed(2) : '--';
        const prevEl = document.getElementById('ashare-live-metric-prev');
        if (prevEl) prevEl.textContent = snap.prev_close ? snap.prev_close.toFixed(2) : '--';
        const volEl = document.getElementById('ashare-live-metric-vol');
        if (volEl) volEl.textContent = formatAshareVolText(snap.volume);
        const amtEl = document.getElementById('ashare-live-metric-amt');
        if (amtEl) amtEl.textContent = formatAshareTurnoverText(snap.turnover);
        const ampEl = document.getElementById('ashare-live-metric-amp');
        if (ampEl) {
            const amp = snap.amplitude !== undefined ? snap.amplitude : (snap.prev_close > 0 ? ((snap.high - snap.low) / snap.prev_close * 100) : null);
            ampEl.textContent = amp !== null && !isNaN(amp) ? `${Number(amp).toFixed(2)}%` : '--';
        }
    }

    // 兼容原有的回放条与副指标（若存在）
    const openEl = document.getElementById('crypto-open-price');
    if (openEl) openEl.textContent = snap.open ? snap.open.toFixed(2) : '--';
    const highEl = document.getElementById('crypto-high-price');
    if (highEl) highEl.textContent = snap.high ? snap.high.toFixed(2) : '--';
    const lowEl = document.getElementById('crypto-low-price');
    if (lowEl) lowEl.textContent = snap.low ? snap.low.toFixed(2) : '--';
    const closeEl = document.getElementById('crypto-close-price');
    if (closeEl) closeEl.textContent = snap.price ? snap.price.toFixed(2) : '--';
    const volEl = document.getElementById('crypto-volume');
    if (volEl) volEl.textContent = formatAshareVolText(snap.volume);
    const chgEl = document.getElementById('crypto-change-percent');
    if (chgEl) {
        const sign = isUp ? '+' : '';
        chgEl.textContent = `${sign}${(snap.change_percent || 0).toFixed(2)}%`;
        chgEl.style.color = priceColor;
    }
}

// ==========================================================================
// AICoin 风格 A 股自选/收藏股票 (Watchlist) 模块
// ==========================================================================
const DEFAULT_ASHARE_WATCHLIST = [
    { code: '600519', name: '贵州茅台', symbol: 'sh600519' },
    { code: '300750', name: '宁德时代', symbol: 'sz300750' },
    { code: '002594', name: '比亚迪', symbol: 'sz002594' },
    { code: '601318', name: '中国平安', symbol: 'sh601318' },
    { code: '300059', name: '东方财富', symbol: 'sz300059' },
    { code: '000001', name: '平安银行', symbol: 'sz000001' },
    { code: '600036', name: '招商银行', symbol: 'sh600036' },
    { code: '000858', name: '五粮液', symbol: 'sz000858' }
];

const ASHARE_INDEXES_WATCHLIST = [
    { code: '000001', name: '上证指数', symbol: 'sh000001', isIndex: true },
    { code: '399001', name: '深证成指', symbol: 'sz399001', isIndex: true },
    { code: '399006', name: '创业板指', symbol: 'sz399006', isIndex: true },
    { code: '000688', name: '科创50', symbol: 'sh000688', isIndex: true }
];

let currentAshareWlTab = 'custom'; // 'custom' | 'holding' | 'index'
let ashareWlSortField = null; // 'price' | 'change' | null
let ashareWlSortOrder = null; // 'desc' | 'asc' | null
let ashareWatchlistQuotes = {}; // code/symbol -> snapshot quote
let isAshareWlFetching = false;

function getAshareWatchlist() {
    try {
        const raw = localStorage.getItem('ashare_live_watchlist_v1');
        if (raw) {
            const list = JSON.parse(raw);
            if (Array.isArray(list) && list.length > 0) return list;
        }
    } catch (e) {
        console.warn('读取A股自选失败:', e);
    }
    return [...DEFAULT_ASHARE_WATCHLIST];
}

function saveAshareWatchlist(list) {
    try {
        localStorage.setItem('ashare_live_watchlist_v1', JSON.stringify(list));
        pushStateToBackend({ ashare_watchlist: list });
    } catch (e) {
        console.warn('保存A股自选失败:', e);
    }
}

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

function getAshareTabStocks() {
    if (currentAshareWlTab === 'custom') {
        return getAshareWatchlist();
    } else if (currentAshareWlTab === 'holding') {
        const acc = getAshareLiveAccount();
        const holdings = [];
        for (const sym in acc.positions) {
            const p = acc.positions[sym];
            if (p && p.total_shares > 0) {
                const normCode = String(p.code || sym || '').replace(/^(sh|sz|bj)/i, '');
                const fullSymbol = p.symbol || normalizeAshareSymbol(sym);
                holdings.push({
                    code: normCode,
                    name: p.name || sym,
                    symbol: fullSymbol,
                    shares: p.total_shares
                });
            }
        }
        return holdings;
    } else if (currentAshareWlTab === 'index') {
        return [...ASHARE_INDEXES_WATCHLIST];
    }
    return [];
}

function renderAshareWatchlist() {
    const listEl = document.getElementById('ashare-watchlist-items');
    if (!listEl) return;

    let stocks = getAshareTabStocks();

    // 排序逻辑
    if (ashareWlSortField) {
        stocks = [...stocks].sort((a, b) => {
            const qA = (a.symbol && ashareWatchlistQuotes[a.symbol]) || ashareWatchlistQuotes[a.code] || {};
            const qB = (b.symbol && ashareWatchlistQuotes[b.symbol]) || ashareWatchlistQuotes[b.code] || {};
            let valA = 0;
            let valB = 0;
            if (ashareWlSortField === 'price') {
                valA = qA.price || 0;
                valB = qB.price || 0;
            } else if (ashareWlSortField === 'change') {
                valA = qA.change_percent || 0;
                valB = qB.change_percent || 0;
            }
            if (ashareWlSortOrder === 'asc') return valA - valB;
            return valB - valA;
        });
    }

    if (stocks.length === 0) {
        let emptyTip = '暂无自选股票，点击下方按钮添加';
        if (currentAshareWlTab === 'holding') emptyTip = '当前账户暂无持仓股票';
        listEl.innerHTML = `<div class="ashare-wl-empty"><span>${emptyTip}</span></div>`;
        return;
    }

    const html = stocks.map(st => {
        const q = (st.symbol && ashareWatchlistQuotes[st.symbol]) || ashareWatchlistQuotes[st.code] || {};
        const price = q.price ? Number(q.price).toFixed(2) : '--';
        const changePercent = q.change_percent != null ? Number(q.change_percent) : null;
        let changeText = '--';
        let stateCls = 'flat';
        if (changePercent != null) {
            const sign = changePercent > 0 ? '+' : '';
            changeText = `${sign}${changePercent.toFixed(2)}%`;
            if (changePercent > 0) stateCls = 'up';
            else if (changePercent < 0) stateCls = 'down';
        }

        const curSym = String(currentAshareSymbol || '').trim().toLowerCase();
        const stSym = String(st.symbol || '').trim().toLowerCase();
        const stCode = String(st.code || '').trim().toLowerCase();
        const normCode = stCode.replace(/^(sh|sz|bj)/i, '');
        const normCurrent = curSym.replace(/^(sh|sz|bj)/i, '');
        let isActive = false;
        if (curSym.startsWith('sh') || curSym.startsWith('sz') || curSym.startsWith('bj')) {
            isActive = (stSym === curSym || (!st.isIndex && normCode === normCurrent));
        } else {
            isActive = (stCode === curSym || (stSym && stSym === curSym) || (normCode === normCurrent && !st.isIndex));
        }

        const tag = getAshareMarketTag(st.code, st.isIndex);
        const name = (st.isIndex ? st.name : (q.name || st.name)) || st.code;

        const removeBtn = (currentAshareWlTab === 'custom')
            ? `<button class="ashare-wl-remove-btn" data-code="${st.code}" title="从自选移除">×</button>`
            : '';

        return `
            <div class="ashare-wl-item ${isActive ? 'active' : ''}" data-symbol="${st.symbol || st.code}" data-code="${st.code}" data-name="${name}">
                <div class="ashare-wl-item-info">
                    <div class="ashare-wl-name-row">
                        <span class="ashare-wl-name">${name}</span>
                        <span class="ashare-wl-tag ${tag.cls}">${tag.text}</span>
                    </div>
                    <div class="ashare-wl-code">${st.code}</div>
                </div>
                <div class="ashare-wl-item-price ${stateCls}">
                    ${price}
                </div>
                <div class="ashare-wl-item-change">
                    <span class="ashare-wl-pill ${stateCls}">${changeText}</span>
                </div>
                ${removeBtn}
            </div>
        `;
    }).join('');

    listEl.innerHTML = html;

    // 绑定行点击与删除点击
    listEl.querySelectorAll('.ashare-wl-item').forEach(item => {
        item.addEventListener('click', (e) => {
            if (e.target.closest('.ashare-wl-remove-btn')) return;
            const sym = item.dataset.symbol || item.dataset.code;
            const name = item.dataset.name;
            selectAshareWatchlistStock(sym, name);
        });
    });

    listEl.querySelectorAll('.ashare-wl-remove-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            removeStockFromAshareWatchlist(btn.dataset.code);
        });
    });
}

async function selectAshareWatchlistStock(sym, name) {
    await switchAshareLiveStock(sym, name);
    renderAshareWatchlist();
}

async function fetchAshareWatchlistQuotes() {
    if (!isAshareLiveMode || isAshareWlFetching) return;
    isAshareWlFetching = true;
    try {
        const stocks = getAshareTabStocks();
        const syms = new Set(stocks.map(s => s.symbol || s.code));
        if (currentAshareSymbol) syms.add(currentAshareSymbol);
        if (syms.size === 0) return;

        const symList = Array.from(syms).join(',');
        const res = await fetch(`/api/ashare/live/batch?symbols=${encodeURIComponent(symList)}`);
        if (!res.ok) return;
        const data = await res.json();
        if (Array.isArray(data)) {
            data.forEach(item => {
                if (item.symbol) {
                    ashareWatchlistQuotes[item.symbol] = item;
                }
                // 指数（如上证指数 sh000001、科创50 sh000688）不要用纯代码覆盖字典，避免与个股（平安银行 000001、恒立实业 000688）冲突
                const isIndexCodeCollision = (item.symbol && item.symbol.startsWith('sh000'));
                if (!isIndexCodeCollision) {
                    ashareWatchlistQuotes[item.code] = item;
                }
                // 若匹配当前选中的标的，联动同步顶部现价
                const curSymLower = String(currentAshareSymbol || '').toLowerCase();
                const isCurrentMatched = (item.symbol && item.symbol.toLowerCase() === curSymLower)
                    || (item.code === currentAshareSymbol && !item.symbol?.startsWith('sh000'));
                if (isCurrentMatched) {
                    currentAsharePrice = item.price;
                    currentAshareName = item.name || currentAshareName;
                    const curPriceEl = document.getElementById('current-price');
                    if (curPriceEl && item.price > 0) {
                        const sign = item.change >= 0 ? '+' : '';
                        curPriceEl.textContent = `¥${item.price.toFixed(2)} (${sign}${item.change_percent.toFixed(2)}%)`;
                        curPriceEl.style.color = item.change >= 0 ? 'var(--crypto-up, #f6465d)' : 'var(--crypto-down, #0ecb81)';
                    }
                    const chgEl = document.getElementById('crypto-change-percent');
                    if (chgEl) {
                        const sign = item.change_percent >= 0 ? '+' : '';
                        chgEl.textContent = `${sign}${item.change_percent.toFixed(2)}%`;
                        chgEl.style.color = item.change >= 0 ? 'var(--crypto-up, #f6465d)' : 'var(--crypto-down, #0ecb81)';
                    }
                    const closeEl = document.getElementById('crypto-close-price');
                    if (closeEl) closeEl.textContent = item.price ? item.price.toFixed(2) : '--';
                }
            });
            renderAshareWatchlist();
        }
    } catch (e) {
        console.warn('获取自选股批量行情失败:', e);
    } finally {
        isAshareWlFetching = false;
    }
}

function addStockToAshareWatchlist(code, name, symbol) {
    const list = getAshareWatchlist();
    const normCode = String(code).replace(/^(sh|sz|bj)/i, '');
    const prefix = symbol ? symbol.slice(0, 2) : (code.startsWith('6') ? 'sh' : 'sz');
    const fullSym = symbol || `${prefix}${normCode}`;
    const exists = list.some(item => (item.symbol ? item.symbol === fullSym : String(item.code).replace(/^(sh|sz|bj)/i, '') === normCode));
    if (exists) return false;

    list.unshift({ code: normCode, name: name || normCode, symbol: fullSym });
    saveAshareWatchlist(list);
    renderAshareWatchlist();
    fetchAshareWatchlistQuotes();
    return true;
}

function removeStockFromAshareWatchlist(code) {
    let list = getAshareWatchlist();
    const normCode = String(code).replace(/^(sh|sz|bj)/i, '');
    list = list.filter(item => String(item.code).replace(/^(sh|sz|bj)/i, '') !== normCode);
    saveAshareWatchlist(list);
    renderAshareWatchlist();
}

function setAshareWatchlistTab(tab) {
    currentAshareWlTab = tab;
    document.querySelectorAll('.ashare-wl-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.wlTab === tab);
    });
    renderAshareWatchlist();
    fetchAshareWatchlistQuotes();
}

function toggleAshareWatchlistSort(field) {
    if (ashareWlSortField !== field) {
        ashareWlSortField = field;
        ashareWlSortOrder = 'desc';
    } else if (ashareWlSortOrder === 'desc') {
        ashareWlSortOrder = 'asc';
    } else {
        ashareWlSortField = null;
        ashareWlSortOrder = null;
    }

    // 更新表头箭头
    const priceArrow = document.querySelector('#ashare-wl-sort-price .sort-arrow');
    const changeArrow = document.querySelector('#ashare-wl-sort-change .sort-arrow');
    if (priceArrow) priceArrow.textContent = (ashareWlSortField === 'price') ? (ashareWlSortOrder === 'asc' ? '↑' : '↓') : '↕';
    if (changeArrow) changeArrow.textContent = (ashareWlSortField === 'change') ? (ashareWlSortOrder === 'asc' ? '↑' : '↓') : '↕';

    renderAshareWatchlist();
}

function collapseAshareWatchlist(collapsed) {
    const mainApp = document.getElementById('main-app');
    const expandBtn = document.getElementById('ashare-wl-expand-btn');
    if (collapsed) {
        mainApp?.classList.add('ashare-watchlist-collapsed');
        expandBtn?.classList.remove('hidden');
        localStorage.setItem('ashare_watchlist_collapsed', '1');
    } else {
        mainApp?.classList.remove('ashare-watchlist-collapsed');
        expandBtn?.classList.add('hidden');
        localStorage.setItem('ashare_watchlist_collapsed', '0');
    }
    requestAnimationFrame(resizeCharts);
}

// ===== 价格预警：存储 =====

function readAshareAlerts(symbol) {
    try {
        const raw = localStorage.getItem(priceAlertStorageKey(symbol));
        const parsed = raw ? JSON.parse(raw) : null;
        return normalizePriceAlertList(parsed, { symbol: symbol });
    } catch (error) {
        return [];
    }
}

function persistAshareAlerts() {
    const symbol = currentAshareSymbol || 'default';
    try {
        const persistable = selectPersistablePriceAlerts(ashareAlerts);
        if (!persistable.length) localStorage.removeItem(priceAlertStorageKey(symbol));
        else localStorage.setItem(priceAlertStorageKey(symbol), JSON.stringify(persistable));
    } catch (error) {
        // 存储不可用时静默降级为纯内存预警
    }
}

// ===== 价格预警：渲染 =====

function ashareAlertLineOptions(alert) {
    return {
        price: alert.price,
        color: alert.triggeredAt ? 'rgba(140, 148, 160, 0.8)' : '#f0a020',
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: false,
        title: '',
    };
}

function ensureAshareAlertPriceLine(alert) {
    if (!candlestickSeries) return;
    const options = ashareAlertLineOptions(alert);
    const existing = ashareAlertPriceLines.get(alert.id);
    if (existing) {
        try {
            existing.applyOptions(options);
        } catch (error) {
            // 图表已重建导致句柄失效：走下面的重建分支
            ashareAlertPriceLines.delete(alert.id);
        }
    }
    if (ashareAlertPriceLines.get(alert.id)) return;
    try {
        ashareAlertPriceLines.set(alert.id, candlestickSeries.createPriceLine(options));
    } catch (error) {
        // 忽略：价格线创建失败不影响预警判定
    }
}

function ensureAshareAlertChip(alert) {
    const container = document.getElementById('chart');
    if (!container) return null;
    let chip = ashareAlertChipEls.get(alert.id);
    if (!chip) {
        chip = document.createElement('div');
        chip.className = 'alert-chip';
        chip.dataset.alertId = alert.id;
        chip.innerHTML = '<span class="alert-chip-text"></span>'
            + '<button type="button" class="alert-chip-close" title="删除该预警">✕</button>'
            + '<span class="alert-chip-grip" title="上下拖动调整预警价位"></span>';
        // 预警标签自身不能把事件透回图表，否则点选/拖动会被当成落线或画线
        ['pointerdown', 'pointerup', 'click', 'dblclick'].forEach((type) => {
            chip.addEventListener(type, (event) => event.stopPropagation());
        });
        chip.querySelector('.alert-chip-close')?.addEventListener('click', (event) => {
            event.stopPropagation();
            removeAshareAlert(alert.id);
        });
        chip.querySelector('.alert-chip-grip')?.addEventListener('pointerdown', (event) => {
            event.stopPropagation();
            startAshareAlertChipDrag(event, alert.id);
        });
        container.appendChild(chip);
        ashareAlertChipEls.set(alert.id, chip);
    }
    chip.classList.toggle('is-triggered', Boolean(alert.triggeredAt));
    const label = formatPriceAlertLabel(alert);
    const textEl = chip.querySelector('.alert-chip-text');
    if (textEl) textEl.textContent = alert.triggeredAt ? `${label} · 已触发` : label;
    return chip;
}

function positionAshareAlertChips() {
    const chartEl = document.getElementById('chart');
    if (!chartEl || !chart || !candlestickSeries) return;
    const width = chartEl.clientWidth;
    const height = chartEl.clientHeight;
    let scaleWidth = 0;
    try {
        scaleWidth = chart.priceScale('right')?.width?.() || 0;
    } catch (error) {
        scaleWidth = 0;
    }
    ashareAlerts.forEach((alert) => {
        const chip = ashareAlertChipEls.get(alert.id);
        if (!chip) return;
        const coordinate = candlestickSeries.priceToCoordinate(alert.price);
        if (coordinate === null || coordinate === undefined || !Number.isFinite(coordinate)) {
            chip.style.display = 'none';
            return;
        }
        chip.style.display = 'flex';
        chip.style.top = `${Math.round(Math.max(10, Math.min(height - 10, coordinate)))}px`;
        const chipWidth = chip.offsetWidth || 120;
        chip.style.left = `${Math.max(0, Math.round(width - scaleWidth - chipWidth - 8))}px`;
    });
}

/** 图表 DOM 覆盖层（A股预警标签 + 币圈价格线药丸）的统一重定位调度 */
function scheduleAshareAlertChipsUpdate() {
    if ((!ashareAlerts.length && !activeTradeLinePills.length) || ashareAlertChipFrame) return;
    ashareAlertChipFrame = window.requestAnimationFrame(() => {
        ashareAlertChipFrame = null;
        positionAshareAlertChips();
        positionChartTradeLinePills();
    });
}

function renderAshareAlerts() {
    const keepIds = new Set(ashareAlerts.map((alert) => alert.id));
    Array.from(ashareAlertChipEls.keys()).forEach((id) => {
        if (keepIds.has(id)) return;
        ashareAlertChipEls.get(id)?.remove();
        ashareAlertChipEls.delete(id);
    });
    Array.from(ashareAlertPriceLines.keys()).forEach((id) => {
        if (keepIds.has(id)) return;
        const line = ashareAlertPriceLines.get(id);
        try {
            candlestickSeries?.removePriceLine?.(line);
        } catch (error) {
            // 图表已重建，句柄随之失效
        }
        ashareAlertPriceLines.delete(id);
    });
    ashareAlerts.forEach((alert) => {
        ensureAshareAlertPriceLine(alert);
        ensureAshareAlertChip(alert);
    });
    positionAshareAlertChips();
}

function clearAshareAlertVisuals() {
    ashareAlertChipEls.forEach((chip) => chip.remove());
    ashareAlertChipEls.clear();
    ashareAlertPriceLines.forEach((line) => {
        try {
            candlestickSeries?.removePriceLine?.(line);
        } catch (error) {
            // 图表已重建，忽略
        }
    });
    ashareAlertPriceLines.clear();
    ashareAlerts = [];
    ashareAlertLastPrice = null;
    setAshareAlertAddMode(false);
}

/** 进入看盘 / 换股：装载该标的的预警；首个 tick 只记录基准价，避免瞬间误报 */
function loadAshareAlertsForSymbol(symbol) {
    clearAshareAlertVisuals();
    ashareAlerts = readAshareAlerts(symbol || currentAshareSymbol);
    renderAshareAlerts();
}

// ===== 价格预警：增删改 =====

function createAshareAlert(price) {
    if (!isAshareLiveMode) return null;
    const symbol = currentAshareSymbol || 'default';
    const reference = Number.isFinite(currentAsharePrice) && currentAsharePrice > 0 ? currentAsharePrice : price;
    const alert = normalizePriceAlert({
        symbol: symbol,
        price: price,
        direction: derivePriceAlertDirection(price, reference),
        enabled: true,
        createdAt: Date.now(),
    }, { symbol: symbol, referencePrice: reference });
    if (!alert) {
        showAshareToast('未取到有效价位，请在图区内重新落线', 'warning');
        return null;
    }
    ashareAlerts.push(alert);
    persistAshareAlerts();
    renderAshareAlerts();
    showAshareToast('添加成功');
    requestAshareAlertNotifyPermission();
    return alert;
}

function removeAshareAlert(id) {
    const index = ashareAlerts.findIndex((alert) => alert.id === id);
    if (index < 0) return;
    ashareAlerts.splice(index, 1);
    const line = ashareAlertPriceLines.get(id);
    if (line) {
        try {
            candlestickSeries?.removePriceLine?.(line);
        } catch (error) {
            // 忽略
        }
        ashareAlertPriceLines.delete(id);
    }
    ashareAlertChipEls.get(id)?.remove();
    ashareAlertChipEls.delete(id);
    persistAshareAlerts();
    renderAshareAlerts();
}

function ashareAlertPriceFromClientY(clientY, rect) {
    if (!candlestickSeries || !rect || !rect.height) return null;
    const y = clientY - rect.top;
    if (!Number.isFinite(y)) return null;
    let price = null;
    try {
        price = candlestickSeries.coordinateToPrice(y);
    } catch (error) {
        return null;
    }
    if (price === null || price === undefined || !Number.isFinite(price)) return null;
    return normalizePriceAlertPrice(price);
}

function startAshareAlertChipDrag(event, alertId) {
    if (event.button !== undefined && event.button !== 0) return;
    const alert = ashareAlerts.find((item) => item.id === alertId);
    const chartEl = document.getElementById('chart');
    if (!alert || !chartEl || !candlestickSeries) return;
    if (typeof event.preventDefault === 'function') event.preventDefault();
    ashareAlertChipDrag = { alertId: alert.id, rect: chartEl.getBoundingClientRect() };

    const onMove = (moveEvent) => {
        if (!ashareAlertChipDrag) return;
        const price = ashareAlertPriceFromClientY(moveEvent.clientY, ashareAlertChipDrag.rect);
        if (price === null) return;
        alert.price = price;
        ensureAshareAlertPriceLine(alert);
        const chip = ashareAlertChipEls.get(alert.id);
        const textEl = chip?.querySelector('.alert-chip-text');
        if (textEl) textEl.textContent = formatPriceAlertLabel(alert);
        positionAshareAlertChips();
    };
    const onUp = () => {
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
        ashareAlertChipDrag = null;
        // 松手后按当前现价重推方向：拖到现价上方 = 涨至，下方 = 跌至
        const reference = Number.isFinite(currentAsharePrice) && currentAsharePrice > 0
            ? currentAsharePrice
            : alert.price;
        alert.direction = derivePriceAlertDirection(alert.price, reference);
        persistAshareAlerts();
        renderAshareAlerts();
    };
    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
}

// ===== 价格预警：落线模式 =====

function setAshareAlertAddMode(active) {
    ashareAlertAdding = Boolean(active);
    const btn = document.getElementById('alert-add-btn');
    if (btn) {
        btn.classList.toggle('is-adding', ashareAlertAdding);
        btn.setAttribute('aria-pressed', String(ashareAlertAdding));
    }
    document.querySelector('.chart-container')?.classList.toggle('alert-adding', ashareAlertAdding);
    if (ashareAlertAdding) {
        // 落线期间让绘图工具回到"选择"态，避免与画线手势抢指针
        drawingController?.activateTool?.('select');
        setDrawingStatus('预警落线：在图上点一下放置预警线，Esc 取消', 'active');
        requestAshareAlertNotifyPermission();
    } else {
        setDrawingStatus('');
    }
}

function toggleAshareAlertAddMode() {
    if (!isAshareLiveMode) return;
    setAshareAlertAddMode(!ashareAlertAdding);
}

function bindAshareAlertChartHandlers() {
    const chartEl = document.getElementById('chart');
    if (!chartEl || chartEl.dataset.alertBound === '1') return;
    chartEl.dataset.alertBound = '1';
    chartEl.addEventListener('pointerup', (event) => {
        if (!ashareAlertAdding || !isAshareLiveMode) return;
        if (event.button !== undefined && event.button !== 0) return;
        const price = ashareAlertPriceFromClientY(event.clientY, chartEl.getBoundingClientRect());
        if (price === null) {
            showAshareToast('未取到有效价位，请在图区内重试', 'warning');
            return;
        }
        createAshareAlert(price);
        setAshareAlertAddMode(false);
    });
}

// ===== 价格预警：触发提醒（弹窗 + 提示音 + 系统通知）=====

function ashareAlertPopupStack() {
    let stack = document.getElementById('alert-popup-stack');
    if (!stack) {
        stack = document.createElement('div');
        stack.id = 'alert-popup-stack';
        stack.className = 'alert-popup-stack';
        (document.querySelector('.chart-container') || document.body).appendChild(stack);
    }
    return stack;
}

function showAshareAlertPopup(title, html) {
    const stack = ashareAlertPopupStack();
    const popup = document.createElement('div');
    popup.className = 'alert-popup';
    popup.innerHTML = '<div class="alert-popup-head"><span>' + escapeHtml(title) + '</span>'
        + '<button type="button" class="alert-popup-close" title="关闭">✕</button></div>'
        + '<div class="alert-popup-body">' + html + '</div>';
    const close = () => popup.remove();
    popup.querySelector('.alert-popup-close')?.addEventListener('click', close);
    stack.appendChild(popup);
    window.setTimeout(close, ASHARE_ALERT_POPUP_TTL_MS);
    return popup;
}

function ashareAlertToastStack() {
    let stack = document.getElementById('alert-toast-stack');
    if (!stack) {
        stack = document.createElement('div');
        stack.id = 'alert-toast-stack';
        stack.className = 'alert-toast-stack';
        (document.querySelector('.chart-container') || document.body).appendChild(stack);
    }
    return stack;
}

function showAshareToast(message, variant) {
    const stack = ashareAlertToastStack();
    const toast = document.createElement('div');
    toast.className = 'alert-toast' + (variant === 'warning' ? ' is-warning' : '');
    toast.innerHTML = '<span class="alert-toast-icon">' + (variant === 'warning' ? '!' : '✓') + '</span>'
        + '<span>' + escapeHtml(message) + '</span>';
    stack.appendChild(toast);
    window.setTimeout(() => toast.remove(), ASHARE_ALERT_TOAST_TTL_MS);
}

function playAshareAlertSound() {
    try {
        const AudioCtor = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtor) return;
        if (!ashareAlertAudioCtx) ashareAlertAudioCtx = new AudioCtor();
        const ctx = ashareAlertAudioCtx;
        if (ctx.state === 'suspended') ctx.resume();
        const start = ctx.currentTime;
        [880, 1180].forEach((frequency, index) => {
            const at = start + index * 0.18;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.value = frequency;
            gain.gain.setValueAtTime(0.0001, at);
            gain.gain.exponentialRampToValueAtTime(0.22, at + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.16);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(at);
            osc.stop(at + 0.18);
        });
    } catch (error) {
        // 音频不可用不影响预警本身
    }
}

function requestAshareAlertNotifyPermission() {
    try {
        if (typeof Notification === 'undefined') return;
        if (Notification.permission === 'default') Notification.requestPermission()?.catch?.(() => {});
    } catch (error) {
        // 忽略：浏览器不支持或用户拒绝
    }
}

function sendAshareSystemNotification(title, body) {
    try {
        if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return;
        const notice = new Notification(title, { body: body, tag: 'kline-ashare-alert' });
        window.setTimeout(() => notice.close?.(), 15000);
    } catch (error) {
        // 忽略：系统通知不可用
    }
}

function fireAshareAlert(alert, triggerPrice) {
    const label = formatPriceAlertLabel(alert);
    const name = currentAshareName || alert.symbol;
    const timeText = formatPriceAlertTriggeredAt(alert.triggeredAt);
    const priceText = formatPriceAlertPrice(triggerPrice);
    showAshareAlertPopup(
        '价格预警触发',
        '<b>' + escapeHtml(name) + '</b> <span class="alert-popup-meta">' + escapeHtml(alert.symbol) + '</span><br>'
        + escapeHtml(label) + '　现价 <b>' + escapeHtml(priceText) + '</b>'
        + '<div class="alert-popup-meta">触发时间 ' + escapeHtml(timeText) + '</div>'
    );
    playAshareAlertSound();
    sendAshareSystemNotification(name + ' ' + label, '现价 ' + priceText + ' · ' + timeText);
}

/** 由 3 秒轮询驱动：只在价格"穿越"阈值时触发，触发即失效并留痕 */
function checkAshareAlerts(previousPrice, currentPrice) {
    if (!ashareAlerts.length) return;
    const triggered = findTriggeredPriceAlerts(ashareAlerts, previousPrice, currentPrice);
    if (!triggered.length) return;
    triggered.forEach((alert) => {
        alert.triggeredAt = Date.now();
        alert.enabled = false;
        fireAshareAlert(alert, currentPrice);
    });
    persistAshareAlerts();
    renderAshareAlerts();
}

// ===== 实时看盘：成交标记（把成交记录标回 K 线）=====

/** 取当前渲染的最后一根 K 线时间：下单瞬间记录，作为成交归属的 K 线 */
function currentAshareBarTime() {
    const bars = latestRenderedKlineData || [];
    for (let i = bars.length - 1; i >= 0; i--) {
        const time = Number(bars[i]?.time);
        if (Number.isFinite(time)) return time;
    }
    return null;
}

/**
 * 把一条成交记录映射到当前图表上的 K 线时间。
 * 1) 优先用成交瞬间记录的 bar_time —— 同周期下精确到具体 K 线（含分钟线）；
 * 2) 回退按「成交日期 + 时间」换算到图表时间域再对齐 —— 换周期后仍能落回当日/当周那根 K 线。
 */
function ashareTradeBarTime(record) {
    const bars = latestRenderedKlineData || [];
    if (!bars.length) return null;
    const recorded = Number(record?.bar_time);
    if (Number.isFinite(recorded) && bars.some((bar) => Number(bar.time) === recorded)) {
        return recorded;
    }
    const dateMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(record?.date || '').trim());
    if (!dateMatch) return null;
    const timeMatch = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/.exec(String(record?.time || '').trim());
    const secondsOfDay = timeMatch
        ? (Number(timeMatch[1]) * 3600) + (Number(timeMatch[2]) * 60) + Number(timeMatch[3] || 0)
        : 0;
    const tradeTimestamp = Date.UTC(Number(dateMatch[1]), Number(dateMatch[2]) - 1, Number(dateMatch[3])) / 1000 + secondsOfDay;
    const aligned = Number(alignTradeMarkerTimeToRenderedBar(tradeTimestamp));
    return bars.some((bar) => Number(bar.time) === aligned) ? aligned : null;
}

/**
 * 实时看盘：把本标的的成交记录渲染成 K 线上的买入/卖出标记。
 * 标记直接从持久化的成交记录推导，不额外存一份，天然随账户一起保存/恢复。
 */
function updateAshareLiveTradeMarkers() {
    if (!isAshareLiveMode || !tradeMarkerSeries) return;
    const acc = getAshareLiveAccount();
    const history = Array.isArray(acc.trade_history) ? acc.trade_history : [];
    const symbol = String(currentAshareSymbol || '').trim();
    const curCode = symbol.replace(/^(sh|sz|bj)/i, '').toLowerCase();
    const normCurSym = normalizeAshareSymbol(symbol);
    const markers = [];
    history.forEach((record) => {
        if (!record) return;
        // 兼容早期「限价成交」记录：只有 code、没有 symbol / date
        const recordSymbol = String(record.symbol || record.code || '').trim();
        const recCode = String(record.code || record.symbol || '').replace(/^(sh|sz|bj)/i, '').toLowerCase();
        const normRecSym = normalizeAshareSymbol(recordSymbol);
        const match = (recordSymbol.toLowerCase() === symbol.toLowerCase()) ||
                      (recCode && curCode && recCode === curCode) ||
                      (normRecSym && normCurSym && normRecSym === normCurSym);
        if (recordSymbol !== symbol && !match) return;
        const type = record.type === '买入' ? 'B' : (record.type === '卖出' ? 'S' : null);
        if (!type) return;
        const time = ashareTradeBarTime(record);
        if (time === null) return;
        // 买入：红色、箭头上、贴在 K 线下方；卖出：绿色、箭头下、贴在 K 线上方
        markers.push(type === 'B'
            ? { time: time, type: type, label: '买', position: 'belowBar', color: '#ff4d4f', shape: 'arrowUp' }
            : { time: time, type: type, label: '卖', position: 'aboveBar', color: '#008000', shape: 'arrowDown' });
    });
    markers.sort((a, b) => Number(a.time) - Number(b.time));
    updateTradeMarkers(markers);
}

/** 成交记录时间戳显示：MM-DD HH:MM:SS（历史记录只有时间没有日期，用户无法判断哪天买的） */
function formatAshareTradeStamp(record) {
    const date = String(record?.date || '').trim();
    const time = String(record?.time || '').trim();
    const shortDate = /^\d{4}-\d{2}-\d{2}$/.test(date) ? date.slice(5) : date;
    return [shortDate, time].filter(Boolean).join(' ');
}

/** 完整日期（挂 title，悬停可见） */
function formatAshareTradeStampFull(record) {
    const date = String(record?.date || '').trim();
    const time = String(record?.time || '').trim();
    return [date, time].filter(Boolean).join(' ') || '时间未记录';
}

async function launchAshareLiveWatch() {
    document.getElementById('training-setup')?.classList.add('hidden');
    isAshareLiveMode = true;
    currentAsharePeriod = '1D';
    
    // 1. 激活与 BTC 完全相同的视效模式、暗色主题与布局容器
    const mainApp = document.getElementById('main-app');
    mainApp?.classList.add('crypto-training-active', 'ashare-live-active');
    mainApp?.setAttribute('data-crypto-theme', currentCryptoTheme || 'dark');
    document.getElementById('training-interface')?.classList.add('crypto-workspace-active');
    applyCryptoTheme(currentCryptoTheme || 'dark', false, false);

    // 2. 隐藏主页、用户选择、报表视图
    document.getElementById('user-selection')?.classList.add('hidden');
    document.getElementById('history-dashboard')?.classList.add('hidden');
    document.getElementById('report-interface')?.classList.add('hidden');
    document.getElementById('training-interface')?.classList.remove('hidden');

    // 工具栏切换为紧凑模式
    toggleToolbarForTraining(true);

    // 3. 激活右侧 A 股专属模拟交易控制台
    // 注意：workspace-sidebar / training-setup / [data-crypto-workspace-only] /
    // [data-a-share-workspace-only] / [data-replay-only] 等元素的隐藏
    // 全部由 CSS `#main-app.ashare-live-active ...{ display:none !important }` 规则管理，
    // 此处严禁再用 classList.add('hidden') 重复隐藏——exitAshareLiveWatch 不会移除，
    // 残留 hidden 会导致退出后回到币圈训练时"当前持仓"等区块永久消失（历史 bug）。
    document.querySelectorAll('[data-ashare-live-only]').forEach(el => el.classList.remove('hidden'));
    document.querySelector('.trade-console')?.classList.remove('hidden');
    document.getElementById('crypto-console-splitter')?.classList.remove('hidden');
    document.getElementById('crypto-console-collapse-btn')?.classList.remove('hidden');
    document.getElementById('crypto-console-collapsed-tab')?.classList.remove('hidden');
    document.getElementById('crypto-theme-toggle-btn')?.classList.remove('hidden');
    updateThemeButton();
    applyCryptoConsoleLayout(readCryptoConsoleLayout());

    // 恢复自选股面板折叠状态
    const wlCollapsed = localStorage.getItem('ashare_watchlist_collapsed') === '1';
    collapseAshareWatchlist(wlCollapsed);

    // 显示 A 股特有控制控件（换股搜索、退出看盘及单行指标条）
    document.getElementById('ashare-live-search-btn')?.classList.remove('hidden');
    document.getElementById('ashare-live-exit-btn')?.classList.remove('hidden');
    document.getElementById('ashare-live-header-metrics')?.classList.remove('hidden');
    document.getElementById('ashare-header-change')?.classList.remove('hidden');
    document.getElementById('ashare-live-market-status')?.classList.remove('hidden');
    document.getElementById('ashare-live-status-badge')?.classList.add('hidden');
    document.getElementById('training-progress')?.classList.add('hidden');

    // 隐藏历史复盘播放条
    const playbackControls = document.querySelector('.playback-controls');
    if (playbackControls) playbackControls.classList.add('hidden');
    const speedControl = document.querySelector('.speed-control');
    if (speedControl) speedControl.classList.add('hidden');

    // 4. 周期按钮配置：按同花顺专业 A 股看盘标准呈现（日、周、月 | 1分、5分、15分、30分、60分、120分、240分）
    document.querySelectorAll('.crypto-view-period, .shared-view-period, .a-share-view-period, .crypto-view-separator').forEach(btn => btn.classList.add('hidden'));
    document.querySelectorAll('.ashare-live-period').forEach(btn => btn.classList.remove('hidden'));
    currentAsharePeriod = 'daily';
    document.querySelectorAll('.ashare-live-period.view-period-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === currentAsharePeriod);
    });

    updatePeriodBadge(currentAsharePeriod);

    // 5. 确保成交量与指标副图开启（与 BTC 截图一致：蜡烛 + 成交量 + MACD）
    // 耦合防护：进入前快照用户在回放训练中的副图/指标状态，exitAshareLiveWatch 时恢复，
    // 避免实时看盘覆盖共享 UI 状态后残留（历史 bug：退出后指标副图整体消失）。
    asharePreLiveUiState = {
        indicatorPanelVisible: indicatorPanelVisible,
        currentIndicatorType: currentIndicatorType,
        indicatorDisplay: document.getElementById('indicator-chart')?.style.display || '',
        volumeCollapsed: document.getElementById('volume-chart')?.classList.contains('panel-collapsed') || false,
        indicatorCollapsed: document.getElementById('indicator-chart')?.classList.contains('panel-collapsed') || false,
    };

    const volPanel = document.getElementById('volume-chart');
    if (volPanel) volPanel.classList.remove('panel-collapsed');
    const volBtn = document.getElementById('toggle-volume-panel-btn');
    if (volBtn) {
        volBtn.classList.add('active');
        volBtn.setAttribute('aria-expanded', 'true');
    }

    const indPanel = document.getElementById('indicator-chart');
    if (indPanel) {
        indPanel.classList.remove('panel-collapsed', 'indicator-collapsed');
        indPanel.style.removeProperty('display');
    }
    const indBtn = document.getElementById('toggle-indicator-panel-btn');
    if (indBtn) {
        indBtn.classList.add('active');
        indBtn.setAttribute('aria-expanded', 'true');
    }
    indicatorPanelVisible = true;
    currentIndicatorType = 'MACD';

    // 6. 初始化图表与画线系统并应用暗黑 AICoin 主题
    initializeChart();
    applyChartTheme();

    // 6.1 价格预警：绑定落线手势、显示「预警」按钮
    bindAshareAlertChartHandlers();
    document.getElementById('alert-add-btn')?.classList.remove('hidden');

    // 7. 渲染自选股面板、获取批量行情并初始化搜索功能
    renderAshareWatchlist();
    fetchAshareWatchlistQuotes();
    initAshareSearchModalEvents();

    // 8. 加载初始股票行情
    await loadAshareLiveData(currentAshareSymbol, currentAsharePeriod);

    // 8.1 装载该标的已保存的价格预警（K 线到位后 priceToCoordinate 才有效）
    loadAshareAlertsForSymbol(currentAshareSymbol);

    // 9. 调整面板比例与尺寸
    applyChartPanelRatios(readChartPanelRatios());
    requestAnimationFrame(() => {
        resizeCharts();
        positionAshareAlertChips();
    });

    // 10. 启动实时轮询 (3秒一次)
    startAshareLivePolling();
}

function normalizeAshareLivePeriod(period) {
    if (!period) return 'daily';
    const p = String(period).trim();
    if (p === '1D' || p === '1d' || p === '日' || p === 'daily') return 'daily';
    if (p === '1W' || p === '1w' || p === '周' || p === 'weekly') return 'weekly';
    if (p === '1M' || p === '月' || p === 'monthly' || p === 'month') return 'monthly';
    if (p === '1m' || p === '1分') return '1m';
    if (p === '5m' || p === '5分') return '5m';
    if (p === '15m' || p === '15分') return '15m';
    if (p === '30m' || p === '30分') return '30m';
    if (p === '60m' || p === '60分' || p === '1h') return '60m';
    if (p === '120m' || p === '120分' || p === '2h') return '120m';
    if (p === '240m' || p === '240分' || p === '4h' || p === '4h_session') return '240m';
    if (p === '2D' || p === '2d') return '2d';
    if (p === '3D' || p === '3d') return '3d';
    return p;
}

async function loadAshareLiveData(symbol, period = 'daily') {
    const normalizedPeriod = normalizeAshareLivePeriod(period);
    const rawSym = String(symbol || '').trim();
    const fullSym = normalizeAshareSymbol(rawSym) || rawSym;
    currentAshareSymbol = fullSym;
    currentAsharePeriod = normalizedPeriod;
    showLoading('正在加载 A 股走势...', '正在拉取分时数据并动态合成各周期...');
    try {
        // 1. 清理上一只股票的任何挂单/持仓均价价格线与标记
        clearChartTradePriceLines();
        if (tradeMarkerSeries && typeof tradeMarkerSeries.setMarkers === 'function') {
            tradeMarkerSeries.setMarkers([]);
        }

        // 2. 彻底复位主图、成交量图、指标图的价格轴自适应（autoScale: true），防止跨价格量级股票比例锁死
        try {
            chart?.priceScale('right')?.applyOptions({ autoScale: true });
            volumeChart?.priceScale('right')?.applyOptions({ autoScale: true });
            indicatorChart?.priceScale('right')?.applyOptions({ autoScale: true });
        } catch (e) {
            console.warn('复位价格轴自适应失败:', e);
        }

        // 动态设置深度条数：日K加载800根（覆盖3.3年以上历史走势，满足2年看盘指导需求）
        let requestLimit = 640;
        if (normalizedPeriod === 'daily') {
            requestLimit = 800;
        } else if (normalizedPeriod === 'weekly') {
            requestLimit = 200;
        } else if (normalizedPeriod === 'monthly') {
            requestLimit = 120;
        }

        const [klineRes, snap] = await Promise.all([
            fetch(`/api/ashare/live/kline?symbol=${encodeURIComponent(rawSym)}&period=${normalizedPeriod}&limit=${requestLimit}`).then(r => r.json()),
            fetch(`/api/ashare/live/snapshot?symbol=${encodeURIComponent(rawSym)}`).then(r => r.json())
        ]);

        if (snap && snap.price > 0) {
            currentAshareName = snap.name || rawSym;
            currentAsharePrice = snap.price;
            recordAshareLastPrice(currentAshareSymbol, snap.price);
            if (snap.code) recordAshareLastPrice(snap.code, snap.price);
            updateAshareHeaderTicker(snap);

            const windowStatusEl = document.getElementById('chart-window-status');
            if (windowStatusEl) windowStatusEl.textContent = '已加载实时走势 (UTC+8)';
        }

        if (klineRes && klineRes.kline_data && klineRes.kline_data.length > 0) {
            const volMap = new Map();
            (klineRes.volume_data || []).forEach(v => {
                const vt = typeof v.time === 'number' ? v.time : intradayBarToTimestamp(v);
                volMap.set(vt, v.value);
            });
            const formattedKlines = klineRes.kline_data.map(b => {
                const bt = typeof b.time === 'number' ? b.time : intradayBarToTimestamp(b);
                return {
                    ...b,
                    time: bt,
                    volume: b.volume ?? volMap.get(bt) ?? 0
                };
            });
            const formattedVols = (klineRes.volume_data || []).map(v => ({
                ...v,
                time: typeof v.time === 'number' ? v.time : intradayBarToTimestamp(v)
            }));
            latestRenderedVolumeData = formattedVols.map(v => ({ ...v }));

            // 如果处于截断复盘中，保持复盘模式并将截断进度平滑映射到新周期
            if (typeof barReplayState !== 'undefined' && barReplayState && barReplayState.active) {
                handleBarReplayPeriodSwitch(formattedKlines, formattedVols, normalizedPeriod);
                updateAshareLiveTradeMarkers();
                requestAnimationFrame(resizeCharts);
                renderAshareLiveAccount();
                return;
            }

            replaceRenderedKlineData(formattedKlines, formattedVols);
            if (candlestickSeries) candlestickSeries.setData(formattedKlines);
            if (volumeSeries) volumeSeries.setData(formattedVols);

            updateMaLinesFromRendered();
            applyLastPriceTagColor();
            showLatestChartInfo();

            // 同步时间轴与视野给所有联动图表 (主图 + 成交量 + 指标)
            if (formattedKlines.length > 160) {
                setVisibleRangeAll({
                    from: formattedKlines.length - 140,
                    to: formattedKlines.length + 5
                });
            } else {
                [chart, volumeChart, indicatorChart].forEach(c => c?.timeScale().fitContent());
            }

            if (indicatorPanelVisible && currentIndicatorType) {
                await loadTechnicalIndicator(currentIndicatorType);
            }

            // 把本标的历史成交标回 K 线（买入在下、卖出在上）
            updateAshareLiveTradeMarkers();

            // 再次确保价格轴与成交量轴自适应已重算生效
            try {
                chart?.priceScale('right')?.applyOptions({ autoScale: true });
                volumeChart?.priceScale('right')?.applyOptions({ autoScale: true });
                indicatorChart?.priceScale('right')?.applyOptions({ autoScale: true });
            } catch (e) {}

            requestAnimationFrame(resizeCharts);
        }

        renderAshareLiveAccount();
    } catch (err) {
        console.error('加载 A 股走势异常:', err);
    } finally {
        hideLoading();
    }
}

async function switchAshareLivePeriod(period) {
    if (!isAshareLiveMode) return;
    const normalizedPeriod = normalizeAshareLivePeriod(period);
    currentAsharePeriod = normalizedPeriod;
    updatePeriodBadge(normalizedPeriod);
    document.querySelectorAll('.ashare-live-period.view-period-btn').forEach(b => {
        const btnPeriod = normalizeAshareLivePeriod(b.dataset.period);
        b.classList.toggle('active', btnPeriod === normalizedPeriod || b.dataset.period === period);
    });
    await loadAshareLiveData(currentAshareSymbol, normalizedPeriod);
}

async function switchAshareLiveStock(code, name) {
    if (barReplayState && barReplayState.active) {
        exitBarReplay();
    }
    const rawSym = String(code || '').trim();
    const fullSym = normalizeAshareSymbol(rawSym) || rawSym;
    const normCode = rawSym.replace(/^(sh|sz|bj)/i, '');
    currentAshareSymbol = fullSym;
    if (name) currentAshareName = name;
    renderAshareWatchlist();
    await loadAshareLiveData(fullSym, currentAsharePeriod);
    // 画图按标的隔离：换股后重建绘图控制器，装载该标的自己的已保存画图
    // （原标的的画图已在每次变更时回写，不会丢失）。
    initializeDrawingTools();
    // 价格预警同样按标的隔离
    loadAshareAlertsForSymbol(normCode);
    requestAnimationFrame(() => {
        resizeCharts();
        positionAshareAlertChips();
    });
}

function startAshareLivePolling() {
    stopAshareLivePolling();
    ashareLivePollTimer = setInterval(async () => {
        if (!isAshareLiveMode) return;
        const pollSymbol = currentAshareSymbol;
        const pollPeriod = currentAsharePeriod;
        try {
            // 1. 同步自选股与持仓批量行情
            await fetchAshareWatchlistQuotes();

            // 2. 当前选中标的实时分时/K线更新
            const snap = await fetch(`/api/ashare/live/snapshot?symbol=${encodeURIComponent(pollSymbol)}`).then(r => r.json());
            if (pollSymbol !== currentAshareSymbol) return; // 标的已切换，丢弃过时轮询响应
            if (snap && snap.price > 0) {
                currentAsharePrice = snap.price;
                // 价格预警：穿越判定要用"上一轮价 → 当前价"，必须在覆盖基准价之前执行
                if (Number.isFinite(ashareAlertLastPrice)) {
                    checkAshareAlerts(ashareAlertLastPrice, snap.price);
                }
                ashareAlertLastPrice = snap.price;
                recordAshareLastPrice(currentAshareSymbol, snap.price);
                if (snap.code) recordAshareLastPrice(snap.code, snap.price);
                matchAsharePendingOrders(snap.price);
                updateAshareHeaderTicker(snap);

                // 复盘截断进行中时，暂停向图表追加最新实时 K 线，避免冲掉复盘切片
                if (barReplayState && barReplayState.active) {
                    renderAshareLiveAccount();
                    scheduleAshareAlertChipsUpdate();
                    return;
                }

                const klineRes = await fetch(`/api/ashare/live/kline?symbol=${encodeURIComponent(pollSymbol)}&period=${pollPeriod}&limit=2`).then(r => r.json());
                if (pollSymbol !== currentAshareSymbol) return;
                if (klineRes && klineRes.kline_data && klineRes.kline_data.length > 0) {
                    const latestBar = klineRes.kline_data[klineRes.kline_data.length - 1];
                    const latestVol = klineRes.volume_data[klineRes.volume_data.length - 1];
                    const formattedBar = {
                        ...latestBar,
                        time: typeof latestBar.time === 'number' ? latestBar.time : intradayBarToTimestamp(latestBar)
                    };
                    const formattedVol = {
                        ...latestVol,
                        time: typeof latestVol.time === 'number' ? latestVol.time : intradayBarToTimestamp(latestVol)
                    };
                    upsertRenderedBar(formattedBar);
                    if (candlestickSeries) candlestickSeries.update(formattedBar);
                    if (volumeSeries) volumeSeries.update(formattedVol);
                    updateMaLinesFromRendered();
                    applyLastPriceTagColor();
                    showLatestChartInfo();
                    if (indicatorPanelVisible && currentIndicatorType) {
                        await loadTechnicalIndicator(currentIndicatorType);
                    }
                }
                renderAshareLiveAccount();
                // 价格轴会随最新价自适应，预警标签需同步贴回新的坐标
                scheduleAshareAlertChipsUpdate();
            }
        } catch (err) {
            console.warn('A股实时轮询失败:', err);
        }
    }, 3000);
}

function stopAshareLivePolling() {
    if (ashareLivePollTimer) {
        clearInterval(ashareLivePollTimer);
        ashareLivePollTimer = null;
    }
}

function renderAshareLiveAccount() {
    if (!isAshareLiveMode) return;
    const acc = getAshareLiveAccount();
    const normSym = String(currentAshareSymbol || '').replace(/^(sh|sz|bj)/i, '');
    const fullSym = normalizeAshareSymbol(currentAshareSymbol);
    const pos = acc.positions[currentAshareSymbol] || acc.positions[normSym] || (fullSym && acc.positions[fullSym]) || { total_shares: 0, frozen_today: 0, avg_cost: 0 };
    const availShares = computeAshareAvailShares
        ? computeAshareAvailShares(pos)
        : Math.max(0, pos.total_shares - (pos.frozen_today || 0) - (pos.frozen_sell || 0));

    // 计算当前标的持仓与浮盈
    const curPrice = currentAsharePrice || 0;
    let totalPosVal = 0;

    for (const sym in acc.positions) {
        const p = acc.positions[sym];
        if (p && p.total_shares > 0) {
            const isCur = (sym === currentAshareSymbol || sym === normSym || (fullSym && sym === fullSym));
            const price = isCur ? curPrice : (p.last_price || p.avg_cost || 0);
            totalPosVal += p.total_shares * price;
        }
    }

    const totalAssets = acc.cash + (Number(acc.cash_frozen) || 0) + totalPosVal; // 现金 + 挂单冻结 + 全部持仓市值
    const curPosVal = pos.total_shares * curPrice;
    const floatPnl = (curPrice > 0 && pos.avg_cost > 0 && pos.total_shares > 0)
        ? (curPrice - pos.avg_cost) * pos.total_shares
        : 0;
    const floatPnlRate = (pos.avg_cost > 0 && curPrice > 0)
        ? ((curPrice - pos.avg_cost) / pos.avg_cost) * 100
        : 0;

    // 更新 A 股专属四宫格资产指标
    const totalAssetsEl = document.getElementById('ashare-live-total-assets');
    if (totalAssetsEl) totalAssetsEl.textContent = `¥${totalAssets.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    const availCashEl = document.getElementById('ashare-live-available-cash');
    if (availCashEl) availCashEl.textContent = `¥${acc.cash.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    const posValEl = document.getElementById('ashare-live-position-value');
    if (posValEl) posValEl.textContent = `¥${totalPosVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; // 全部持仓市值

    const pnlEl = document.getElementById('ashare-live-floating-pnl');
    if (pnlEl) {
        if (pos.total_shares > 0 && pos.avg_cost > 0) {
            const sign = floatPnl >= 0 ? '+' : '';
            pnlEl.textContent = `${sign}¥${floatPnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${sign}${floatPnlRate.toFixed(2)}%)`;
            pnlEl.style.color = floatPnl >= 0 ? 'var(--crypto-up, #f6465d)' : 'var(--crypto-down, #0ecb81)';
        } else {
            pnlEl.textContent = '¥0.00 (+0.00%)';
            pnlEl.style.color = 'var(--crypto-muted)';
        }
    }

    // 标的代码展示
    const posCodeEl = document.getElementById('ashare-live-pos-code');
    if (posCodeEl) posCodeEl.textContent = `${currentAshareName} (${currentAshareSymbol})`;

    // 更新当前持仓卡片：只展示"本股票"的持仓。
    // 历史行为是列出全部标的持仓（当前标的置顶 ★当前），但多标的/多笔订单一多就很乱；
    // 其余标的的持仓统一到左侧自选面板的「持仓」标签页查看（getAshareTabStocks）。
    const posContainer = document.getElementById('ashare-live-positions');
    const unfreezeBtn = document.getElementById('ashare-live-unfreeze-btn');
    if (posContainer) {
        const currentHeldShares = Number(pos.total_shares) || 0;
        const heldPosKey = findAsharePositionKey(acc, currentAshareSymbol);
        const heldCodes = (currentHeldShares > 0 && heldPosKey) ? [heldPosKey] : [];
        if (heldCodes.length > 0) {
            posContainer.innerHTML = heldCodes.map((code) => {
                const p = acc.positions[code];
                const isCurrent = (code === currentAshareSymbol || code === normSym || (fullSym && code === fullSym));
                const price = isCurrent ? curPrice : (Number(asharePriceCache[code]) || Number(p.avg_cost) || 0);
                const avail = computeAshareAvailShares ? computeAshareAvailShares(p) : Math.max(0, p.total_shares - (p.frozen_today || 0) - (p.frozen_sell || 0));
                const pnl = (price > 0 && p.avg_cost > 0) ? (price - p.avg_cost) * p.total_shares : 0;
                const pnlRate = (p.avg_cost > 0 && price > 0) ? ((price - p.avg_cost) / p.avg_cost) * 100 : 0;
                const sign = pnl >= 0 ? '+' : '';
                const frozenTags = [
                    p.frozen_today > 0 ? `🔒T+1 ${p.frozen_today}股` : '',
                    p.frozen_sell > 0 ? `📋挂卖 ${p.frozen_sell}股` : ''
                ].filter(Boolean).join('　');
                return `
                <div class="ashare-pos-card${isCurrent ? ' current-symbol' : ''}">
                    <div class="ashare-pos-header">
                        <span>${p.name || code} (${code})</span>
                        <span style="color: ${pnl >= 0 ? '#f6465d' : '#0ecb81'}">${sign}¥${pnl.toFixed(2)} (${sign}${pnlRate.toFixed(2)}%)</span>
                    </div>
                    <div class="ashare-pos-grid">
                        <div class="ashare-pos-grid-item"><span>总持仓:</span><strong>${p.total_shares} 股 (${(p.total_shares / 100).toFixed(0)}手)</strong></div>
                        <div class="ashare-pos-grid-item"><span>可卖:</span><strong style="color: #f0b90b;">${avail} 股 (${Math.floor(avail / 100)}手)</strong></div>
                        <div class="ashare-pos-grid-item"><span>成本均价:</span><strong>¥${Number(p.avg_cost || 0).toFixed(2)}</strong></div>
                        <div class="ashare-pos-grid-item"><span>现价:</span><strong>¥${Number(price).toFixed(2)}</strong></div>
                    </div>
                    ${frozenTags ? `<div class="ashare-pos-frozen-tag"><span>${frozenTags}</span></div>` : ''}
                </div>`;
            }).join('');
            if (unfreezeBtn) unfreezeBtn.classList.toggle('hidden', !(Number(pos.frozen_today) > 0));
        } else {
            posContainer.innerHTML = '<div class="no-positions">暂无持仓</div>';
            if (unfreezeBtn) unfreezeBtn.classList.add('hidden');
        }
    }

    // 限价挂单列表（跨标的，可撤单）
    const ordersContainer = document.getElementById('ashare-live-orders');
    if (ordersContainer) {
        const openOrders = (acc.pending_orders || []).filter(o => o.status === 'open');
        if (openOrders.length > 0) {
            ordersContainer.innerHTML = openOrders.map((o) => `
                <div class="ashare-order-row">
                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 6px;">
                        <div style="display: flex; gap: 6px; align-items: center; min-width: 0;">
                            <span class="ashare-order-side ${o.side}">${o.side === 'buy' ? '买' : '卖'}</span>
                            <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${o.name || o.code}</span>
                        </div>
                        <button type="button" class="ashare-cancel-order-btn" data-order-id="${o.id}">撤单</button>
                    </div>
                    <div style="display: flex; justify-content: space-between; color: var(--crypto-muted); margin-top: 2px;">
                        <span>¥${Number(o.price).toFixed(2)} × ${o.shares}股 (${o.shares / 100}手)</span>
                        <span>${o.created_date || ''}</span>
                    </div>
                </div>
            `).join('');
        } else {
            ordersContainer.innerHTML = '<div class="no-positions">暂无挂单</div>';
        }
    }

    // 更新委托价格显示与最大可买/可卖手
    const priceText = curPrice > 0 ? `¥${curPrice.toFixed(2)}` : '--';
    const buyPriceEl = document.getElementById('ashare-buy-price-display');
    if (buyPriceEl) buyPriceEl.textContent = priceText;
    const sellPriceEl = document.getElementById('ashare-sell-price-display');
    if (sellPriceEl) sellPriceEl.textContent = priceText;

    const maxBuyLots = (curPrice > 0) ? Math.floor(acc.cash / (curPrice * 100)) : 0;
    const maxSellLots = Math.floor(availShares / 100);
    const maxBuyEl = document.getElementById('ashare-max-buy-lots');
    if (maxBuyEl) maxBuyEl.textContent = String(maxBuyLots);
    const maxSellEl = document.getElementById('ashare-max-sell-lots');
    if (maxSellEl) maxSellEl.textContent = String(maxSellLots);

    // 更新买入/卖出输入预估
    updateAshareOrderPreview();

    // 渲染历史成交记录
    const histContainer = document.getElementById('ashare-live-trade-history');
    if (histContainer) {
        if (acc.trade_history && acc.trade_history.length > 0) {
            histContainer.innerHTML = acc.trade_history.map(t => `
                <div class="ashare-trade-item">
                    <div style="display: flex; gap: 6px; align-items: center;">
                        <span class="ashare-trade-type ${t.type === '买入' ? 'buy' : 'sell'}">${t.type}</span>
                        <span>${t.name}</span>
                        <span style="color: var(--crypto-muted);">${t.shares}股 (${t.lots || (t.shares / 100)}手)</span>
                    </div>
                    <div style="text-align: right;">
                        <div>¥${Number(t.price || 0).toFixed(2)}</div>
                        <div class="ashare-trade-time" title="${escapeHtml(formatAshareTradeStampFull(t))}">${escapeHtml(formatAshareTradeStamp(t))}${Number(t.fee) > 0 ? ` · 费¥${Number(t.fee).toFixed(2)}` : ''}</div>
                    </div>
                </div>
            `).join('');
        } else {
            histContainer.innerHTML = '<div class="no-trades">暂无交易记录</div>';
        }
    }
    if (currentAshareWlTab === 'holding') {
        renderAshareWatchlist();
    }
}

function updateAshareOrderPreview() {
    const acc = getAshareLiveAccount();
    const pos = getAsharePosition(acc, currentAshareSymbol);

    // 买入预估计算（限价按输入限价，市价按现价）
    const buyLotsInput = document.getElementById('ashare-buy-lots');
    const buyLots = Math.max(0, parseInt(buyLotsInput?.value, 10) || 0);
    const buyShares = buyLots * 100;
    const buyPrice = (ashareBuyOrderType === 'limit') ? getAshareLimitPrice('buy') : (currentAsharePrice || 0);
    const buyAmount = buyShares * buyPrice;
    const buyFees = computeAshareTradeFees ? computeAshareTradeFees('buy', buyAmount) : { total: 0 };
    const buyCost = buyAmount + buyFees.total;
    const remainCash = Math.max(0, acc.cash - buyCost);

    const buyCostEl = document.getElementById('ashare-buy-total-cost');
    if (buyCostEl) buyCostEl.textContent = `¥${buyCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    const remainCashEl = document.getElementById('ashare-buy-remain-cash');
    if (remainCashEl) {
        remainCashEl.textContent = `¥${remainCash.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        remainCashEl.style.color = acc.cash < buyCost ? '#f6465d' : '';
    }

    // 卖出预估计算（限价按输入限价，市价按现价）
    const sellLotsInput = document.getElementById('ashare-sell-lots');
    const sellLots = Math.max(0, parseInt(sellLotsInput?.value, 10) || 0);
    const sellShares = sellLots * 100;
    const sellPrice = (ashareSellOrderType === 'limit') ? getAshareLimitPrice('sell') : (currentAsharePrice || 0);
    const sellAmount = sellShares * sellPrice;
    const sellFeesPreview = computeAshareTradeFees ? computeAshareTradeFees('sell', sellAmount) : { total: 0 };
    const sellRevenue = sellAmount - sellFeesPreview.total;

    const sellRevenueEl = document.getElementById('ashare-sell-total-revenue');
    if (sellRevenueEl) sellRevenueEl.textContent = `¥${sellRevenue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    const frozenHintEl = document.getElementById('ashare-sell-frozen-hint');
    if (frozenHintEl) frozenHintEl.textContent = `${pos.frozen_today || 0} 股`;
}

function selectAshareOrderAction(action) {
    const buyTab = document.getElementById('ashare-tab-buy');
    const sellTab = document.getElementById('ashare-tab-sell');
    const buySubpanel = document.getElementById('ashare-buy-subpanel');
    const sellSubpanel = document.getElementById('ashare-sell-subpanel');

    const isBuy = action === 'buy';
    buyTab?.classList.toggle('active', isBuy);
    sellTab?.classList.toggle('active', !isBuy);
    buySubpanel?.classList.toggle('hidden', !isBuy);
    sellSubpanel?.classList.toggle('hidden', isBuy);
    updateAshareOrderPreview();
}

function applyAshareFraction(target, fraction) {
    const acc = getAshareLiveAccount();
    const frac = Number(fraction) || 1;
    if (target === 'buy') {
        if (currentAsharePrice <= 0) return;
        const maxLots = Math.floor(acc.cash / (currentAsharePrice * 100));
        const lots = frac >= 1 ? maxLots : Math.floor(maxLots * frac);
        const input = document.getElementById('ashare-buy-lots');
        if (input) input.value = Math.max(0, lots);
    } else {
        const pos = getAsharePosition(acc, currentAshareSymbol);
        const availShares = computeAshareAvailShares
        ? computeAshareAvailShares(pos)
        : Math.max(0, pos.total_shares - (pos.frozen_today || 0) - (pos.frozen_sell || 0));
        const availLots = Math.floor(availShares / 100);
        const lots = frac >= 1 ? availLots : Math.floor(availLots * frac);
        const input = document.getElementById('ashare-sell-lots');
        if (input) input.value = Math.max(0, lots);
    }
    updateAshareOrderPreview();
}

// ==========================================================================
// A股实时看盘：限价挂单（当日有效、快照到达时撮合、撤单退冻结）
// 模型：买入挂单提交即从 cash 扣除至 cash_frozen；卖出挂单冻结 positions[code].frozen_sell
// ==========================================================================

function getAshareOrderType(side) {
    return side === 'sell' ? ashareSellOrderType : ashareBuyOrderType;
}

function setAshareOrderType(side, type) {
    if (side === 'sell') ashareSellOrderType = type;
    else ashareBuyOrderType = type;
    const panel = side === 'sell' ? 'sell' : 'buy';
    document.querySelectorAll(`.ashare-order-type-switch[data-target="${panel}"] .ashare-order-type-btn`).forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.otype === type);
    });
    const priceDisplay = document.getElementById(`ashare-${panel}-price-display`);
    const limitInput = document.getElementById(`ashare-${panel}-limit-price`);
    if (priceDisplay) priceDisplay.classList.toggle('hidden', type === 'limit');
    if (limitInput) {
        limitInput.classList.toggle('hidden', type !== 'limit');
        if (type === 'limit' && !limitInput.value && currentAsharePrice > 0) {
            limitInput.value = currentAsharePrice.toFixed(2);
        }
    }
    updateAshareOrderPreview();
}

function getAshareLimitPrice(side) {
    const raw = document.getElementById(`ashare-${side}-limit-price`)?.value;
    const px = parseFloat(raw);
    return Number.isFinite(px) && px > 0 ? Math.round(px * 100) / 100 : 0;
}

function submitAshareLimitBuy() {
    const lots = parseInt(document.getElementById('ashare-buy-lots')?.value, 10) || 0;
    const shares = lots * 100;
    const price = getAshareLimitPrice('buy');
    if (price <= 0) {
        alert('请输入有效的限价价格！');
        return;
    }
    if (lots <= 0) {
        alert('A股买入最小单位为 1 手（100 股），请输入有效整数手！');
        return;
    }
    const acc = getAshareLiveAccount();
    const check = validateAshareLimitBuy ? validateAshareLimitBuy(acc.cash, price, shares) : { valid: true };
    if (!check.valid) {
        alert(check.error);
        return;
    }
    // 提交即冻结（含买入佣金）：cash → cash_frozen；frozen_amount 记录冻结总额，成交/撤单/失效统一按其退回
    const buyFees = computeAshareTradeFees ? computeAshareTradeFees('buy', check.cost) : { total: 0 };
    const frozenAmount = check.cost + buyFees.total;
    acc.cash -= frozenAmount;
    acc.cash_frozen = (Number(acc.cash_frozen) || 0) + frozenAmount;
    acc.pending_orders = acc.pending_orders || [];
    acc.pending_orders.push({
        id: `lb${Date.now()}${Math.floor(Math.random() * 1000)}`,
        code: currentAshareSymbol,
        name: currentAshareName,
        side: 'buy',
        price,
        shares,
        frozen_amount: frozenAmount,
        created_date: new Date().toISOString().slice(0, 10),
        status: 'open'
    });
    saveAshareLiveAccount(acc);
    renderAshareLiveAccount();
    alert(`限价买单已提交！${currentAshareName} ${shares} 股 @ ¥${price.toFixed(2)}，冻结资金 ¥${frozenAmount.toFixed(2)}（含佣金 ¥${buyFees.total.toFixed(2)}）。\n价格到达即自动成交，当日收盘后未成交自动失效。`);
}

function submitAshareLimitSell() {
    const lots = parseInt(document.getElementById('ashare-sell-lots')?.value, 10) || 0;
    const shares = lots * 100;
    const price = getAshareLimitPrice('sell');
    if (price <= 0) {
        alert('请输入有效的限价价格！');
        return;
    }
    if (lots <= 0) {
        alert('A股卖出请输入有效手数（至少 1 手）！');
        return;
    }
    const acc = getAshareLiveAccount();
    const posKey = findAsharePositionKey(acc, currentAshareSymbol) || currentAshareSymbol;
    const pos = acc.positions[posKey] || { total_shares: 0, frozen_today: 0, frozen_sell: 0 };
    const check = validateAshareLimitSell ? validateAshareLimitSell(pos, price, shares) : { valid: true };
    if (!check.valid) {
        alert(check.error);
        return;
    }
    // 提交即冻结可用持仓
    pos.frozen_sell = (Number(pos.frozen_sell) || 0) + shares;
    acc.positions[posKey] = pos;
    acc.pending_orders = acc.pending_orders || [];
    acc.pending_orders.push({
        id: `ls${Date.now()}${Math.floor(Math.random() * 1000)}`,
        code: currentAshareSymbol,
        name: currentAshareName,
        side: 'sell',
        price,
        shares,
        created_date: new Date().toISOString().slice(0, 10),
        status: 'open'
    });
    saveAshareLiveAccount(acc);
    renderAshareLiveAccount();
    alert(`限价卖单已提交！${currentAshareName} ${shares} 股 @ ¥${price.toFixed(2)}（可用持仓已冻结）。\n价格到达即自动成交，当日收盘后未成交自动失效。`);
}

function cancelAsharePendingOrder(orderId) {
    const acc = getAshareLiveAccount();
    const order = (acc.pending_orders || []).find(o => o.id === orderId && o.status === 'open');
    if (!order) return;
    // 退回冻结
    if (order.side === 'buy') {
        const refund = Number(order.frozen_amount) || (Number(order.price) || 0) * (Number(order.shares) || 0);
        acc.cash += refund;
        acc.cash_frozen = Math.max(0, (Number(acc.cash_frozen) || 0) - refund);
    } else {
        const pos = acc.positions[order.code];
        if (pos) pos.frozen_sell = Math.max(0, (Number(pos.frozen_sell) || 0) - (Number(order.shares) || 0));
    }
    order.status = 'canceled';
    saveAshareLiveAccount(acc);
    renderAshareLiveAccount();
}

/**
 * 快照到达时撮合当前标的的 open 挂单（含跨日失效兜底）。
 * 成交：买入按挂单价入账（cash_frozen 释放、持仓入账并进 T+1 冻结）；
 *       卖出按挂单价回笼资金（frozen_sell 释放、持仓扣减）。
 */
function matchAsharePendingOrders(price) {
    if (!isAshareLiveMode || !(price > 0)) return;
    const acc = getAshareLiveAccount();
    const orders = acc.pending_orders || [];
    const todayStr = new Date().toISOString().slice(0, 10);
    const mine = orders.filter(o => o.status === 'open' && o.code === currentAshareSymbol);
    const othersExpired = orders.filter(o => o.status === 'open' && o.code !== currentAshareSymbol && o.created_date !== todayStr);
    if (mine.length === 0 && othersExpired.length === 0) return;

    let changed = false;
    const { fills, expired } = matchAshareLimitOrders ? matchAshareLimitOrders(mine, price, todayStr) : { fills: [], expired: [] };

    expired.forEach(({ order }) => {
        order.status = 'expired';
        if (order.side === 'buy') {
            const refund = Number(order.frozen_amount) || (Number(order.price) || 0) * (Number(order.shares) || 0);
            acc.cash += refund;
            acc.cash_frozen = Math.max(0, (Number(acc.cash_frozen) || 0) - refund);
        } else {
            const pos = acc.positions[order.code];
            if (pos) pos.frozen_sell = Math.max(0, (Number(pos.frozen_sell) || 0) - (Number(order.shares) || 0));
        }
        changed = true;
    });
    othersExpired.forEach((order) => {
        order.status = 'expired';
        if (order.side === 'buy') {
            const refund = Number(order.frozen_amount) || (Number(order.price) || 0) * (Number(order.shares) || 0);
            acc.cash += refund;
            acc.cash_frozen = Math.max(0, (Number(acc.cash_frozen) || 0) - refund);
        } else {
            const pos = acc.positions[order.code];
            if (pos) pos.frozen_sell = Math.max(0, (Number(pos.frozen_sell) || 0) - (Number(order.shares) || 0));
        }
        changed = true;
    });

    fills.forEach(({ order }) => {
        order.status = 'filled';
        const px = Number(order.price) || 0;
        const shares = Number(order.shares) || 0;
        const pos = acc.positions[order.code] || { total_shares: 0, frozen_today: 0, frozen_sell: 0, avg_cost: 0 };
        if (order.side === 'buy') {
            // 释放提交时冻结的总额（含买入佣金），持仓成本按含费口径入账
            const frozenAmount = Number(order.frozen_amount) || px * shares;
            acc.cash_frozen = Math.max(0, (Number(acc.cash_frozen) || 0) - frozenAmount);
            const oldTotal = Number(pos.total_shares) || 0;
            pos.avg_cost = ((oldTotal * (Number(pos.avg_cost) || 0)) + frozenAmount) / (oldTotal + shares);
            pos.total_shares = oldTotal + shares;
            pos.frozen_today = (Number(pos.frozen_today) || 0) + shares; // T+1
            acc.trade_history.unshift({ time: new Date().toLocaleTimeString(), date: new Date().toISOString().slice(0, 10), type: '买入', symbol: order.code, code: order.code, name: order.name, lots: shares / 100, shares, price: px, cost: px * shares, fee: frozenAmount - px * shares, note: '限价成交', bar_time: String(order.code) === String(currentAshareSymbol) ? currentAshareBarTime() : null });
        } else {
            pos.frozen_sell = Math.max(0, (Number(pos.frozen_sell) || 0) - shares);
            pos.total_shares = Math.max(0, (Number(pos.total_shares) || 0) - shares);
            if (pos.total_shares <= 0) { pos.total_shares = 0; pos.avg_cost = 0; pos.frozen_today = 0; pos.frozen_sell = 0; }
            const sellFees = computeAshareTradeFees ? computeAshareTradeFees('sell', px * shares) : { total: 0 };
            acc.cash += px * shares - sellFees.total;
            acc.trade_history.unshift({ time: new Date().toLocaleTimeString(), date: new Date().toISOString().slice(0, 10), type: '卖出', symbol: order.code, code: order.code, name: order.name, lots: shares / 100, shares, price: px, cost: px * shares, fee: sellFees.total, note: '限价成交', bar_time: String(order.code) === String(currentAshareSymbol) ? currentAshareBarTime() : null });
        }
        acc.positions[order.code] = pos;
        changed = true;
    });

    if (changed) {
        saveAshareLiveAccount(acc);
        renderAshareLiveAccount();
        // 限价成交也要补上 K 线标记（若成交的是当前标的）
        updateAshareLiveTradeMarkers();
    }
}

function executeAshareLiveBuy() {
    if (ashareBuyOrderType === 'limit') {
        submitAshareLimitBuy();
        return;
    }
    const qtyInput = document.getElementById('ashare-buy-lots');
    const lots = parseInt(qtyInput?.value, 10) || 0;
    if (lots <= 0) {
        alert('A股买入最小单位为 1 手（100 股），请输入有效整数手！');
        return;
    }
    if (currentAsharePrice <= 0) {
        alert('未获取到当前有效标的价格，请等待行情加载！');
        return;
    }
    const shares = lots * 100;
    const amount = shares * currentAsharePrice;
    const fees = computeAshareTradeFees ? computeAshareTradeFees('buy', amount) : { total: 0, commission: 0, stampTax: 0 };
    const cost = amount + fees.total; // 含买入佣金
    const acc = getAshareLiveAccount();

    if (acc.cash < cost) {
        alert(`可用资金不足！买入 ${lots} 手 (${shares} 股) 含佣金需 ¥${cost.toFixed(2)}（成交额 ¥${amount.toFixed(2)} + 佣金 ¥${fees.total.toFixed(2)}），当前可用资金仅有 ¥${acc.cash.toFixed(2)}。`);
        return;
    }

    acc.cash -= cost;
    const posKey = findAsharePositionKey(acc, currentAshareSymbol) || currentAshareSymbol;
    const pos = acc.positions[posKey] || { total_shares: 0, frozen_today: 0, avg_cost: 0 };
    const oldTotal = pos.total_shares || 0;
    const newTotal = oldTotal + shares;
    pos.avg_cost = ((oldTotal * (pos.avg_cost || 0)) + cost) / newTotal; // 成本均价含买入佣金
    pos.total_shares = newTotal;
    pos.frozen_today = (pos.frozen_today || 0) + shares; // T+1 锁定当日买入持仓
    if (!pos.name) pos.name = currentAshareName;
    if (!pos.symbol) pos.symbol = currentAshareSymbol;
    acc.positions[posKey] = pos;
    acc.last_date = new Date().toISOString().slice(0, 10);

    acc.trade_history.unshift({
        id: 'ord_' + Date.now(),
        time: new Date().toLocaleTimeString(),
        date: acc.last_date,
        type: '买入',
        symbol: currentAshareSymbol,
        name: currentAshareName,
        lots: lots,
        shares: shares,
        price: currentAsharePrice,
        cost: amount,
        fee: fees.total,
        bar_time: currentAshareBarTime()
    });

    saveAshareLiveAccount(acc);
    renderAshareLiveAccount();
    updateAshareLiveTradeMarkers();
    alert(`【买入成交】已以市价 ¥${currentAsharePrice.toFixed(2)} 买入 ${currentAshareName} ${lots} 手 (${shares} 股)，成交额 ¥${amount.toFixed(2)} + 佣金 ¥${fees.total.toFixed(2)} = 合计 ¥${cost.toFixed(2)}。\n\n📌 规则提示：根据 A 股 T+1 交易制度，今日买入的 ${shares} 股已锁定，下一个交易日方可卖出。`);
}

function executeAshareLiveSell() {
    if (ashareSellOrderType === 'limit') {
        submitAshareLimitSell();
        return;
    }
    const qtyInput = document.getElementById('ashare-sell-lots');
    const lots = parseInt(qtyInput?.value, 10) || 0;
    if (lots <= 0) {
        alert('A股卖出请输入有效手数（至少 1 手）！');
        return;
    }
    if (currentAsharePrice <= 0) {
        alert('未获取到当前有效标的价格，请等待行情加载！');
        return;
    }
    const shares = lots * 100;
    const acc = getAshareLiveAccount();
    const posKey = findAsharePositionKey(acc, currentAshareSymbol) || currentAshareSymbol;
    const pos = acc.positions[posKey] || { total_shares: 0, frozen_today: 0, avg_cost: 0 };
    const availShares = computeAshareAvailShares
        ? computeAshareAvailShares(pos)
        : Math.max(0, pos.total_shares - (pos.frozen_today || 0) - (pos.frozen_sell || 0));

    if (shares > availShares) {
        alert(`【T+1 卖出限制】可用持仓不足！\n\n当前总持仓: ${pos.total_shares} 股 (${(pos.total_shares / 100).toFixed(0)} 手)\n今日买入冻结: ${pos.frozen_today || 0} 股 (🔒 T+1 限制，当日不可卖)\n当前可卖持仓: ${availShares} 股 (${Math.floor(availShares / 100)} 手)\n您尝试卖出: ${shares} 股 (${lots} 手)。`);
        return;
    }

    const amount = shares * currentAsharePrice;
    const sellFees = computeAshareTradeFees ? computeAshareTradeFees('sell', amount) : { total: 0, commission: 0, stampTax: 0 };
    const revenue = amount - sellFees.total; // 回笼 = 成交额 - 佣金 - 印花税
    acc.cash += revenue;
    pos.total_shares -= shares;
    if (pos.total_shares <= 0) {
        pos.total_shares = 0;
        pos.avg_cost = 0;
        pos.frozen_today = 0;
    }
    acc.positions[posKey] = pos;
    acc.last_date = new Date().toISOString().slice(0, 10);

    acc.trade_history.unshift({
        id: 'ord_' + Date.now(),
        time: new Date().toLocaleTimeString(),
        date: acc.last_date,
        type: '卖出',
        symbol: currentAshareSymbol,
        name: currentAshareName,
        lots: lots,
        shares: shares,
        price: currentAsharePrice,
        cost: amount,
        fee: sellFees.total,
        bar_time: currentAshareBarTime()
    });

    saveAshareLiveAccount(acc);
    renderAshareLiveAccount();
    updateAshareLiveTradeMarkers();
    alert(`【卖出成交】已以市价 ¥${currentAsharePrice.toFixed(2)} 卖出 ${currentAshareName} ${lots} 手 (${shares} 股)，成交额 ¥${amount.toFixed(2)} - 费用 ¥${sellFees.total.toFixed(2)}（佣金+印花税）= 回笼 ¥${revenue.toFixed(2)}。`);
}

function clearAshareTradeHistory() {
    if (!confirm('确定清空 A 股模拟交易的全部历史成交记录吗？')) return;
    const acc = getAshareLiveAccount();
    acc.trade_history = [];
    saveAshareLiveAccount(acc);
    renderAshareLiveAccount();
    // 记录清空后图上的买入/卖出标记也要同步清掉
    updateAshareLiveTradeMarkers();
}

function unfreezeAshareT1Holdings() {
    const acc = getAshareLiveAccount();
    let thawedCount = 0;
    for (const sym in acc.positions) {
        const pos = acc.positions[sym];
        if (pos && pos.frozen_today > 0) {
            thawedCount += pos.frozen_today;
            pos.frozen_today = 0;
        }
    }
    saveAshareLiveAccount(acc);
    renderAshareLiveAccount();
    alert(`【模拟次日开盘】已成功解冻 ${thawedCount} 股今日买入持仓，全部转为可用可卖持仓！`);
}

function resetAshareLiveAccount() {
    if (!confirm('确定重置 A 股模拟账户吗？现金将恢复为 100,000 元，所有持仓和成交记录将清空。')) return;
    const acc = {
        cash: 100000,
        positions: {},
        trade_history: [],
        last_date: new Date().toISOString().slice(0, 10)
    };
    saveAshareLiveAccount(acc);
    hideAshareBalanceModal();
    renderAshareLiveAccount();
    // 账户重置后图上不应再残留旧的买入/卖出标记
    updateAshareLiveTradeMarkers();
    alert('A 股模拟账户已重置恢复至初始 100,000 元现金！');
}

let ashareSearchDebounceTimer = null;
let ashareSearchEventsBound = false;

function initAshareSearchModalEvents() {
    if (ashareSearchEventsBound) return;
    const input = document.getElementById('ashare-search-input');
    if (input) {
        ashareSearchEventsBound = true;
        input.addEventListener('input', () => {
            if (ashareSearchDebounceTimer) clearTimeout(ashareSearchDebounceTimer);
            const query = input.value.trim();
            if (!query) {
                document.getElementById('ashare-search-results').innerHTML = '';
                return;
            }
            ashareSearchDebounceTimer = setTimeout(async () => {
                try {
                    const res = await fetch(`/api/ashare/live/search?q=${encodeURIComponent(query)}`);
                    const results = await res.json();
                    renderAshareSearchResults(results);
                } catch (e) {
                    console.warn('搜索股票失败:', e);
                }
            }, 250);
        });
    }
}

function renderAshareSearchResults(results) {
    const container = document.getElementById('ashare-search-results');
    if (!container) return;
    if (!results || results.length === 0) {
        container.innerHTML = '<div style="padding: 12px; text-align: center; color: var(--crypto-muted, #848e9c); font-size: 12px;">未找到匹配标的</div>';
        return;
    }

    const currentList = getAshareWatchlist();
    const html = results.map(st => {
        const normCode = String(st.code).replace(/^(sh|sz|bj)/i, '');
        const isAdded = currentList.some(item => (st.symbol ? item.symbol === st.symbol : String(item.code).replace(/^(sh|sz|bj)/i, '') === normCode));
        const tag = getAshareMarketTag(st.code, false);

        return `
            <div class="ashare-search-item" data-symbol="${st.symbol || ''}" data-code="${st.code}" data-name="${st.name}">
                <div class="ashare-search-item-info">
                    <span class="ashare-wl-tag ${tag.cls}">${tag.text}</span>
                    <span class="ashare-search-item-code">${st.code}</span>
                    <span class="ashare-search-item-name">${st.name}</span>
                </div>
                <div>
                    <button class="ashare-search-add-btn ${isAdded ? 'added' : ''}" data-code="${st.code}" data-name="${st.name}" data-symbol="${st.symbol || ''}">
                        ${isAdded ? '已在自选' : '+ 自选'}
                    </button>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = html;

    // 点击行切换股票并关闭弹窗
    container.querySelectorAll('.ashare-search-item').forEach(item => {
        item.addEventListener('click', async (e) => {
            if (e.target.closest('.ashare-search-add-btn')) return;
            const sym = item.dataset.symbol || item.dataset.code;
            const name = item.dataset.name;
            hideAshareSearchModal();
            await switchAshareLiveStock(sym, name);
            renderAshareWatchlist();
            requestAnimationFrame(resizeCharts);
        });
    });

    // 点击 "+ 自选" 按钮
    container.querySelectorAll('.ashare-search-add-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (btn.classList.contains('added')) return;
            const code = btn.dataset.code;
            const name = btn.dataset.name;
            const symbol = btn.dataset.symbol;
            addStockToAshareWatchlist(code, name, symbol);
            btn.classList.add('added');
            btn.textContent = '已在自选';
        });
    });
}

function showAshareSearchModal() {
    initAshareSearchModalEvents();
    const modal = document.getElementById('ashare-search-modal');
    if (modal) {
        modal.classList.remove('hidden');
        const input = document.getElementById('ashare-search-input');
        if (input) {
            input.value = '';
            input.focus();
        }
        document.getElementById('ashare-search-results').innerHTML = '';
    }
}

function hideAshareSearchModal() {
    document.getElementById('ashare-search-modal')?.classList.add('hidden');
}

function showAshareBalanceModal() {
    const modal = document.getElementById('ashare-balance-modal');
    if (!modal) return;
    const acc = getAshareLiveAccount();
    const pos = getAsharePosition(acc, currentAshareSymbol);
    const availShares = computeAshareAvailShares
        ? computeAshareAvailShares(pos)
        : Math.max(0, pos.total_shares - (pos.frozen_today || 0) - (pos.frozen_sell || 0));

    const cashInput = document.getElementById('ashare-modal-cash');
    if (cashInput) cashInput.value = Math.round(acc.cash);
    const sharesInput = document.getElementById('ashare-modal-avail-shares');
    if (sharesInput) sharesInput.value = availShares;
    const costInput = document.getElementById('ashare-modal-avg-cost');
    if (costInput) costInput.value = Number(pos.avg_cost || currentAsharePrice || 0).toFixed(2);

    modal.classList.remove('hidden');
}

function hideAshareBalanceModal() {
    document.getElementById('ashare-balance-modal')?.classList.add('hidden');
}

function saveAshareBalanceModal() {
    const cash = parseFloat(document.getElementById('ashare-modal-cash')?.value) || 0;
    const shares = parseInt(document.getElementById('ashare-modal-avail-shares')?.value, 10) || 0;
    const cost = parseFloat(document.getElementById('ashare-modal-avg-cost')?.value) || 0;

    if (shares % 100 !== 0) {
        alert('持仓股数必须是 100 股（1手）的整数倍！');
        return;
    }

    const acc = getAshareLiveAccount();
    acc.cash = Math.max(0, cash);
    const posKey = findAsharePositionKey(acc, currentAshareSymbol) || currentAshareSymbol;
    acc.positions[posKey] = {
        total_shares: shares,
        available_shares: shares,
        frozen_today: 0, // 手动设定的持仓默认作为可用持仓
        avg_cost: cost,
        name: currentAshareName,
        symbol: currentAshareSymbol
    };
    saveAshareLiveAccount(acc);
    hideAshareBalanceModal();
    renderAshareLiveAccount();
    renderAshareWatchlist();
    alert('模拟账户资产与持仓已更新生效！');
}

function exitAshareLiveWatch() {
    stopAshareLivePolling();
    setChartFocusMode(false);
    isAshareLiveMode = false;
    const mainApp = document.getElementById('main-app');
    mainApp?.classList.remove('ashare-live-active', 'crypto-training-active', 'ashare-watchlist-collapsed');
    document.getElementById('training-interface')?.classList.remove('crypto-workspace-active');
    document.getElementById('training-interface')?.classList.add('hidden');
    document.getElementById('ashare-live-search-btn')?.classList.add('hidden');
    document.getElementById('ashare-live-exit-btn')?.classList.add('hidden');
    document.getElementById('ashare-wl-expand-btn')?.classList.add('hidden');
    document.getElementById('ashare-adjust-balance-btn')?.classList.add('hidden');
    document.getElementById('ashare-live-status-badge')?.classList.add('hidden');
    document.getElementById('ashare-live-header-metrics')?.classList.add('hidden');
    document.getElementById('ashare-header-change')?.classList.add('hidden');
    document.getElementById('ashare-live-market-status')?.classList.add('hidden');
    // 价格预警：退出看盘时收掉按钮与图上的预警线/标签（数据已按标的持久化，下次进入自动恢复）
    document.getElementById('alert-add-btn')?.classList.add('hidden');
    clearAshareAlertVisuals();
    document.querySelectorAll('[data-ashare-live-only]').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.ashare-live-period').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.shared-view-period').forEach(el => el.classList.remove('hidden'));
    if (!isCryptoMode()) {
        document.getElementById('crypto-theme-toggle-btn')?.classList.add('hidden');
        document.getElementById('crypto-console-collapse-btn')?.classList.add('hidden');
        document.getElementById('crypto-console-collapsed-tab')?.classList.add('hidden');
    }

    const playbackControls = document.querySelector('.playback-controls');
    if (playbackControls) playbackControls.classList.remove('hidden');
    const speedControl = document.querySelector('.speed-control');
    if (speedControl) speedControl.classList.remove('hidden');

    // 恢复进入 A股实时看盘前的副图/指标用户状态（与 launchAshareLiveWatch 的快照对称）
    if (asharePreLiveUiState) {
        const pre = asharePreLiveUiState;
        asharePreLiveUiState = null;
        indicatorPanelVisible = Boolean(pre.indicatorPanelVisible);
        currentIndicatorType = pre.currentIndicatorType || 'MACD';
        const indPanelRestore = document.getElementById('indicator-chart');
        if (indPanelRestore) {
            indPanelRestore.style.display = pre.indicatorDisplay || '';
            indPanelRestore.classList.toggle('panel-collapsed', Boolean(pre.indicatorCollapsed));
        }
        const volPanelRestore = document.getElementById('volume-chart');
        if (volPanelRestore) {
            volPanelRestore.classList.toggle('panel-collapsed', Boolean(pre.volumeCollapsed));
        }
        const indBtnRestore = document.getElementById('toggle-indicator-panel-btn');
        if (indBtnRestore) {
            indBtnRestore.classList.toggle('active', indicatorPanelVisible);
            indBtnRestore.setAttribute('aria-expanded', String(indicatorPanelVisible));
        }
        const indicatorSelectRestore = document.getElementById('indicator-select');
        if (indicatorSelectRestore) indicatorSelectRestore.value = currentIndicatorType;
        updateIndicatorHeaderLabel();
        renderIndicatorLibrary();
        renderActiveIndicatorTags();
        // 若恢复为可见，重载指标绘图数据；面板高度状态复位后重排图表
        if (indicatorPanelVisible) {
            loadTechnicalIndicator(currentIndicatorType);
        }
        requestAnimationFrame(() => {
            applyChartPanelRatios(readChartPanelRatios());
            resizeCharts();
        });
    }

    toggleToolbarForTraining(false);
    document.getElementById('history-dashboard')?.classList.remove('hidden');
}