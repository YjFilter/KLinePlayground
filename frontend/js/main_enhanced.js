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
        training_start: null,
        training_end: null,
        has_earlier: false,
        has_later: false,
        read_only: false,
        period: 'daily',
    };
}

function resetChartWindowState() {
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

function isIntradayMode() {
    return !!(currentTraining && currentTraining.data_mode === INTRADAY_DATA_MODE);
}

// 从 #kline-period 下拉读取用户选择的周期。
// 始终返回 INTRADAY_PERIODS 之一，默认 'daily'。
function getSelectedKlinePeriod() {
    const select = document.getElementById('kline-period');
    if (!select) return 'daily';
    const value = select.value;
    return INTRADAY_PERIODS.indexOf(value) >= 0 ? value : 'daily';
}

// 将周期值转换为可读的徽章文字。
function formatIntradayPeriodBadge(period) {
    switch (period) {
        case '30m': return '30m';
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
    const next = INTRADAY_PERIODS.indexOf(period) >= 0 ? period : 'daily';
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
    return THEME_PALETTES[currentTheme] || THEME_PALETTES.light;
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
    document.getElementById('load-earlier-year-btn')?.addEventListener('click', loadEarlierYear);
    document.getElementById('load-later-year-btn')?.addEventListener('click', loadLaterYear);

    // 设置按钮
    document.getElementById('settings-btn')?.addEventListener('click', showSettings);
    document.getElementById('save-settings-btn')?.addEventListener('click', saveSettings);
    document.getElementById('cancel-settings-btn')?.addEventListener('click', hideSettings);
    document.getElementById('theme-toggle-btn')?.addEventListener('click', () => {
        applyTheme(currentTheme === 'dark' ? 'light' : 'dark', true, true);
    });
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

    // 技术指标选择
    document.getElementById('indicator-select')?.addEventListener('change', changeIndicator);

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
    window.addEventListener('resize', resizeCharts);
}

// 设置键盘快捷键
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Shift') {
            isShiftKeyPressed = true;
            updatePriceMode();
        }
        // 只在训练界面激活快捷键
        if (document.getElementById('training-interface').classList.contains('hidden') || isViewOnlyMode) {
            return;
        }

        // 如果是由于按住按键导致的重复触发，则忽略大多数操作
        // 但允许数字键的重复输入（如果焦点在输入框内）
        if (event.repeat) {
            // 检查当前焦点是否在输入框，如果不在，则阻止所有重复事件
            const quantityInput = document.getElementById('trade-quantity');
            if (document.activeElement !== quantityInput) {
                return;
            }
            // 如果焦点在输入框，且按下的不是数字，也阻止
            if (!/^[0-9]$/.test(event.key)) {
                return;
            }
            // 此时，允许在输入框中按住数字键进行输入
        }

        const quantityInput = document.getElementById('trade-quantity');
        const isInputFocused = document.activeElement === quantityInput;

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
                if (!isInputFocused) {
                    event.preventDefault();
                    quantityInput.focus();
                    quantityInput.value = event.key;
                }
                // 如果焦点已在输入框，则不作处理，允许默认的输入行为
                // 这样用户就可以正常输入多位数，并且按住数字键也能连续输入
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
// 处理窗口大小变化
function resizeCharts() {
    if (chart && !document.getElementById('training-interface').classList.contains('hidden')) {
        const chartContainer = document.getElementById('chart');
        const volumeContainer = document.getElementById('volume-chart');
        const indicatorContainer = document.getElementById('indicator-canvas');

        chart.resize(chartContainer.clientWidth, chartContainer.clientHeight);
        volumeChart.resize(volumeContainer.clientWidth, volumeContainer.clientHeight);
        indicatorChart.resize(indicatorContainer.clientWidth, indicatorContainer.clientHeight);
        
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
    // 1. 暂停任何正在进行的回放
    if (isPlaying) {
        pausePlayback();
    }
    stopAutoSync();

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
    document.getElementById('floating-pnl').style.color = '#000000';
    
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
    // 设置默认日期为一年前
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
    document.getElementById('start-date').value = oneYearAgo.toISOString().split('T')[0];
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

function replaceRenderedKlineData(klineData) {
    latestRenderedKlineData = Array.isArray(klineData) ? klineData.map(item => ({ ...item })) : [];
}

function upsertRenderedBar(bar) {
    if (!bar) return;
    if (latestRenderedKlineData.length === 0) {
        latestRenderedKlineData = [{ ...bar }];
        return;
    }

    const lastBar = latestRenderedKlineData[latestRenderedKlineData.length - 1];
    if (lastBar.time === bar.time) {
        latestRenderedKlineData[latestRenderedKlineData.length - 1] = { ...bar };
        return;
    }

    latestRenderedKlineData.push({ ...bar });
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
function normalizeChartTime(item) {
    if (!item) return 0;
    if (typeof item.time === 'number') return item.time;
    const rawTime = item.time || item.end_time || item.start_time || item.datetime;
    return intradayBarToTimestamp({ time: rawTime });
}

function normalizeChartCandle(item) {
    return {
        time: normalizeChartTime(item),
        open: Number(item.open),
        high: Number(item.high),
        low: Number(item.low),
        close: Number(item.close),
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
    if (!value) return null;
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
    if (!options.replace && options.direction === 'earlier') {
        merged.has_later = previous.has_later;
    }
    if (!options.replace && options.direction === 'later') {
        merged.has_earlier = previous.has_earlier;
    }
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

async function switchViewPeriod(period) {
    const nextPeriod = INTRADAY_PERIODS.indexOf(period) >= 0 ? period : (period === 'weekly' ? 'weekly' : 'daily');

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
            currentTraining = await response.json();
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
                setChartWindowStatus('已加载训练开始前至少两年的走势。', 'success');
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
}

function showTrainingInterface() {
    document.getElementById('history-dashboard')?.classList.add('hidden');
    document.getElementById('training-interface').classList.remove('hidden');
    setTrainingViewOnlyMode(false, { showBackToReport: false });
    updateAccountInfo();
    // 隐藏按钮和标题
    toggleToolbarForTraining(true);
}

// 图表管理
function initializeChart() {
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
        if (ohlcData) {
            if (previousDataPoint) {
                ohlcHtml = `
                    <div style="margin-bottom: 4px;">
                        <strong>开:</strong> <span style="color: ${ohlcData.open > previousDataPoint.close ? '#ff4d4f' : ohlcData.open < previousDataPoint.close ? '#008000' : '#000000'};">${ohlcData.open.toFixed(2)}</span>
                        <strong>高:</strong> <span style="color: ${ohlcData.high > previousDataPoint.close ? '#ff4d4f' : ohlcData.high < previousDataPoint.close ? '#008000' : '#000000'};">${ohlcData.high.toFixed(2)}</span>
                        <strong>低:</strong> <span style="color: ${ohlcData.low > previousDataPoint.close ? '#ff4d4f' : ohlcData.low < previousDataPoint.close ? '#008000' : '#000000'};">${ohlcData.low.toFixed(2)}</span>
                        <strong>收: <span style="color: ${ohlcData.close > ohlcData.open ? '#ff4d4f' : ohlcData.close > ohlcData.open ? '#008000' : '#000000'};">${ohlcData.close.toFixed(2)}</span></strong>
                    </div>
                `;
            } else {
                ohlcHtml = `
                    <div style="margin-bottom: 4px;">
                        <strong>开:</strong> <span>${ohlcData.open.toFixed(2)}</span>
                        <strong>高:</strong> <span>${ohlcData.high.toFixed(2)}</span>
                        <strong>低:</strong> <span>${ohlcData.low.toFixed(2)}</span>
                        <strong>收: <span style="color: ${ohlcData.close > ohlcData.open ? '#ff4d4f' : ohlcData.close < ohlcData.open ? '#008000' : '#000000'};">${ohlcData.close.toFixed(2)}</span></strong>
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

function updateCurrentInfo(barData, progress) {
    if (!barData) return;
    const palette = getThemePalette();

    const date = new Date(barData.time * 1000);
    const formattedDate = `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
    document.getElementById('current-date').textContent = formattedDate;
    document.getElementById('current-price').textContent = `¥${barData.close.toFixed(2)}`;

    // 显示当前bar ID
    document.getElementById('current-bar-id').textContent = `Bar ID: ${barData.bar_id || 'N/A'}`;

    // 更新当日详情
    document.getElementById('open-price').textContent = `¥${barData.open.toFixed(2)}`;
    document.getElementById('high-price').textContent = `¥${barData.high.toFixed(2)}`;
    document.getElementById('low-price').textContent = `¥${barData.low.toFixed(2)}`;
    document.getElementById('close-price').textContent = `¥${barData.close.toFixed(2)}`;

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
    } else {
        document.getElementById('volume').textContent = `--`;
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
        } else {
            document.getElementById('change-percent').textContent = `--%`;
            document.getElementById('change-percent').style.color = palette.neutral;
        }
    } else {
        document.getElementById('change-percent').textContent = `--%`;
        document.getElementById('change-percent').style.color = palette.neutral;
    }

    // 更新进度信息
    if (progress) {
        document.getElementById('training-progress').textContent =
            `进度: ${progress.training_progress.toFixed(1)}% (${progress.current_bar_id}/${progress.training_total_bars || (progress.total_bars - progress.preview_bars)})`;
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

        return {
            time: alignTradeMarkerTimeToRenderedBar(marker.time),
            position: shape === 'arrowDown' ? 'aboveBar' : 'belowBar',
            color: marker.type === 'B' ? '#ff4d4f' : '#008000',
            shape: shape,
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

async function nextBar() {
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

    if (false) {
        alert('请填写有效触发价');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/orders/${orderId}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        if (!response.ok) {
            alert(data.error || '撤单失败');
            return;
        }
        renderPendingOrders(data.pending_orders);
    } catch (error) {
        console.error('撤单失败:', error);
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

// 账户信息更新
async function updateAccountInfo() {
    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/account`);
        const account = await response.json();

        document.getElementById('total-assets').textContent = `¥${account.total_assets.toLocaleString()}`;
        document.getElementById('available-cash').textContent = `¥${account.available_cash.toLocaleString()}`;
        document.getElementById('position-value').textContent = `¥${account.position_value.toLocaleString()}`;
        document.getElementById('floating-pnl').textContent = `¥${account.floating_pnl.toLocaleString()}`;
        document.getElementById('floating-pnl').style.color = account.floating_pnl > 0 ? '#ff4d4f' : account.floating_pnl < 0 ? '#008000' : '#000000';

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
async function updateTradeHistory() {
    try {
        const response = await fetch(`${API_BASE}/training/${currentTraining.id}/trade_records`);
        if (!response.ok) return;
        const records = await response.json();
        
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
    const money = (value) => `¥${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    const dateRange = [report.start_date, report.end_date].filter(Boolean).join(' 至 ') || '-';
    const summaryItems = [
        ['股票代码', report.stock_code || '-'],
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
    createTradeDetailsTable(detailsSection, report.trade_details); // 使用辅助函数创建表格

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
    const requestedPeriod = INTRADAY_PERIODS.includes(currentReportData.period)
        ? currentReportData.period
        : 'daily';
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
