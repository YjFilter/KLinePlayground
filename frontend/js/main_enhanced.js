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
let isPlaying = false;
let playbackInterval = null;
let currentTraining = null;
let currentIndicatorType = 'MACD';
let currentIndicatorSeries = [];
let bollSeries = {}; // 用于存储BOLL指标线
let autoSyncInterval = null;
let lastKnownBarId = null;
let lastKnownTradeCount = null;
let maPeriods = [5, 10, 20]; // 默认MA周期
let isShiftClicked = false;
let isShiftKeyPressed = false;
let currentTheme = localStorage.getItem('uiTheme') || 'light';
let currentCryptoTheme = localStorage.getItem('cryptoUiTheme') || 'dark';
let currentPeriod = 'daily';
let currentOrderType = 'market';
let availableDataSources = [];
let latestRenderedKlineData = [];
let trainingSetupReturnScreen = 'main';
let currentReportData = null;
let currentHistoryFilter = 'all';
let isViewOnlyMode = false;
let skipTradeReasonPrompt = false;
let pendingTradeReasonAction = null;
let chartWindowState = createEmptyChartWindowState();
let chartWindowRequestChain = Promise.resolve();
let chartWindowRequestGeneration = 0;
let chartWindowLoadingDirection = null;
let chartPanelResizeObserver = null;
let chartPanelResizeFrame = null;
let chartPanelResizing = false;
let activeChartPanelSplitter = null;
let chartPanelRatios = null;
let drawingController = null;
let drawingUiAbortController = null;
let selectedTrainingMarketType = 'a_share';
let selectedCryptoInstrument = null;
let cryptoInstrumentSearchTimer = null;
let periodSwitchAbortController = null;
let periodSwitchGeneration = 0;
let periodSwitchFeedbackTimer = null;
let cryptoPeriodSnapshotCacheTrainingId = null;
let cryptoOrderConstraints = null;
let cryptoOrderSubmitting = false;
let cryptoNextInFlight = false;
let cryptoFeeSubmitting = false;
let cryptoHistoryPrepareJobId = null;
let cryptoHistoryPrepareAbortController = null;
let cryptoHistoryPrepareRetryConfig = null;
let cryptoEarlierSegmentLoading = false;
let cryptoEarlierSegmentGeneration = 0;
const PERIOD_LOADING_DELAY_MS = 150;
const CRYPTO_PERIOD_SNAPSHOT_CACHE_LIMIT = 8;
const cryptoPeriodSnapshotCache = new Map();
const CHART_PANEL_STORAGE_KEY = 'kline-chart-panel-heights-v2';
const CHART_PANEL_DEFAULT_RATIOS = { chart: 0.72, 'volume-chart': 0.11, 'indicator-chart': 0.17 };
const CHART_PANEL_MIN_HEIGHTS = { chart: 160, 'volume-chart': 32, 'indicator-chart': 52 };
function createEmptyChartWindowState() {
    return {
        kline_data: [],
        volume_data: [],
        trade_markers: [],
        window_start: null,
        window_end: null,
        history_start: null,
        history_end: null,
        render_start: null,
        render_end: null,
        has_earlier_render: false,
        training_start: null,
        training_end: null,
        has_earlier: false,
        has_later: false,
        extended_history: false,
        read_only: false,
        period: 'daily',
    };
}

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

function clearCryptoPeriodSnapshotCache() {
    cryptoPeriodSnapshotCache.clear();
    cryptoPeriodSnapshotCacheTrainingId = currentTraining?.id === undefined || currentTraining?.id === null
        ? null
        : String(currentTraining.id);
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

function buildCryptoPeriodSnapshotCacheKey(trainingId, period, replayTime, windowState = chartWindowState) {
    const expandedWindow = Boolean(windowState?.extended_history);
    const windowStart = expandedWindow ? cryptoPeriodSnapshotCacheTimestamp(windowState.window_start) : '';
    const windowEnd = expandedWindow ? cryptoPeriodSnapshotCacheTimestamp(windowState.window_end) : '';
    const historyStart = cryptoPeriodSnapshotCacheTimestamp(windowState?.history_start);
    const historyEnd = cryptoPeriodSnapshotCacheTimestamp(windowState?.history_end);
    const renderStart = cryptoPeriodSnapshotCacheTimestamp(windowState?.render_start);
    const renderEnd = cryptoPeriodSnapshotCacheTimestamp(windowState?.render_end);
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

// === Intraday 多周期回放 (TASK-013) ===
// data_mode 标识: 来自 /api/training/start 响应的 currentTraining.data_mode。
// 仅当 data_mode === INTRADAY_DATA_MODE 时走新的 intraday 路径，
// 其余情况一律沿用原 legacy_daily JavaScript 路径。
const INTRADAY_DATA_MODE = 'intraday_30m';
const INTRADAY_PERIODS = ['30m', '4h_session', 'daily', 'weekly'];
const CRYPTO_MARKET_TYPE = 'crypto_perpetual';
const CRYPTO_DATA_MODE = 'crypto_5m';
const CRYPTO_PERIODS = ['5m', '15m', '30m', '1h', '4h', 'daily', 'weekly'];

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
    return isCryptoMode() || selectedTrainingMarketType === CRYPTO_MARKET_TYPE
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

// 将周期值转换为可读的徽章文字。
function formatIntradayPeriodBadge(period) {
    switch (period) {
        case '5m': return '5m';
        case '15m': return '15m';
        case '30m': return '30m';
        case '1h': return '1h';
        case '4h': return '4h';
        case '4h_session': return '4h';
        case 'weekly': return '周K';
        case 'daily':
        default: return '日K';
    }
}

// start / data / period 返回顶层 snapshot；next / reset 把 snapshot 嵌在 response.snapshot。
// 此函数统一提取 snapshot 对象。
function extractIntradaySnapshot(response) {
    if (!response || typeof response !== 'object') return null;
    if (response.snapshot && typeof response.snapshot === 'object') {
        return response.snapshot;
    }
    return response;
}

// 把市场墙上时间转换为 lightweight-charts 的 UTCTimestamp。
// lightweight-charts 使用 UTC 字段绘制标签，因此这里用 Date.UTC 保留 10:00 等原始盘中时间，
// 不把北京时间换算成 02:00 UTC。
function intradayBarToTimestamp(bar) {
    if (!bar) return 0;
    const raw = bar.start_time || bar.end_time || bar.time || bar.datetime;
    if (typeof raw === 'number') return raw;
    if (!raw) return 0;
    const match = String(raw).match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
    if (!match) return 0;
    return Math.floor(Date.UTC(
        Number(match[1]),
        Number(match[2]) - 1,
        Number(match[3]),
        Number(match[4] || 0),
        Number(match[5] || 0),
        Number(match[6] || 0)
    ) / 1000);
}

// 把 intraday snapshot.kline_data 转成 lightweight-charts 所需的蜡烛数据格式。
function buildIntradayKlineChartData(klineData) {
    if (!Array.isArray(klineData)) return [];
    return klineData.map(function (bar) {
        return {
            time: intradayBarToTimestamp(bar),
            open: Number(bar.open),
            high: Number(bar.high),
            low: Number(bar.low),
            close: Number(bar.close),
            volume: Number(bar.volume) || 0,
        };
    });
}

// intraday snapshot 没有独立的 volume_data，从每根 K 线的 volume 字段构造。
function buildIntradayVolumeData(klineData) {
    if (!Array.isArray(klineData)) return [];
    return klineData.map(function (bar) {
        const isUp = Number(bar.close) >= Number(bar.open);
        return {
            time: intradayBarToTimestamp(bar),
            value: Number(bar.volume) || 0,
            color: isUp ? '#ff4d4f' : '#008000',
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

    candlestickSeries.setData(chartData);
    volumeSeries.setData(volumeData);
    replaceRenderedKlineData(chartData);
    loadTechnicalIndicator(currentIndicatorType);

    // 清空均线系列，intraday 模式不计算 MA
    maPeriods.forEach(function (p) {
        if (maSeries[p]) maSeries[p].setData([]);
    });
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

const THEME_PALETTES = {
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
    }
};

function getThemePalette() {
    const activeTheme = isCryptoMode() ? currentCryptoTheme : currentTheme;
    return THEME_PALETTES[activeTheme] || THEME_PALETTES.light;
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
        // 兼容四个 intraday 周期与 legacy 的 daily/weekly
        badge.textContent = formatIntradayPeriodBadge(currentPeriod);
    }
    document.querySelectorAll('.view-period-btn').forEach((button) => {
        button.classList.toggle('active', button.dataset.period === currentPeriod);
    });
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
            downColor: palette.negative,
            borderUpColor: palette.positive,
            borderDownColor: palette.negative,
            wickUpColor: palette.positive,
            wickDownColor: palette.negative,
        });
    }
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
        if (maSeries[p]) {
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
            items.push({ label: 'UP', color: '#ff6b6b' });
            items.push({ label: 'MID', color: '#4ecdc4' });
            items.push({ label: 'LOW', color: '#45b7d1' });
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

    // 训练设置相关
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
    document.getElementById('theme-toggle-btn')?.addEventListener('click', () => {
        applyTheme(currentTheme === 'dark' ? 'light' : 'dark', true, true);
    });
    document.getElementById('crypto-theme-toggle-btn')?.addEventListener('click', toggleCryptoTheme);
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
    });

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
    document.querySelectorAll('[data-crypto-action]').forEach((button) => {
        button.addEventListener('click', () => selectCryptoOrderAction(button.dataset.cryptoAction));
    });
    document.getElementById('toggle-volume-panel-btn')?.addEventListener('click', () => toggleChartPanel('volume-chart'));
    document.getElementById('toggle-indicator-panel-btn')?.addEventListener('click', () => toggleChartPanel('indicator-chart'));
    document.getElementById('chart-fullscreen-btn')?.addEventListener('click', toggleChartFullscreen);
    document.getElementById('chart-focus-exit-btn')?.addEventListener('click', () => setChartFocusMode(false));

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
            case 'enter':
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

function readChartPanelRatios() {
    if (chartPanelRatios) return chartPanelRatios;
    try {
        chartPanelRatios = normalizeChartPanelRatios(JSON.parse(localStorage.getItem(CHART_PANEL_STORAGE_KEY) || 'null'));
    } catch (error) {
        chartPanelRatios = normalizeChartPanelRatios(null);
    }
    return chartPanelRatios;
}

function persistChartPanelRatios() {
    if (!chartPanelRatios) return;
    localStorage.setItem(CHART_PANEL_STORAGE_KEY, JSON.stringify(chartPanelRatios));
}

function setChartPanelHeight(panel, height) {
    if (!panel || !Number.isFinite(height)) return;
    panel.style.flex = `0 0 ${Math.round(height)}px`;
    panel.style.height = `${Math.round(height)}px`;
}

function getChartPanelAvailableHeight(container) {
    const splitterHeight = Array.from(container.querySelectorAll('.chart-panel-splitter'))
        .reduce((sum, splitter) => sum + splitter.getBoundingClientRect().height, 0);
    return Math.max(0, container.clientHeight - splitterHeight);
}

function applyChartPanelRatios(candidateRatios) {
    const { container, panels } = getChartPanelElements();
    if (!container || container.clientHeight <= 0) return;
    chartPanelRatios = normalizeChartPanelRatios(candidateRatios || readChartPanelRatios());
    const availableHeight = getChartPanelAvailableHeight(container);
    if (availableHeight <= 0) return;

    const panelIds = Object.keys(panels);
    const heights = {};
    panelIds.forEach((panelId) => {
        heights[panelId] = Math.max(CHART_PANEL_MIN_HEIGHTS[panelId], availableHeight * chartPanelRatios[panelId]);
    });

    let overflow = panelIds.reduce((sum, panelId) => sum + heights[panelId], 0) - availableHeight;
    ['chart', 'indicator-chart', 'volume-chart'].forEach((panelId) => {
        if (overflow <= 0) return;
        const reducible = Math.max(0, heights[panelId] - CHART_PANEL_MIN_HEIGHTS[panelId]);
        const reduction = Math.min(reducible, overflow);
        heights[panelId] -= reduction;
        overflow -= reduction;
    });
    if (overflow < 0) heights.chart += Math.abs(overflow);

    panelIds.forEach((panelId) => setChartPanelHeight(panels[panelId], heights[panelId]));
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
const CRYPTO_CONSOLE_DEFAULT_WIDTH = 340;
const CRYPTO_CONSOLE_MIN_WIDTH = 280;
const CRYPTO_CONSOLE_MAX_WIDTH = 520;

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
        const chartContainer = document.getElementById('chart');
        const volumeContainer = document.getElementById('volume-chart');
        const indicatorContainer = document.getElementById('indicator-canvas');

        if (chartContainer.clientWidth > 0 && chartContainer.clientHeight > 0) {
            chart.resize(chartContainer.clientWidth, chartContainer.clientHeight);
        }
        if (volumeContainer.clientWidth > 0 && volumeContainer.clientHeight > 0) {
            volumeChart.resize(volumeContainer.clientWidth, volumeContainer.clientHeight);
        }
        if (indicatorContainer.clientWidth > 0 && indicatorContainer.clientHeight > 0) {
            indicatorChart.resize(indicatorContainer.clientWidth, indicatorContainer.clientHeight);
        }
        
        scheduleChipDistributionRender();
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
}

function renderMaPeriodsEditor() {
    const container = document.getElementById('ma-periods-editor');
    if (!container) return;
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
            maPeriods = [5, 10, 20];
        }
        renderMaPeriodsEditor();

        // 加载指标配置
        if (settings.indicators) {
            const ind = settings.indicators;
            if (ind.macd) {
                document.getElementById('macd-fast').value = ind.macd.fast || 12;
                document.getElementById('macd-slow').value = ind.macd.slow || 26;
                document.getElementById('macd-signal').value = ind.macd.signal || 9;
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
                fast: parseInt(document.getElementById('macd-fast').value) || 12,
                slow: parseInt(document.getElementById('macd-slow').value) || 26,
                signal: parseInt(document.getElementById('macd-signal').value) || 9
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
        periodSelect.value = crypto ? '5m' : 'daily';
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
    if (active) {
        applyCryptoTheme(currentCryptoTheme, false, false);
        applyCryptoConsoleLayout(readCryptoConsoleLayout());
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
    refreshCryptoOrderPreview();
    refreshCryptoTpSlPnl();
}

function toggleChartPanel(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    const collapsed = panel.classList.toggle('panel-collapsed');
    const button = document.querySelector('[aria-controls="' + panelId + '"]');
    button?.classList.toggle('active', !collapsed);
    button?.setAttribute('aria-expanded', String(!collapsed));
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
    document.getElementById('chart-focus-exit-btn')?.classList.toggle('hidden', !active);
    requestAnimationFrame(resizeCharts);
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
        : `${message || '历史数据准备失败'}。请检查网络或数据源后重试。`;
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
    const payload = {
        user: currentUser,
        market_type: CRYPTO_MARKET_TYPE,
        data_mode: CRYPTO_DATA_MODE,
        mode: isRandomMode ? 'random' : 'specified',
        data_source: 'binance',
        period: getSelectedKlinePeriod(),
        max_training_days: parseInt(document.getElementById('max-training-bars')?.value) || 0,
        initial_capital: parseFloat(document.getElementById('crypto-initial-capital')?.value) || 10000,
        leverage: parseInt(document.getElementById('crypto-leverage')?.value) || 5,
        history_years: getCryptoHistoryYears(),
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

function replaceRenderedKlineData(klineData) {
    latestRenderedKlineData = Array.isArray(klineData) ? klineData.map(item => ({ ...item })) : [];
    syncDrawingToolBars();
}

function upsertRenderedBar(bar) {
    if (!bar) return;
    if (latestRenderedKlineData.length === 0) {
        latestRenderedKlineData = [{ ...bar }];
        syncDrawingToolBars();
        return;
    }

    const lastBar = latestRenderedKlineData[latestRenderedKlineData.length - 1];
    if (lastBar.time === bar.time) {
        latestRenderedKlineData[latestRenderedKlineData.length - 1] = { ...bar };
        syncDrawingToolBars();
        return;
    }

    latestRenderedKlineData.push({ ...bar });
    syncDrawingToolBars();
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

function syncDrawingToolbarState(tool = null) {
    document.querySelectorAll('[data-drawing-tool]').forEach((button) => {
        const aliases = { 'long-position': 'long', 'short-position': 'short' };
        const active = (aliases[button.dataset.drawingTool] || button.dataset.drawingTool) === tool;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
    });
}

function clearSessionDrawings() {
    drawingController?.resetAll?.();
    drawingController?.cancelGesture?.();
    setDrawingInteractionState(false);
    syncDrawingToolbarState(null);
    setDrawingStatus('');
}

function invokeDrawingAction(action) {
    if (!drawingController) return;
    const methodMap = {
        lock: 'toggleLock',
        hide: 'toggleHidden',
        delete: 'deleteSelected',
        undo: 'undo',
        redo: 'redo',
        clear: 'clearAll',
    };
    const method = methodMap[action];
    if (method && typeof drawingController[method] === 'function') drawingController[method]();
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
    const fallback = window.KLineDrawingTools?.resetFibonacciLevels?.() || [];
    const settings = selected || { levels: fallback, reverse: false };
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

function initializeDrawingTools() {
    destroyDrawingTools();
    drawingUiAbortController = new AbortController();
    const drawingUiSignal = drawingUiAbortController.signal;
    const api = window.KLineDrawingTools;
    const Controller = api?.DrawingController;
    if (!Controller || !chart || !candlestickSeries) return;
    drawingController = new Controller({
        chart,
        series: candlestickSeries,
        element: document.getElementById('chart'),
        bars: latestRenderedKlineData,
        accountSizeProvider: () => Number(currentTraining?.account?.equity ?? currentTraining?.initial_capital ?? 0),
        onError: (error) => {
            setDrawingStatus(error?.message || '画线失败，请在K线区域内重试。', 'error');
            setDrawingInteractionState(false);
            syncDrawingToolbarState(null);
        },
        onInteractionChange: (active) => setDrawingInteractionState(active),
        onToolChange: (tool) => syncDrawingToolbarState(tool),
    });

    document.querySelectorAll('[data-drawing-tool]').forEach((button) => {
        if (button.dataset.drawingBound === '1') return;
        button.dataset.drawingBound = '1';
        button.addEventListener('click', () => {
            const toolAliases = { 'long-position': 'long', 'short-position': 'short' };
            const tool = toolAliases[button.dataset.drawingTool] || button.dataset.drawingTool;
            try {
                drawingController?.activateTool?.(tool);
                syncDrawingToolbarState(tool);
                setDrawingStatus(tool === 'select' ? '选择并拖动已有图形。' : '按住并拖动鼠标创建图形。', 'active');
            } catch (error) {
                setDrawingStatus(error?.message || '无法启用画线工具。', 'error');
                syncDrawingToolbarState(null);
            }
            document.getElementById('drawing-fibonacci-settings')?.classList.toggle(
                'hidden', button.dataset.drawingTool !== 'fibonacci'
            );
            if (button.dataset.drawingTool === 'fibonacci') renderFibonacciSettingsPanel();
        });
    });
    document.querySelectorAll('[data-drawing-action]').forEach((button) => {
        if (button.dataset.drawingBound === '1') return;
        button.dataset.drawingBound = '1';
        button.addEventListener('click', () => invokeDrawingAction(button.dataset.drawingAction));
    });
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
    document.getElementById('chart')?.addEventListener('pointerup', () => {
        if (!document.getElementById('drawing-fibonacci-settings')?.classList.contains('hidden')) {
            setTimeout(renderFibonacciSettingsPanel, 0);
        }
    }, { signal: drawingUiSignal });
    syncDrawingToolBars();
}

function shiftLogicalRange(range, delta = 1) {
    if (!range) return null;
    return {
        from: range.from + delta,
        to: range.to + delta
    };
}

function setVisibleRangeAll(range) {
    if (!range) return;
    chart?.timeScale().setVisibleLogicalRange(range);
    volumeChart?.timeScale().setVisibleLogicalRange(range);
    indicatorChart?.timeScale().setVisibleLogicalRange(range);
}

function setVisibleTimeRangeAll(range) {
    [chart, volumeChart, indicatorChart].forEach((item) => {
        if (!item) return;
        if (range) item.timeScale().setVisibleRange(range);
        else item.timeScale().fitContent();
    });
}
function normalizeChartTime(item) {
    if (!item) return 0;
    if (typeof item.time === 'number') return item.time;
    const rawTime = item.time || item.timestamp || item.end_time || item.start_time || item.datetime;
    return intradayBarToTimestamp({ time: rawTime });
}

function normalizeChartCandle(item) {
    return {
        time: normalizeChartTime(item),
        open: Number(item.open),
        high: Number(item.high),
        low: Number(item.low),
        close: Number(item.close),
        volume: Number(item.volume) || 0,
    };
}

function normalizeChartVolume(item) {
    return {
        time: normalizeChartTime(item),
        value: Number(item.value ?? item.volume) || 0,
        color: item.color || '#999999',
    };
}

function normalizeChartMarker(marker) {
    return {
        ...marker,
        time: normalizeChartTime(marker),
    };
}

function mergeTimedItems(existingItems, incomingItems, normalizer) {
    const merged = new Map();
    [...(existingItems || []), ...(incomingItems || [])].forEach((item) => {
        const normalized = normalizer(item);
        if (normalized.time) merged.set(normalized.time, normalized);
    });
    return Array.from(merged.values()).sort((left, right) => left.time - right.time);
}

function normalizeTradeMarkers(markers) {
    return (markers || [])
        .map(normalizeChartMarker)
        .filter((marker) => marker.time)
        .sort((left, right) => left.time - right.time);
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

function mergeChartWindow(existing, incoming) {
    const base = existing || createEmptyChartWindowState();
    const next = incoming || {};
    const normalizeCandle = (item) => ({ ...normalizeChartCandle(item), time: normalizeChartTime(item) });
    const normalizeVolume = (item) => ({ ...normalizeChartVolume(item), time: normalizeChartTime(item) });
    return {
        ...base,
        ...next,
        kline_data: mergeTimedItems(base.kline_data, next.kline_data, normalizeCandle),
        volume_data: mergeTimedItems(base.volume_data, next.volume_data, normalizeVolume),
        trade_markers: next.trade_markers !== undefined
            ? normalizeTradeMarkers(next.trade_markers)
            : normalizeTradeMarkers(base.trade_markers),
    };
}

function parseChartWindowTimestamp(value) {
    if (value instanceof Date) {
        return Number.isFinite(value.getTime()) ? new Date(value.getTime()) : null;
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
        return new Date(value < 1e12 ? value * 1000 : value);
    }
    if (!value) return null;
    const numericValue = Number(value);
    if (/^\d+(?:\.\d+)?$/.test(String(value)) && Number.isFinite(numericValue)) {
        return new Date(numericValue < 1e12 ? numericValue * 1000 : numericValue);
    }
    const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
    if (!match) return null;
    return new Date(Date.UTC(
        Number(match[1]), Number(match[2]) - 1, Number(match[3]),
        Number(match[4] || 0), Number(match[5] || 0), Number(match[6] || 0)
    ));
}

function formatChartWindowTimestamp(date) {
    const pad = (value) => String(value).padStart(2, '0');
    return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}`;
}

function shiftChartWindowYear(value, yearDelta) {
    const date = parseChartWindowTimestamp(value);
    if (!date) return value;
    const originalMonth = date.getUTCMonth();
    date.setUTCFullYear(date.getUTCFullYear() + yearDelta);
    if (date.getUTCMonth() !== originalMonth) date.setUTCDate(0);
    return formatChartWindowTimestamp(date);
}

function earlierChartWindowTimestamp(left, right) {
    if (!left) return right || null;
    if (!right) return left;
    return parseChartWindowTimestamp(left) <= parseChartWindowTimestamp(right) ? left : right;
}

function laterChartWindowTimestamp(left, right) {
    if (!left) return right || null;
    if (!right) return left;
    return parseChartWindowTimestamp(left) >= parseChartWindowTimestamp(right) ? left : right;
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
    replaceRenderedKlineData(merged.kline_data);
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
    const volumeData = (snapshot.kline_data || []).map((bar) => ({
        time: bar.end_time || bar.start_time || bar.time,
        value: Number(bar.volume) || 0,
        color: Number(bar.close) >= Number(bar.open) ? '#ff4d4f' : '#008000',
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
    });
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

    candlestickSeries.setData(data.kline_data);
    volumeSeries.setData(data.volume_data || []);
    replaceRenderedKlineData(data.kline_data);

    if (data.ma_data) {
        maPeriods.forEach(p => {
            if (maSeries[p]) {
                maSeries[p].setData(data.ma_data[p] || []);
            }
        });
    }

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
    await loadTechnicalIndicator(currentIndicatorType);
    if (visibleRange !== null) {
        setVisibleRangeAll(visibleRange);
    }
    await updateChipDistribution();
}

function applyCryptoPeriodSnapshot(snapshot, nextPeriod, visibleRange, hadExtendedHistory) {
    applyIntradaySnapshot(snapshot, { fitContent: false });
    currentTraining.period = nextPeriod;
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
    const canRestoreRange = visibleRange && Number.isFinite(renderedStart) && Number.isFinite(renderedEnd)
        && visibleRange.from >= renderedStart && visibleRange.to <= renderedEnd;
    requestAnimationFrame(() => {
        if (canRestoreRange) setVisibleTimeRangeAll(visibleRange);
        else setVisibleTimeRangeAll(null);
    });
}

function isFineCryptoPeriod(period) {
    return period === '5m' || period === '15m';
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
    clearCryptoPeriodSnapshotCache();
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
    if (currentPeriod === nextPeriod && currentTraining?.id) {
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
        endPeriodSwitchFeedback();
        applyCryptoPeriodSnapshot(cachedSnapshot, nextPeriod, visibleRange, hadExtendedHistory);
        setChartWindowStatus('已从缓存切换到 ' + formatIntradayPeriodBadge(nextPeriod) + '。', 'success');
        return;
    }
    beginPeriodSwitchFeedback(nextPeriod);
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
        applyCryptoPeriodSnapshot(snapshot, nextPeriod, visibleRange, hadExtendedHistory);
        setChartWindowStatus('已切换到 ' + formatIntradayPeriodBadge(nextPeriod) + '。', 'success');
    } catch (error) {
        if (error?.name === 'AbortError') return;
        console.error('切换币圈周期失败:', error);
        setChartWindowStatus(error.message || '切换币圈周期失败。', 'error');
    } finally {
        if (requestGeneration === periodSwitchGeneration) endPeriodSwitchFeedback();
    }
}

async function switchViewPeriod(period) {
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
            currentTraining.period = period;
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
            const error = await response.json();
            alert(error.error || error.message || '开始训练失败');
        }
    } catch (error) {
        console.error('开始训练失败:', error);
        alert('开始训练失败');
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

// 图表管理
function initializeChart() {
    destroyDrawingTools();
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
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: palette.border,
            minimumWidth: 80,
        },
        // 使用 localization 选项来格式化十字标线的时间
        localization: {
            // timeFormatter 用于格式化十字标线悬浮窗中的时间
            timeFormatter: (businessDay) => {
                // businessDay 是一个 Date 对象，包含了年、月、日
                // 注意：这里的 businessDay 是一个 UTC 日期对象，所以使用 getUTCFullYear 等方法可以避免时区问题
                const date = new Date(businessDay * 1000);

                const year = date.getUTCFullYear();
                const month = ('0' + (date.getUTCMonth() + 1)).slice(-2); // 月份从0开始
                const day = ('0' + date.getUTCDate()).slice(-2);

                return `${year}年${month}月${day}日`;
            },
            locale: 'zh-CN',
        },
        timeScale: {
            borderColor: palette.border,
            timeVisible: true,
            secondsVisible: false,
            tickMarkFormatter: (time) => {
                const date = new Date(time * 1000);
                return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
            }
        },
    });

    // 添加K线系列
    candlestickSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
        upColor: 'rgba(255, 77, 79, 0)',
        downColor: palette.negative,
        borderUpColor: palette.positive,
        borderDownColor: palette.negative,
        wickUpColor: palette.positive,
        wickDownColor: palette.negative,
        borderVisible: true,
    });
    candlestickSeries.applyOptions({ lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });

    // 添加移动平均线
    maPeriods.forEach((p, index) => {
        maSeries[p] = chart.addSeries(LightweightCharts.LineSeries, {
            color: maColors[index % maColors.length],
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
            tickMarkFormatter: (time) => {
                const date = new Date(time * 1000);
                return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
            }
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
    const indicatorContainer = document.getElementById('indicator-canvas');
    indicatorContainer.innerHTML = '';

    // 在图表容器内动态创建信息显示框
    const infoDisplay_2 = document.createElement('div');
    infoDisplay_2.id = 'indicator-info-display';
    infoDisplay_2.className = 'chart-info-display';
    indicatorContainer.appendChild(infoDisplay_2);

    const indicatorLegend = document.createElement('div');
    indicatorLegend.id = 'indicator-legend';
    indicatorLegend.className = 'chart-legend';
    indicatorContainer.appendChild(indicatorLegend);

    indicatorChart = LightweightCharts.createChart(indicatorContainer, {
        width: indicatorContainer.clientWidth,
        height: indicatorContainer.clientHeight,
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
            tickMarkFormatter: (time) => {
                const date = new Date(time * 1000);
                return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
            }
        },
    });

    // 监听主图表（K线图）的时间轴变化
    chart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
        if (timeRange) { // 增加一个 null 检查
            volumeChart.timeScale().setVisibleLogicalRange(timeRange);
            indicatorChart.timeScale().setVisibleLogicalRange(timeRange);
            maybeLoadEarlierCryptoSegment(timeRange);
        }
        scheduleChipDistributionRender();
    });
    
    chart.timeScale().subscribeVisibleTimeRangeChange(() => {
        scheduleChipDistributionRender();
    });

    // 监听成交量图表的时间轴变化
    volumeChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
        if (timeRange) {
            chart.timeScale().setVisibleLogicalRange(timeRange);
            indicatorChart.timeScale().setVisibleLogicalRange(timeRange);
        }
    });

    // 监听技术指标图表的时间轴变化
    indicatorChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
        if (timeRange) {
            chart.timeScale().setVisibleLogicalRange(timeRange);
            volumeChart.timeScale().setVisibleLogicalRange(timeRange);
        }
    });

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
            infoEl.style.display = 'none';
            // 同步其他图表的十字准星
            syncCrosshair(volumeChart, volumeSeries, null);
            if (currentIndicatorSeries.length > 0) {
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
            const mData = param.seriesData.get(maSeries[p]);
            if (mData) {
                maHtml += `<span style="color: ${maSeries[p].options().color};">MA${p}:${mData.value.toFixed(2)} </span>`;
            }
        });
        maHtml += '</div>';

        // 获取并显示BOLL指标数据
        let bollHtml = '';
        // 检查BOLL指标是否处于激活状态 (通过检查bollSeries对象)
        if (currentIndicatorType === 'BOLL' && bollSeries.upper && bollSeries.middle && bollSeries.lower) {
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
        if (currentIndicatorSeries.length > 0) {
            syncCrosshair(indicatorChart, currentIndicatorSeries[0], dataPoint);
        }
    });

    volumeChart.subscribeCrosshairMove(param => {
        const dataPoint = getCrosshairDataPoint(volumeSeries, param);
        syncCrosshair(chart, candlestickSeries, dataPoint);
        if (currentIndicatorSeries.length > 0) {
            syncCrosshair(indicatorChart, currentIndicatorSeries[0], dataPoint);
        }
    });

    indicatorChart.subscribeCrosshairMove(param => {
        const infoEl = document.getElementById('indicator-info-display');
        if (!infoEl) return;

        // 如果十字准星移出图表或没有数据，则隐藏信息框
        if (!param.time || param.point.x < 0 || param.point.y < 0 || currentIndicatorSeries.length === 0) {
            infoEl.style.display = 'none';
            return;
        }

        infoEl.style.display = 'block';
        let indicatorHtml = '';

        // 根据当前指标类型，获取并格式化数据
        switch (currentIndicatorType) {
            case 'MACD':
                const difData = param.seriesData.get(currentIndicatorSeries[0]);
                const deaData = param.seriesData.get(currentIndicatorSeries[1]);
                const histData = param.seriesData.get(currentIndicatorSeries[2]);
                if (difData && deaData && histData) {
                    indicatorHtml = `
                        <div><strong>MACD</strong></div>
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
    });

    initializeDrawingTools();
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
        await loadTechnicalIndicator(currentIndicatorType);

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

function updateElementText(elementId, text, color) {
    const element = document.getElementById(elementId);
    if (!element) return;
    element.textContent = text;
    if (color) element.style.color = color;
}

function updateCurrentInfo(barData, progress) {
    if (!barData) return;
    const palette = getThemePalette();

    const date = new Date(barData.time * 1000);
    const formattedDate = `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
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
            position: cryptoStyle?.position || (shape === 'arrowDown' ? 'aboveBar' : 'belowBar'),
            color: cryptoStyle?.color || (marker.type === 'B' ? '#ff4d4f' : '#008000'),
            shape: cryptoStyle?.shape || shape,
            text: marker.type,
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
    clearCryptoPeriodSnapshotCache();
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
            requestAnimationFrame(() => loadTechnicalIndicator(currentIndicatorType));
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
        clearCryptoPeriodSnapshotCache();
        applyCryptoNextDelta(payload.delta);
        if (previousLogicalRange !== null) setVisibleRangeAll(shiftLogicalRange(previousLogicalRange, 1));
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
            if (previousLogicalRange !== null) {
                setVisibleRangeAll(shiftLogicalRange(previousLogicalRange, 1));
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

                        if (data.requires_full_refresh) {
                            await updateAdjustment(shiftLogicalRange(previousLogicalRange, 1));
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
                            await loadTechnicalIndicator(currentIndicatorType);
                            setVisibleRangeAll(shiftLogicalRange(previousLogicalRange, 1));
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
                if (maSeries[p] && mData && mData.length > 0) {
                    maSeries[p].update(mData[mData.length - 1]);
                }
            });
        }
    } catch (error) {
        console.error('更新移动平均线失败:', error);
    }
}

function getTechnicalIndicatorConfig(indicatorType) {
    if (indicatorType === 'MACD') {
        return {
            fast: parseInt(document.getElementById('macd-fast')?.value, 10) || 12,
            slow: parseInt(document.getElementById('macd-slow')?.value, 10) || 26,
            signal: parseInt(document.getElementById('macd-signal')?.value, 10) || 9,
        };
    }
    if (indicatorType === 'KDJ') {
        return {
            n: parseInt(document.getElementById('kdj-n')?.value, 10) || 9,
            m1: parseInt(document.getElementById('kdj-m1')?.value, 10) || 3,
            m2: parseInt(document.getElementById('kdj-m2')?.value, 10) || 3,
        };
    }
    if (indicatorType === 'RSI') {
        const periods = String(document.getElementById('rsi-periods')?.value || '6,12,24')
            .split(',')
            .map((value) => parseInt(value.trim(), 10))
            .filter((value) => Number.isFinite(value) && value > 0);
        return { periods: periods.length ? periods : [6, 12, 24] };
    }
    return {
        period: parseInt(document.getElementById('boll-period')?.value, 10) || 20,
        stdDev: parseFloat(document.getElementById('boll-std-dev')?.value) || 2,
    };
}

function clearTechnicalIndicatorSeries() {
    if (bollSeries.upper && chart) {
        Object.values(bollSeries).forEach((series) => chart.removeSeries(series));
    }
    bollSeries = {};
    if (indicatorChart && currentIndicatorSeries.length > 0) {
        currentIndicatorSeries.forEach((series) => indicatorChart.removeSeries(series));
    }
    currentIndicatorSeries = [];
    renderChartLegend();
    renderIndicatorLegend();
}

function createIndicatorLineSeries(color, title) {
    const series = indicatorChart.addSeries(LightweightCharts.LineSeries, {
        color,
        lineWidth: 1,
        crosshairMarkerVisible: false,
        priceLineVisible: false,
        lastValueVisible: false,
    });
    if (title) series.indicatorTitle = title;
    return series;
}

async function loadTechnicalIndicator(indicatorType) {
    if (!chart || !indicatorChart || !window.KLineIndicatorMath) return;
    const visibleLogicalRange = chart.timeScale().getVisibleLogicalRange();
    const indicatorChartElement = document.getElementById('indicator-chart');
    const indicatorCanvasElement = document.getElementById('indicator-canvas');
    const indicatorHeaderElement = document.getElementById('indicator-header');
    const infoElement = document.getElementById('indicator-info-display');

    try {
        clearTechnicalIndicatorSeries();
        indicatorCanvasElement?.style.removeProperty('display');
        indicatorChartElement?.classList.remove('indicator-collapsed');
        if (indicatorHeaderElement) indicatorHeaderElement.style.display = 'inline-flex';

        const data = window.KLineIndicatorMath.calculate(
            indicatorType,
            latestRenderedKlineData,
            getTechnicalIndicatorConfig(indicatorType),
        );
        if (!data.data || data.data.length === 0) {
            if (infoElement) {
                infoElement.style.display = 'block';
                infoElement.textContent = '当前已加载K线不足，暂时无法计算该指标';
            }
            return;
        }
        if (infoElement) infoElement.style.display = 'none';

        if (data.type === 'MACD') {
            const difSeries = createIndicatorLineSeries('#ff6b6b', 'DIF');
            const deaSeries = createIndicatorLineSeries('#4ecdc4', 'DEA');
            const histogramSeries = indicatorChart.addSeries(LightweightCharts.HistogramSeries, {
                crosshairMarkerVisible: false,
                priceLineVisible: false,
                lastValueVisible: false,
            });
            difSeries.setData(data.data.map((item) => ({ time: item.time, value: item.dif })));
            deaSeries.setData(data.data.map((item) => ({ time: item.time, value: item.dea })));
            histogramSeries.setData(data.data.map((item) => ({
                time: item.time,
                value: item.histogram,
                color: item.histogram >= 0 ? '#ff4d4f' : '#008000',
            })));
            currentIndicatorSeries.push(difSeries, deaSeries, histogramSeries);
        } else if (data.type === 'KDJ') {
            const kSeries = createIndicatorLineSeries('#ff6b6b', 'K');
            const dSeries = createIndicatorLineSeries('#4ecdc4', 'D');
            const jSeries = createIndicatorLineSeries('#45b7d1', 'J');
            kSeries.setData(data.data.map((item) => ({ time: item.time, value: item.k })));
            dSeries.setData(data.data.map((item) => ({ time: item.time, value: item.d })));
            jSeries.setData(data.data.map((item) => ({ time: item.time, value: item.j })));
            currentIndicatorSeries.push(kSeries, dSeries, jSeries);
        } else if (data.type === 'RSI') {
            const colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#f9c74f', '#90be6d', '#f8961e'];
            data.periods.forEach((period, index) => {
                const series = createIndicatorLineSeries(colors[index % colors.length], `RSI(${period})`);
                series.rsiTitle = `RSI(${period})`;
                series.setData(data.data.map((item) => ({ time: item.time, value: item[`rsi${period}`] })));
                currentIndicatorSeries.push(series);
            });
        } else if (data.type === 'BOLL') {
            const colors = { upper: '#ff6b6b', middle: '#4ecdc4', lower: '#45b7d1' };
            Object.keys(colors).forEach((key) => {
                bollSeries[key] = chart.addSeries(LightweightCharts.LineSeries, {
                    color: colors[key],
                    lineWidth: 2,
                    priceLineVisible: false,
                    crosshairMarkerVisible: false,
                    lastValueVisible: false,
                });
                bollSeries[key].setData(data.data.map((item) => ({ time: item.time, value: item[key] })));
                const indicatorLine = createIndicatorLineSeries(colors[key], key.toUpperCase());
                indicatorLine.setData(data.data.map((item) => ({ time: item.time, value: item[key] })));
                currentIndicatorSeries.push(indicatorLine);
            });
            renderChartLegend();
        }

        renderIndicatorLegend();
    } catch (error) {
        console.error(`加载技术指标失败: ${error}`);
        if (infoElement) {
            infoElement.style.display = 'block';
            infoElement.textContent = '技术指标计算失败';
        }
    } finally {
        if (visibleLogicalRange !== null && indicatorChart) {
            indicatorChart.timeScale().setVisibleLogicalRange(visibleLogicalRange);
        }
    }
}
function changeIndicator() {
    const select = document.getElementById('indicator-select');
    currentIndicatorType = select.value;
    loadTechnicalIndicator(currentIndicatorType);
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
    document.getElementById('crypto-liquidation-price').textContent = position.liquidation_price ? Number(position.liquidation_price).toLocaleString() : '--';
    document.getElementById('crypto-margin-ratio').textContent = account.margin_ratio == null ? '--' : (Number(account.margin_ratio) * 100).toFixed(2) + '%';
    const fundingNet = Number(account.funding_net ?? accountPayload?.funding_net ?? 0);
    document.getElementById('crypto-funding-summary').textContent = '资金费净额：' + fundingNet.toFixed(4) + ' USDT';
    renderCryptoPendingOrders(pendingOrders);
    refreshCryptoOrderPreview();
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
    const positionQuantity = Math.abs(Number(currentTraining?.position?.quantity || 0));
    const quantity = action === 'close' ? positionQuantity : floorCryptoQuantity((margin * leverage) / entryPrice, step);
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
    const body = { action, order_type: orderType, margin, leverage };
    if (orderType !== 'market') {
        const directionError = validateCryptoPendingPrice(orderType, action, entryPrice, currentPrice);
        if (directionError) {
            setCryptoOrderStatus(directionError, 'error');
            return;
        }
        if (orderType === 'limit') body.limit_price = entryPrice;
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
            : '挂单已提交，将从下一根已揭示 K 线开始检查。';
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
    try {
        console.log("所有持仓已清空，正在生成最终报告...");
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/end`, {
            method: 'POST'
        });

        if (response.ok) {
            const report = await response.json();
            pausePlayback();
            clearSessionDrawings();
            clearCryptoPeriodSnapshotCache();
            showReport(report);
        } else {
            const error = await response.json();
            alert(`结束训练失败: ${error.message}`);
        }
    } catch (error) {
        console.error('结束训练失败:', error);
        alert('结束训练失败');
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
