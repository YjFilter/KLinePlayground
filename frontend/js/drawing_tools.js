(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  } else {
    root.KLineDrawingTools = api;
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const DEFAULT_FIBONACCI_LEVELS = Object.freeze([
    Object.freeze({value: 0, label: '0', colorGroup: 'purple', color: '#7c4dff', enabled: true}),
    Object.freeze({value: 0.236, label: '23.6', colorGroup: 'purple', color: '#7c4dff', enabled: true}),
    Object.freeze({value: 0.382, label: '38.2', colorGroup: 'blue', color: '#2962ff', enabled: true}),
    Object.freeze({value: 0.5, label: '50', colorGroup: 'blue', color: '#2962ff', enabled: true}),
    Object.freeze({value: 0.618, label: '61.8', colorGroup: 'blue', color: '#2962ff', enabled: true}),
    Object.freeze({value: 0.786, label: '78.6', colorGroup: 'pink', color: '#ec407a', enabled: true}),
    Object.freeze({value: 1, label: '100', colorGroup: 'pink', color: '#ec407a', enabled: true}),
    Object.freeze({value: 1.382, label: '138.2', colorGroup: 'green', color: '#26a69a', enabled: true}),
    Object.freeze({value: 1.618, label: '161.8', colorGroup: 'green', color: '#26a69a', enabled: true}),
    Object.freeze({value: 2, label: '200', colorGroup: 'orange', color: '#ff9800', enabled: true}),
  ]);

  // AiCoin「斐波那契趋势时间」默认档位：0~3 延伸倍数，配色对齐其顶部彩色图例条。
  const DEFAULT_FIB_TREND_TIME_LEVELS = Object.freeze([
    Object.freeze({value: 0, label: '0', colorGroup: 'gray', color: '#9e9e9e', enabled: true}),
    Object.freeze({value: 0.382, label: '0.382', colorGroup: 'purple', color: '#7c4dff', enabled: true}),
    Object.freeze({value: 0.618, label: '0.618', colorGroup: 'blue', color: '#2962ff', enabled: true}),
    Object.freeze({value: 1, label: '1', colorGroup: 'cyan', color: '#00bcd4', enabled: true}),
    Object.freeze({value: 1.382, label: '1.382', colorGroup: 'lightblue', color: '#4fc3f7', enabled: true}),
    Object.freeze({value: 1.618, label: '1.618', colorGroup: 'pink', color: '#ec407a', enabled: true}),
    Object.freeze({value: 2, label: '2', colorGroup: 'magenta', color: '#d500f9', enabled: true}),
    Object.freeze({value: 2.382, label: '2.382', colorGroup: 'green', color: '#4caf50', enabled: true}),
    Object.freeze({value: 2.618, label: '2.618', colorGroup: 'brightgreen', color: '#0ecb81', enabled: true}),
    Object.freeze({value: 3, label: '3', colorGroup: 'orange', color: '#ff9800', enabled: true}),
  ]);

  const DEFAULT_LINE_WIDTH = 1;
  const DEFAULT_LINE_STYLE = 'solid';
  const DEFAULT_LABEL_VISIBLE = true;
  const DEFAULT_TEXT_CONTENT = 'Text';
  const DEFAULT_RECTANGLE_FILL = 'transparent';
  const DEFAULT_RECTANGLE_OPACITY = 0.12;
  // 斐波那契时间（Fibonacci Time Zones / Fibonacci Time）：
  // 把斐波那契倍数应用到时间轴上，从起点锚点向右按倍数画垂直时间线。
  // 参考 AiCoin：0 / 0.382 / 0.618 / 1 / 1.382 / 1.618 / 2 / 2.382 / 2.618 / 3
  const DEFAULT_FIBONACCI_TIME_LEVELS = Object.freeze([0, 0.382, 0.618, 1, 1.382, 1.618, 2, 2.382, 2.618, 3]);

  let nextDrawingId = 1;
  const SNAP_DISTANCE_PX = 8;
  const DEFAULT_RISK_REWARD_RATIO = 1.5;
  const DRAFT_DRAWING_ID = '__drawing-draft__';

  function assertFinite(value, name) {
    if (!Number.isFinite(value)) {
      throw new TypeError(`${name} must be finite`);
    }
    return value;
  }

  function clone(value) {
    return value == null ? value : JSON.parse(JSON.stringify(value));
  }

  /**
   * 把 hex 颜色 (#rgb / #rrggbb) 转 rgba，失败返回 null 让调用方回退原值。
   * 与 main_enhanced.js 的同名函数保持一致（独立 IIFE 模块，不能跨模块共享）。
   */
  function hexColorWithAlpha(hex, alpha) {
    if (typeof hex !== 'string' || !hex.startsWith('#')) return null;
    let digits = hex.slice(1);
    if (digits.length === 3) {
      digits = digits.split('').map((char) => char + char).join('');
    } else if (digits.length !== 6) {
      return null;
    }
    if (!/^[0-9a-fA-F]{6}$/.test(digits)) return null;
    const r = parseInt(digits.slice(0, 2), 16);
    const g = parseInt(digits.slice(2, 4), 16);
    const b = parseInt(digits.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function createTimeProjectionContext(bars) {
    const times = (Array.isArray(bars) ? bars : [])
      .map((bar) => Number(bar && bar.time))
      .filter(Number.isFinite)
      .sort((left, right) => left - right)
      .filter((time, index, values) => index === 0 || time !== values[index - 1]);
    if (!times.length) return null;
    const intervals = [];
    for (let index = 1; index < times.length; index += 1) {
      const interval = times[index] - times[index - 1];
      if (interval > 0) intervals.push(interval);
    }
    intervals.sort((left, right) => left - right);
    const middle = Math.floor(intervals.length / 2);
    const interval = intervals.length === 0
      ? null
      : intervals.length % 2
        ? intervals[middle]
        : (intervals[middle - 1] + intervals[middle]) / 2;
    return {
      firstTime: times[0],
      lastTime: times[times.length - 1],
      interval,
    };
  }

  function projectionReference(timeScale, context, target, mode) {
    if (!context || !Number.isFinite(context.interval) || context.interval <= 0
        || typeof timeScale.coordinateToLogical !== 'function') return null;
    const references = [];
    for (const time of [context.firstTime, context.lastTime]) {
      if (references.some((reference) => reference.time === time)) continue;
      const coordinate = timeScale.timeToCoordinate(time);
      if (!Number.isFinite(coordinate)) continue;
      const logical = timeScale.coordinateToLogical(coordinate);
      if (Number.isFinite(logical)) references.push({time, logical});
    }
    if (!references.length) return null;
    const key = mode === 'time' ? 'time' : 'logical';
    return references.reduce((best, reference) => (
      !best || Math.abs(reference[key] - target) < Math.abs(best[key] - target)
        ? reference
        : best
    ), null);
  }

  function coordinateToProjectedTime(timeScale, coordinate, context) {
    const directTime = timeScale.coordinateToTime(coordinate);
    if (Number.isFinite(directTime)) return directTime;
    if (typeof timeScale.coordinateToLogical !== 'function') return null;
    const logical = timeScale.coordinateToLogical(coordinate);
    if (!Number.isFinite(logical)) return null;
    const reference = projectionReference(timeScale, context, logical, 'logical');
    if (!reference) return null;
    return Math.round(reference.time + ((logical - reference.logical) * context.interval));
  }

  function projectedTimeToCoordinate(timeScale, time, context) {
    const directCoordinate = timeScale.timeToCoordinate(time);
    if (Number.isFinite(directCoordinate)) return directCoordinate;
    if (typeof timeScale.logicalToCoordinate !== 'function') return null;
    const reference = projectionReference(timeScale, context, time, 'time');
    if (!reference) return null;
    return timeScale.logicalToCoordinate(
      reference.logical + ((time - reference.time) / context.interval)
    );
  }

  function normalizeAnchor(anchor) {
    if (!anchor || typeof anchor !== 'object') {
      throw new TypeError('anchor must be an object');
    }
    return {
      time: assertFinite(anchor.time, 'anchor.time'),
      price: assertFinite(anchor.price, 'anchor.price'),
    };
  }

  function normalizeDrawingType(type) {
    if (type === 'long-position') return 'long';
    if (type === 'short-position') return 'short';
    if (type === 'fibonacci-time') return 'fibonacci-time';
    return type;
  }

  function normalizeRiskSide(side) {
    const normalized = normalizeDrawingType(side);
    if (normalized !== 'long' && normalized !== 'short') {
      throw new RangeError('side must be long or short');
    }
    return normalized;
  }

  function defaultFibonacciSettings() {
    return {
      levels: resetFibonacciLevels(),
      reverse: false,
      lineWidth: 1,
      lineStyle: 'solid',
      labelPosition: 'left',
    };
  }

  // 「斐波那契趋势时间」默认设置：0~3 档位 + 虚线，和回撤斐波那契区分开。
  function defaultFibTrendTimeSettings() {
    return {
      levels: resetFibTrendTimeLevels(),
      reverse: false,
      lineWidth: 1,
      lineStyle: 'dashed',
      labelPosition: 'left',
    };
  }

  function resetFibTrendTimeLevels() {
    return clone(DEFAULT_FIB_TREND_TIME_LEVELS);
  }

  /**
   * 归一化通用线条设置：所有画图工具（horizontal/trend/ray/rectangle/ruler/text）
   * 的 model.options 都会经过此函数，确保字段一致。这样前端设置面板可以按统一字段读写。
   * 注意：color 字段不在此处强制 fallback（保留 undefined 让渲染时回退到主题色 strokeColor）。
   */
  function normalizeLineOptions(options, defaults = {}) {
    const config = options || {};
    const fallback = {
      lineWidth: DEFAULT_LINE_WIDTH,
      lineStyle: DEFAULT_LINE_STYLE,
      labelVisible: DEFAULT_LABEL_VISIBLE,
      ...defaults,
    };
    const lineWidth = config.lineWidth == null ? fallback.lineWidth : assertFinite(config.lineWidth, 'lineWidth');
    if (lineWidth <= 0) throw new RangeError('lineWidth must be positive');
    const lineStyle = config.lineStyle || fallback.lineStyle;
    if (!['solid', 'dashed', 'dotted'].includes(lineStyle)) {
      throw new RangeError('lineStyle must be solid, dashed, or dotted');
    }
    return {
      ...clone(config),
      lineWidth,
      lineStyle,
      labelVisible: config.labelVisible !== false,
    };
  }

  function normalizeRectangleOptions(options) {
    const base = normalizeLineOptions(options);
    const config = options || {};
    // fillColor 缺省时保留 undefined（渲染时回退到 strokeColor 透明版）。
    // fillOpacity 缺省时也保留 undefined（渲染时回退到 0.16 默认）。
    let fillOpacity = config.fillOpacity;
    if (fillOpacity != null) {
      fillOpacity = assertFinite(fillOpacity, 'fillOpacity');
      if (fillOpacity < 0 || fillOpacity > 1) {
        throw new RangeError('fillOpacity must be between 0 and 1');
      }
    }
    return {
      ...base,
      fillColor: config.fillColor,
      fillOpacity,
    };
  }

  function normalizeTextOptions(options) {
    const base = normalizeLineOptions(options);
    const config = options || {};
    return {
      ...base,
      text: config.text == null || config.text === '' ? DEFAULT_TEXT_CONTENT : String(config.text),
      fontSize: config.fontSize == null ? 14 : assertFinite(config.fontSize, 'fontSize'),
    };
  }

  function normalizeFibonacciLevel(level) {
    const definition = typeof level === 'number' ? {value: level} : clone(level || {});
    const value = assertFinite(definition.value, 'level.value');
    return {
      value,
      label: definition.label == null ? `${value * 100}` : String(definition.label),
      colorGroup: definition.colorGroup || 'custom',
      color: definition.color || '#2962ff',
      enabled: definition.enabled !== false,
    };
  }

  function normalizeFibonacciSettings(options, defaults = defaultFibonacciSettings()) {
    const config = options || {};
    const lineWidth = config.lineWidth == null ? defaults.lineWidth : assertFinite(config.lineWidth, 'lineWidth');
    if (lineWidth <= 0) throw new RangeError('lineWidth must be positive');
    const lineStyle = config.lineStyle || defaults.lineStyle;
    if (!['solid', 'dashed', 'dotted'].includes(lineStyle)) {
      throw new RangeError('lineStyle must be solid, dashed, or dotted');
    }
    const labelPosition = config.labelPosition || defaults.labelPosition;
    if (!['left', 'right'].includes(labelPosition)) {
      throw new RangeError('labelPosition must be left or right');
    }
    return {
      ...clone(config),
      levels: (config.levels || defaults.levels).map(normalizeFibonacciLevel),
      reverse: Boolean(config.reverse),
      lineWidth,
      lineStyle,
      labelPosition,
    };
  }

  function calculateFibonacciLevels(startPrice, endPrice, options) {
    assertFinite(startPrice, 'startPrice');
    assertFinite(endPrice, 'endPrice');
    const config = options || {};
    const levels = config.levels || DEFAULT_FIBONACCI_LEVELS;
    const origin = config.reverse ? endPrice : startPrice;
    const destination = config.reverse ? startPrice : endPrice;
    return levels.map((level) => {
      const definition = typeof level === 'number' ? { value: level } : level;
      const value = assertFinite(definition.value, 'level.value');
      return {
        ...clone(definition),
        value,
        price: origin + ((destination - origin) * value),
      };
    });
  }

  function calculateRulerMetrics(startAnchor, endAnchor, options) {
    const start = normalizeAnchor(startAnchor);
    const end = normalizeAnchor(endAnchor);
    const config = options || {};
    const minimumTime = Math.min(start.time, end.time);
    const maximumTime = Math.max(start.time, end.time);
    const visibleBars = Array.isArray(config.bars)
      ? config.bars.filter((bar) => Number.isFinite(bar.time)
        && bar.time >= minimumTime && bar.time <= maximumTime)
      : [];
    let barCount = visibleBars.length;
    if (barCount === 0 && Number.isFinite(config.barCount)) {
      barCount = Math.abs(config.barCount);
    } else if (barCount === 0 && Number.isFinite(config.startIndex) && Number.isFinite(config.endIndex)) {
      barCount = Math.abs(config.endIndex - config.startIndex);
    }
    const priceDelta = end.price - start.price;
    const elapsedDuration = Math.abs(end.time - start.time);
    return {
      priceDelta,
      absolutePriceChange: Math.abs(priceDelta),
      percentChange: start.price === 0 ? 0 : (priceDelta / start.price) * 100,
      barCount,
      bullishCount: visibleBars.filter((bar) => Number.isFinite(bar.open)
        && Number.isFinite(bar.close) && bar.close > bar.open).length,
      bearishCount: visibleBars.filter((bar) => Number.isFinite(bar.open)
        && Number.isFinite(bar.close) && bar.close < bar.open).length,
      totalVolume: visibleBars.reduce((total, bar) => (
        Number.isFinite(bar.volume) ? total + bar.volume : total
      ), 0),
      duration: elapsedDuration,
      elapsedDuration,
      direction: priceDelta >= 0 ? 'bull' : 'bear',
    };
  }

  function calculateRiskReward(side, entry, stop, target, options) {
    assertFinite(entry, 'entry');
    assertFinite(stop, 'stop');
    assertFinite(target, 'target');
    const normalizedSide = normalizeRiskSide(side);
    const valid = normalizedSide === 'long'
      ? stop < entry && target > entry
      : stop > entry && target < entry;
    if (!valid) {
      throw new RangeError(`invalid ${normalizedSide} price ordering`);
    }
    const risk = Math.abs(entry - stop);
    const reward = Math.abs(target - entry);
    const result = {
      side: normalizedSide,
      entry,
      stop,
      target,
      risk,
      reward,
      riskPercent: entry === 0 ? 0 : (risk / Math.abs(entry)) * 100,
      rewardPercent: entry === 0 ? 0 : (reward / Math.abs(entry)) * 100,
      rewardRiskRatio: reward / risk,
    };
    const config = options || {};
    if (Number.isFinite(config.accountRiskAmount)) {
      result.accountRiskAmount = config.accountRiskAmount;
    } else if (Number.isFinite(config.accountSize) && Number.isFinite(config.accountRiskPercent)) {
      result.accountRiskAmount = config.accountSize * config.accountRiskPercent / 100;
    }
    if (Number.isFinite(config.accountSize)) result.accountSize = config.accountSize;
    const positionSize = Number.isFinite(config.positionSize) ? config.positionSize : config.quantity;
    if (Number.isFinite(positionSize)) result.positionSize = positionSize;
    return result;
  }

  function createDrawingModel(type, anchors, options) {
    if (typeof type !== 'string' || !type) {
      throw new TypeError('type is required');
    }
    if (!Array.isArray(anchors) || anchors.length === 0) {
      throw new TypeError('anchors must be a non-empty array');
    }
    const config = options || {};
    const normalizedType = normalizeDrawingType(type);
    let modelOptions;
    if (normalizedType === 'fibonacci') {
      modelOptions = normalizeFibonacciSettings(config.options);
    } else if (normalizedType === 'fib-trend-time') {
      modelOptions = normalizeFibonacciSettings(config.options, defaultFibTrendTimeSettings());
    } else if (normalizedType === 'rectangle') {
      modelOptions = normalizeRectangleOptions(config.options);
    } else if (normalizedType === 'text') {
      modelOptions = normalizeTextOptions(config.options);
    } else {
      // horizontal / trend / ray / ruler / long / short / risk-reward 等：通用线条字段
      modelOptions = normalizeLineOptions(config.options);
    }
    for (const key of [
      'accountRiskAmount', 'accountSize', 'accountRiskPercent', 'positionSize', 'quantity'
    ]) {
      if (Number.isFinite(config[key])) modelOptions[key] = config[key];
    }
    const model = {
      id: config.id || `drawing-${nextDrawingId++}`,
      type: normalizedType,
      anchors: anchors.map(normalizeAnchor),
      locked: Boolean(config.locked),
      hidden: Boolean(config.hidden),
      selected: Boolean(config.selected),
      options: modelOptions,
    };
    if (normalizedType === 'long' || normalizedType === 'short' || normalizedType === 'risk-reward') {
      const side = normalizedType === 'risk-reward' ? normalizeRiskSide(config.side) : normalizedType;
      if (model.anchors.length !== 3) {
        throw new RangeError('risk/reward drawings require three anchors');
      }
      calculateRiskReward(
        side,
        model.anchors[0].price,
        model.anchors[1].price,
        model.anchors[2].price,
        model.options
      );
      model.side = side;
    }
    return model;
  }

  function serializeDrawing(model) {
    if (!model || typeof model !== 'object') {
      throw new TypeError('drawing model is required');
    }
    const serialized = clone(model);
    serialized.type = normalizeDrawingType(serialized.type);
    serialized.anchors = model.anchors.map(normalizeAnchor);
    if (serialized.type === 'fibonacci') {
      serialized.options = normalizeFibonacciSettings(serialized.options);
    } else if (serialized.type === 'fib-trend-time') {
      serialized.options = normalizeFibonacciSettings(serialized.options, defaultFibTrendTimeSettings());
    } else if (serialized.type === 'rectangle') {
      serialized.options = normalizeRectangleOptions(serialized.options);
    } else if (serialized.type === 'text') {
      serialized.options = normalizeTextOptions(serialized.options);
    } else {
      serialized.options = normalizeLineOptions(serialized.options);
    }
    if (serialized.type === 'long' || serialized.type === 'short' || serialized.type === 'risk-reward') {
      const side = serialized.type === 'risk-reward' ? serialized.side : serialized.type;
      if (serialized.anchors.length !== 3) {
        throw new RangeError('risk/reward drawings require three anchors');
      }
      calculateRiskReward(
        side,
        serialized.anchors[0].price,
        serialized.anchors[1].price,
        serialized.anchors[2].price,
        serialized.options
      );
    }
    return serialized;
  }

  function resetFibonacciLevels() {
    return clone(DEFAULT_FIBONACCI_LEVELS);
  }

  class DrawingStore {
    constructor(drawings) {
      this._drawings = clone(drawings || []);
      this._undoStack = [];
      this._redoStack = [];
    }

    get size() {
      return this._drawings.length;
    }

    snapshot() {
      return clone(this._drawings);
    }

    get(id) {
      return clone(this._drawings.find((drawing) => drawing.id === id));
    }

    _commit(nextDrawings) {
      this._undoStack.push(this.snapshot());
      this._drawings = clone(nextDrawings);
      this._redoStack = [];
    }

    add(model) {
      const serialized = serializeDrawing(model);
      if (this._drawings.some((drawing) => drawing.id === serialized.id)) {
        throw new RangeError(`drawing already exists: ${serialized.id}`);
      }
      this._commit([...this._drawings, serialized]);
      return clone(serialized);
    }

    update(id, updater) {
      const index = this._drawings.findIndex((drawing) => drawing.id === id);
      if (index < 0) return undefined;
      const current = clone(this._drawings[index]);
      const updated = typeof updater === 'function' ? updater(current) : { ...current, ...updater };
      const next = this.snapshot();
      next[index] = serializeDrawing({ ...updated, id });
      this._commit(next);
      return clone(next[index]);
    }

    remove(id) {
      const next = this._drawings.filter((drawing) => drawing.id !== id);
      if (next.length === this._drawings.length) return false;
      this._commit(next);
      return true;
    }

    clear() {
      if (this._drawings.length === 0) return false;
      this._commit([]);
      return true;
    }

    reset() {
      const changed = this._drawings.length > 0 || this._undoStack.length > 0 || this._redoStack.length > 0;
      this._drawings = [];
      this._undoStack = [];
      this._redoStack = [];
      return changed;
    }

    undo() {
      if (this._undoStack.length === 0) return false;
      this._redoStack.push(this.snapshot());
      this._drawings = this._undoStack.pop();
      return true;
    }

    redo() {
      if (this._redoStack.length === 0) return false;
      this._undoStack.push(this.snapshot());
      this._drawings = this._redoStack.pop();
      return true;
    }
  }

  const createTrendModel = (anchors, options) => createDrawingModel('trend', anchors, options);
  const createHorizontalModel = (anchors, options) => createDrawingModel('horizontal', anchors, options);
  const createRayModel = (anchors, options) => createDrawingModel('ray', anchors, options);
  const createRectangleModel = (anchors, options) => createDrawingModel('rectangle', anchors, options);
  const createTextModel = (anchors, options) => createDrawingModel('text', anchors, options);
  const createFibonacciModel = (anchors, options) => createDrawingModel('fibonacci', anchors, options);
  const createFibTrendTimeModel = (anchors, options) => createDrawingModel('fib-trend-time', anchors, options);
  const createRulerModel = (anchors, options) => createDrawingModel('ruler', anchors, options);
  const createRiskRewardModel = (side, anchors, options) => createDrawingModel(
    'risk-reward',
    anchors,
    { ...(options || {}), side }
  );

  function distanceToSegment(point, start, end) {
    const deltaX = end.x - start.x;
    const deltaY = end.y - start.y;
    const lengthSquared = (deltaX * deltaX) + (deltaY * deltaY);
    if (lengthSquared === 0) return Math.hypot(point.x - start.x, point.y - start.y);
    const ratio = Math.max(0, Math.min(1,
      (((point.x - start.x) * deltaX) + ((point.y - start.y) * deltaY)) / lengthSquared
    ));
    return Math.hypot(
      point.x - (start.x + ratio * deltaX),
      point.y - (start.y + ratio * deltaY)
    );
  }

  function calculateRayEndpoint(start, directionPoint, bounds) {
    const deltaX = directionPoint.x - start.x;
    const deltaY = directionPoint.y - start.y;
    if (deltaX === 0 && deltaY === 0) return {x: start.x, y: start.y};
    const candidates = [];
    if (deltaX > 0) candidates.push((bounds.right - start.x) / deltaX);
    if (deltaX < 0) candidates.push((bounds.left - start.x) / deltaX);
    if (deltaY > 0) candidates.push((bounds.bottom - start.y) / deltaY);
    if (deltaY < 0) candidates.push((bounds.top - start.y) / deltaY);
    const scale = Math.min(...candidates.filter((candidate) => Number.isFinite(candidate) && candidate >= 0));
    if (!Number.isFinite(scale)) return {x: directionPoint.x, y: directionPoint.y};
    return {
      x: start.x + deltaX * scale,
      y: start.y + deltaY * scale,
    };
  }

  function drawLine(context, start, end) {
    context.beginPath();
    context.moveTo(start.x, start.y);
    context.lineTo(end.x, end.y);
    context.stroke();
  }

  function clamp(value, minimum, maximum) {
    return Math.min(Math.max(value, minimum), Math.max(minimum, maximum));
  }

  function trimFixed(value, precision) {
    return Number(value.toFixed(precision)).toString();
  }

  function formatAdaptivePrice(value) {
    if (!Number.isFinite(value)) return '--';
    const absoluteValue = Math.abs(value);
    if (absoluteValue >= 100) return trimFixed(value, 2);
    if (absoluteValue >= 1) return trimFixed(value, 4);
    if (absoluteValue >= 0.01) return trimFixed(value, 5);
    if (absoluteValue >= 0.0001) return trimFixed(value, 6);
    return trimFixed(value, 8);
  }

  function formatSignedPrice(value) {
    if (!Number.isFinite(value)) return '--';
    return `${value >= 0 ? '+' : '-'}${formatAdaptivePrice(Math.abs(value))}`;
  }

  function formatSignificant(value, digits) {
    if (!Number.isFinite(value)) return '--';
    if (value === 0) return '0';
    return Number(value.toPrecision(digits)).toString();
  }

  function formatCompactNumber(value, suffixes) {
    if (!Number.isFinite(value)) return '--';
    const units = suffixes || [
      {threshold: 1e9, divisor: 1e9, suffix: 'B'},
      {threshold: 1e6, divisor: 1e6, suffix: 'M'},
      {threshold: 1e3, divisor: 1e3, suffix: 'K'},
    ];
    const absoluteValue = Math.abs(value);
    const unit = units.find((candidate) => absoluteValue >= candidate.threshold);
    if (!unit) return formatAdaptivePrice(value);
    return `${trimFixed(value / unit.divisor, 2)}${unit.suffix}`;
  }

  function formatAccountValue(value) {
    return formatCompactNumber(value, [
      {threshold: 1e6, divisor: 1e6, suffix: 'M'},
      {threshold: 1e3, divisor: 1e3, suffix: 'K'},
    ]);
  }

  function colorWithAlpha(color, alpha) {
    if (typeof color !== 'string') return color;
    if (color.charAt(0) === '#') {
      let hex = color.slice(1);
      if (hex.length === 3) hex = hex.split('').map((part) => part + part).join('');
      if (hex.length >= 6) {
        const red = parseInt(hex.slice(0, 2), 16);
        const green = parseInt(hex.slice(2, 4), 16);
        const blue = parseInt(hex.slice(4, 6), 16);
        if ([red, green, blue].every(Number.isFinite)) {
          return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
        }
      }
      return color;
    }
    const match = color.match(/^rgba?\(([^)]+)\)$/i);
    if (match) {
      const parts = match[1].split(',').map((part) => Number.parseFloat(part.trim()));
      if (parts.length >= 3 && parts.slice(0, 3).every(Number.isFinite)) {
        return `rgba(${parts[0]}, ${parts[1]}, ${parts[2]}, ${alpha})`;
      }
    }
    return color;
  }

  // AiCoin 风格：选中/悬停图形时，把锚点价格同步到右侧价格轴。
  // 斐波那契自带档位标签、text 无价格含义，因此不产生轴标签。
  function axisLabelPrices(model) {
    if (!model || typeof model !== 'object' || !Array.isArray(model.anchors)) return [];
    const anchors = model.anchors;
    switch (model.type) {
      case 'horizontal':
        return [anchors[0].price];
      case 'trend':
      case 'ray':
      case 'rectangle':
      case 'ruler':
        return [anchors[0].price, anchors[1].price];
      case 'long':
      case 'short':
      case 'risk-reward':
        return [anchors[0].price, anchors[1].price, anchors[2].price];
      default:
        return [];
    }
  }

  function drawLabel(context, text, x, top, color, ratioX, ratioY, bounds) {
    const paddingX = 6 * ratioX;
    const labelHeight = 20 * ratioY;
    const labelWidth = context.measureText(text).width + (paddingX * 2);
    const marginX = 3 * ratioX;
    const marginY = 2 * ratioY;
    const drawX = clamp(x, marginX, bounds.width - labelWidth - marginX);
    const drawTop = clamp(top, marginY, bounds.height - labelHeight - marginY);
    context.fillStyle = color;
    context.fillRect(drawX, drawTop, labelWidth, labelHeight);
    context.fillStyle = '#ffffff';
    context.textBaseline = 'middle';
    context.fillText(text, drawX + paddingX, drawTop + (labelHeight / 2));
    return {x: drawX, y: drawTop, width: labelWidth, height: labelHeight};
  }

  function applyLineStyle(context, lineStyle, ratio) {
    if (lineStyle === 'dashed') context.setLineDash([6 * ratio, 4 * ratio]);
    else if (lineStyle === 'dotted') context.setLineDash([2 * ratio, 3 * ratio]);
    else context.setLineDash([]);
  }

  function formatDuration(seconds) {
    const totalMinutes = Math.floor(Math.abs(seconds) / 60);
    if (totalMinutes < 1) return `${Math.floor(Math.abs(seconds))}秒`;
    const days = Math.floor(totalMinutes / 1440);
    const hours = Math.floor((totalMinutes % 1440) / 60);
    const minutes = totalMinutes % 60;
    const parts = [];
    if (days) parts.push(`${days}天`);
    if (hours) parts.push(`${hours}小时`);
    if (minutes || parts.length === 0) parts.push(`${minutes}分钟`);
    return parts.join('');
  }

  function layoutRiskLabelTops(labels, height, ratioY) {
    const labelHeight = 20 * ratioY;
    const gap = 2 * ratioY;
    const margin = 2 * ratioY;
    const sorted = labels
      .map((label) => ({...label, top: label.y - (labelHeight / 2)}))
      .sort((left, right) => left.top - right.top);
    sorted.forEach((label, index) => {
      const minimumTop = index === 0 ? margin : sorted[index - 1].top + labelHeight + gap;
      label.top = Math.max(label.top, minimumTop);
    });
    const overflow = sorted.length
      ? sorted[sorted.length - 1].top + labelHeight + margin - height
      : 0;
    if (overflow > 0) sorted.forEach((label) => { label.top -= overflow; });
    for (let index = sorted.length - 2; index >= 0; index -= 1) {
      sorted[index].top = Math.min(sorted[index].top, sorted[index + 1].top - labelHeight - gap);
    }
    const underflow = sorted.length ? margin - sorted[0].top : 0;
    if (underflow > 0) sorted.forEach((label) => { label.top += underflow; });
    return new Map(sorted.map((label) => [label.key, label.top]));
  }

  class DrawingPaneRenderer {
    constructor(primitive) {
      this._primitive = primitive;
    }

    draw(target) {
      const primitive = this._primitive;
      const model = primitive.model();
      if (model.hidden) return;
      const anchors = primitive.projectAnchors();
      if (anchors.length === 0 || !anchors.some(Boolean)) return;
      target.useBitmapCoordinateSpace((scope) => {
        const context = scope.context;
        const ratioX = scope.horizontalPixelRatio || 1;
        const ratioY = scope.verticalPixelRatio || 1;
        const point = (anchor) => anchor ? {x: anchor.x * ratioX, y: anchor.y * ratioY} : null;
        const points = anchors.map(point);
        const width = scope.bitmapSize.width;
        const height = scope.bitmapSize.height;
        primitive.setPaneBounds(scope.mediaSize.width, scope.mediaSize.height);
        const strokeColor = model.options.color || primitive.defaultStrokeColor();
        context.save();
        context.beginPath();
        context.rect(0, 0, width, height);
        context.clip();
        context.strokeStyle = strokeColor;
        context.fillStyle = model.options.fillColor || colorWithAlpha(strokeColor, 0.16);
        context.lineWidth = (model.selected ? 2 : 1) * Math.max(ratioX, ratioY);
        context.font = `${12 * ratioY}px sans-serif`;

        const first = points[0];
        const second = points[1] || first;
        const requiresTwoAnchors = !['horizontal', 'text'].includes(model.type);
        if (!first || (requiresTwoAnchors && !second)) {
          context.restore();
          return;
        }
        if (model.type === 'horizontal') {
          context.strokeStyle = strokeColor;
          context.lineWidth = model.options.lineWidth * Math.max(ratioX, ratioY);
          applyLineStyle(context, model.options.lineStyle, ratioX);
          drawLine(context, {x: 0, y: first.y}, {x: width, y: first.y});
          if (model.options.labelVisible !== false && Number.isFinite(first.price)) {
            context.fillStyle = strokeColor;
            context.fillText(first.price.toFixed(2), 4 * ratioX, first.y - (3 * ratioY));
          }
        } else if (model.type === 'ray') {
          context.strokeStyle = strokeColor;
          context.lineWidth = model.options.lineWidth * Math.max(ratioX, ratioY);
          applyLineStyle(context, model.options.lineStyle, ratioX);
          drawLine(context, first, calculateRayEndpoint(first, second, {
            left: 0,
            top: 0,
            right: width,
            bottom: height,
          }));
        } else if (model.type === 'rectangle') {
          const left = Math.min(first.x, second.x);
          const top = Math.min(first.y, second.y);
          const rectWidth = Math.abs(second.x - first.x);
          const rectHeight = Math.abs(second.y - first.y);
          context.strokeStyle = strokeColor;
          context.lineWidth = model.options.lineWidth * Math.max(ratioX, ratioY);
          applyLineStyle(context, model.options.lineStyle, ratioX);
          const fillColor = model.options.fillColor;
          const fillAlpha = model.options.fillOpacity;
          if (!fillColor || fillColor === 'transparent') {
            // 默认：strokeColor 透明版（保持原有视觉一致）
            context.fillStyle = colorWithAlpha(strokeColor, fillAlpha ?? 0.16);
          } else if (fillAlpha > 0) {
            context.fillStyle = hexColorWithAlpha(fillColor, fillAlpha) || fillColor;
          } else {
            context.fillStyle = fillColor;
          }
          context.fillRect(left, top, rectWidth, rectHeight);
          context.strokeRect(left, top, rectWidth, rectHeight);
        } else if (model.type === 'text') {
          context.fillStyle = strokeColor;
          context.font = `${model.options.fontSize * ratioY}px sans-serif`;
          context.fillText(model.options.text || 'Text', first.x, first.y);
        } else if (model.type === 'fibonacci') {
          context.save();
          context.strokeStyle = '#2962ff';
          context.setLineDash([6 * ratioX, 4 * ratioX]);
          drawLine(context, first, second);
          context.restore();
          const left = first.x;
          const right = width;
          context.lineWidth = model.options.lineWidth * Math.max(ratioX, ratioY);
          applyLineStyle(context, model.options.lineStyle, ratioX);
          calculateFibonacciLevels(model.anchors[0].price, model.anchors[1].price, model.options)
            .filter((level) => level.enabled !== false)
            .forEach((level) => {
              const y = primitive.priceToCoordinate(level.price) * ratioY;
              context.strokeStyle = level.color || strokeColor;
              context.fillStyle = level.color || strokeColor;
              drawLine(context, {x: left, y}, {x: right, y});
              const label = level.label == null ? `${level.value * 100}` : level.label;
              const labelText = `${label}% (${level.price.toFixed(2)})`;
              const labelX = model.options.labelPosition === 'right'
                ? right - context.measureText(labelText).width - (4 * ratioX)
                : left + (4 * ratioX);
              context.fillText(labelText, labelX, y - (3 * ratioY));
            });
        } else if (model.type === 'fib-trend-time') {
          // 斐波那契趋势时间（重写版）：
          // 用户从 A→B 量取一段走势（anchors[0]=A 起点，anchors[1]=B 终点）。
          // 0 线对齐 B（第二锚点），Δt = |B.time - A.time|（A→B 量取的走势时长），
          // 1 线在 B 右侧 +1×Δt 处，0.382/0.618 在 B~B+Δt 之间，
          // 1.382/1.618/2/... 继续向 B 右侧（未来）扩展。
          // 渲染用纯像素插值（不依赖时间投影，避免 _timeProjection 不可用导致坐标错乱）：
          //   deltaX = |B.x - A.x|（向右扩展距离）
          //   lineX = B.x + ratio × deltaX
          const deltaX = Math.abs(second.x - first.x);
          // 两锚点之间的虚线参考连线（被量取的这一段走势）
          context.save();
          context.strokeStyle = strokeColor;
          context.setLineDash([4 * ratioX, 4 * ratioX]);
          context.lineWidth = Math.max(1, (Number(model.options.lineWidth) || 1) * 0.75)
            * Math.max(ratioX, ratioY);
          drawLine(context, first, second);
          context.restore();
          // 垂直时间线：位置 = B + ratio × Δt（始终从 B 向右扩展）
          context.lineWidth = Math.max(Number(model.options.lineWidth) || 1, 1)
            * Math.max(ratioX, ratioY);
          applyLineStyle(context, model.options.lineStyle, ratioX);
          const enabledLevels = (model.options.levels || [])
            .filter((level) => level && level.enabled !== false);
          enabledLevels.forEach((level) => {
            const ratio = Number(level.value || 0);
            const x = second.x + ratio * deltaX;
            if (!Number.isFinite(x)) return;
            context.strokeStyle = level.color || strokeColor;
            drawLine(context, {x, y: 0}, {x, y: height});
            if (model.options.labelVisible !== false) {
              const labelText = level.label == null
                ? String(level.value == null ? '' : level.value)
                : String(level.label);
              const labelY = model.options.labelPosition === 'bottom'
                ? height - (6 * ratioY)
                : (8 * ratioY) + 12 * ratioY;
              context.fillStyle = level.color || strokeColor;
              context.fillText(labelText, x + (3 * ratioX), labelY);
            }
          });
        } else if (model.type === 'ruler') {
          const left = Math.min(first.x, second.x);
          const top = Math.min(first.y, second.y);
          const rectWidth = Math.abs(second.x - first.x);
          const rectHeight = Math.abs(second.y - first.y);
          const centerX = left + (rectWidth / 2);
          const metrics = primitive.rulerMetrics();
          context.fillStyle = 'rgba(38, 166, 154, 0.18)';
          context.strokeStyle = '#26a69a';
          context.fillRect(left, top, rectWidth, rectHeight);
          context.strokeRect(left, top, rectWidth, rectHeight);
          context.save();
          context.setLineDash([5 * ratioX, 4 * ratioX]);
          drawLine(context, {x: first.x, y: first.y}, {x: second.x, y: first.y});
          drawLine(context, {x: centerX, y: first.y}, {x: centerX, y: second.y});
          context.restore();
          const horizontalDirection = second.x >= first.x ? 1 : -1;
          const horizontalArrowX = 8 * ratioX;
          const horizontalArrowY = 4 * ratioY;
          context.beginPath();
          context.moveTo(second.x, first.y);
          context.lineTo(second.x - (horizontalDirection * horizontalArrowX), first.y - horizontalArrowY);
          context.moveTo(second.x, first.y);
          context.lineTo(second.x - (horizontalDirection * horizontalArrowX), first.y + horizontalArrowY);
          context.stroke();
          const verticalDirection = second.y >= first.y ? 1 : -1;
          const verticalArrowX = 4 * ratioX;
          const verticalArrowY = 8 * ratioY;
          context.beginPath();
          context.moveTo(centerX, second.y);
          context.lineTo(centerX - verticalArrowX, second.y - (verticalDirection * verticalArrowY));
          context.moveTo(centerX, second.y);
          context.lineTo(centerX + verticalArrowX, second.y - (verticalDirection * verticalArrowY));
          context.stroke();
          context.fillStyle = '#78909c';
          context.strokeStyle = '#c7d5df';
          for (const anchor of [first, second]) {
            context.beginPath();
            context.arc(anchor.x, anchor.y, 4.5 * Math.max(ratioX, ratioY), 0, Math.PI * 2);
            context.fill();
            context.stroke();
          }
          const rulerLines = [
            `${formatAdaptivePrice(metrics.priceDelta)} (${metrics.percentChange.toFixed(2)}%)`,
            `${metrics.barCount}柱 (${metrics.bullishCount}阳${metrics.bearishCount}阴)`,
            formatDuration(metrics.elapsedDuration),
          ];
          let cardPaddingX = 8 * ratioX;
          let cardPaddingY = 5 * ratioY;
          let lineHeight = 18 * ratioY;
          let cardWidth = Math.max(...rulerLines.map((line) => context.measureText(line).width))
            + (cardPaddingX * 2);
          let cardHeight = (rulerLines.length * lineHeight) + (cardPaddingY * 2);
          const availableWidth = Math.max(ratioX, width - (8 * ratioX));
          const availableHeight = Math.max(ratioY, height - (8 * ratioY));
          const cardScale = Math.min(1, availableWidth / cardWidth, availableHeight / cardHeight);
          if (cardScale < 1) {
            context.font = `${12 * ratioY * cardScale}px sans-serif`;
            cardPaddingX *= cardScale;
            cardPaddingY *= cardScale;
            lineHeight *= cardScale;
            cardWidth = Math.max(...rulerLines.map((line) => context.measureText(line).width))
              + (cardPaddingX * 2);
            cardHeight = (rulerLines.length * lineHeight) + (cardPaddingY * 2);
          }
          const marginX = 4 * ratioX;
          const marginY = 4 * ratioY;
          const cardGap = 8 * ratioY;
          const preferredX = centerX - (cardWidth / 2);
          const aboveY = top - cardHeight - cardGap;
          const belowY = top + rectHeight + cardGap;
          const preferredY = aboveY >= marginY
            ? aboveY
            : belowY + cardHeight <= height - marginY
              ? belowY
              : top + ((rectHeight - cardHeight) / 2);
          const cardX = clamp(preferredX, marginX, width - cardWidth - marginX);
          const cardY = clamp(preferredY, marginY, height - cardHeight - marginY);
          context.fillStyle = 'rgba(10, 63, 66, 0.94)';
          context.fillRect(cardX, cardY, cardWidth, cardHeight);
          context.fillStyle = '#f4fbfb';
          context.textBaseline = 'middle';
          rulerLines.forEach((line, index) => {
            context.fillText(
              line,
              cardX + cardPaddingX,
              cardY + cardPaddingY + (lineHeight * index) + (lineHeight / 2)
            );
          });
        } else if (model.type === 'long' || model.type === 'short' || model.type === 'risk-reward') {
          const entry = first;
          const stop = second;
          const target = points[2];
          if (!target) {
            context.restore();
            return;
          }
          const right = Math.max(stop.x, target.x);
          const rectWidth = Math.max(ratioX, right - entry.x);
          context.fillStyle = 'rgba(239, 83, 80, 0.20)';
          context.fillRect(entry.x, Math.min(entry.y, stop.y), rectWidth, Math.abs(stop.y - entry.y));
          context.fillStyle = 'rgba(38, 166, 154, 0.20)';
          context.fillRect(entry.x, Math.min(entry.y, target.y), rectWidth, Math.abs(target.y - entry.y));
          context.strokeStyle = '#087f78';
          drawLine(context, {x: entry.x, y: entry.y}, {x: right, y: entry.y});
          context.strokeStyle = '#ef5350';
          drawLine(context, {x: entry.x, y: stop.y}, {x: right, y: stop.y});
          context.strokeStyle = '#26a69a';
          drawLine(context, {x: entry.x, y: target.y}, {x: right, y: target.y});
          context.strokeStyle = strokeColor;
          if (model.hovered) {
            const side = model.type === 'risk-reward' ? model.side : model.type;
            const metrics = calculateRiskReward(
              side,
              model.anchors[0].price,
              model.anchors[1].price,
              model.anchors[2].price,
              model.options
            );
            const labelX = entry.x + (4 * ratioX);
            const labels = [
              {
                key: 'stop', y: stop.y, color: '#ef5350',
                text: `止损 ${formatAdaptivePrice(metrics.stop)} · -${metrics.riskPercent.toFixed(2)}%`,
              },
              {
                key: 'entry', y: entry.y, color: '#087f78',
                text: `入场 ${formatAdaptivePrice(metrics.entry)} · RR ${metrics.rewardRiskRatio.toFixed(2)}`,
              },
              {
                key: 'target', y: target.y, color: '#26a69a',
                text: `止盈 ${formatAdaptivePrice(metrics.target)} · +${metrics.rewardPercent.toFixed(2)}%`,
              },
            ];
            const labelTops = layoutRiskLabelTops(labels, height, ratioY);
            labels.forEach((label) => {
              drawLabel(
                context, label.text, labelX, labelTops.get(label.key), label.color,
                ratioX, ratioY, {width, height}
              );
            });
          }
        } else {
          drawLine(context, first, second);
        }

        if (model.selected && !model.locked) {
          context.fillStyle = '#ffffff';
          for (const anchor of points.filter(Boolean)) {
            context.beginPath();
            context.arc(anchor.x, anchor.y, 4 * Math.max(ratioX, ratioY), 0, Math.PI * 2);
            context.fill();
            context.stroke();
          }
        }
        context.restore();
      });
    }
  }

  class DrawingPaneView {
    constructor(primitive) {
      this._renderer = new DrawingPaneRenderer(primitive);
    }

    zOrder() {
      return 'top';
    }

    renderer() {
      return this._renderer;
    }
  }

  // lightweight-charts 每帧会读取 text()/coordinate()/颜色等方法，
  // 在右侧价格轴内绘制原生高亮标签（AiCoin 选中图形时的轴价格效果）。
  class DrawingPriceAxisView {
    constructor(primitive, slot) {
      this._primitive = primitive;
      this._slot = slot;
    }

    _state() {
      return this._primitive.axisLabelState(this._slot);
    }

    coordinate() {
      const state = this._state();
      return state.visible ? state.coordinate : 0;
    }

    fixedCoordinate() {
      return null;
    }

    text() {
      const state = this._state();
      return state.visible ? state.text : '';
    }

    textColor() {
      return this._state().textColor || '#131722';
    }

    backColor() {
      const state = this._state();
      return state.visible ? state.backColor : 'rgba(0, 0, 0, 0)';
    }

    visible() {
      return Boolean(this._state().visible);
    }

    tickVisible() {
      return this.visible();
    }
  }

  class DrawingPrimitive {
    constructor(model) {
      this._model = serializeDrawing(model);
      this._bars = [];
      this._timeProjection = null;
      this._chart = null;
      this._series = null;
      this._requestUpdate = null;
      this._paneBounds = null;
      this._axisColorsProvider = null;
      this._defaultColorProvider = null;
      this._paneView = new DrawingPaneView(this);
      // lightweight-charts 按数组引用缓存轴视图包装：池大小变化时才重建并返回新数组。
      this._priceAxisViews = [];
      this._axisViewsCache = null;
    }

    attached(parameters) {
      this._chart = parameters.chart;
      this._series = parameters.series;
      this._requestUpdate = parameters.requestUpdate;
    }

    detached() {
      this._chart = null;
      this._series = null;
      this._requestUpdate = null;
    }

    model() {
      return clone(this._model);
    }

    setModel(model) {
      this._model = serializeDrawing(model);
      if (this._requestUpdate) this._requestUpdate();
    }

    setBars(bars) {
      const nextBars = Array.isArray(bars) ? bars : [];
      if (this._bars === nextBars) return false;
      this._bars = nextBars;
      this._timeProjection = createTimeProjectionContext(nextBars);
      if (this._requestUpdate) this._requestUpdate();
      return true;
    }

    usesBars() {
      return true;
    }

    requestUpdate() {
      if (this._requestUpdate) this._requestUpdate();
    }

    setPaneBounds(width, height) {
      this._paneBounds = {
        left: 0,
        top: 0,
        right: width,
        bottom: height,
      };
    }

    rulerMetrics() {
      if (this._model.type !== 'ruler') return null;
      return calculateRulerMetrics(
        this._model.anchors[0],
        this._model.anchors[1],
        {...this._model.options, bars: this._bars}
      );
    }

    priceToCoordinate(price) {
      if (!this._series) return null;
      return this._series.priceToCoordinate(price);
    }

    setAxisLabelColors(provider) {
      this._axisColorsProvider = typeof provider === 'function' ? provider : null;
    }

    setDefaultStrokeColor(provider) {
      this._defaultColorProvider = typeof provider === 'function' ? provider : null;
    }

    defaultStrokeColor() {
      if (this._defaultColorProvider) {
        try {
          const color = this._defaultColorProvider();
          if (typeof color === 'string' && color) return color;
        } catch (error) {
          // 主题提供器异常时回退到默认蓝色。
        }
      }
      return '#5b8ff9';
    }

    priceAxisViews() {
      const needed = this._axisSlotCount();
      if (!this._axisViewsCache || this._axisViewsCache.count !== needed) {
        this._priceAxisViews = Array.from(
          {length: needed},
          (unused, slot) => new DrawingPriceAxisView(this, slot)
        );
        this._axisViewsCache = {count: needed, views: this._priceAxisViews};
      }
      return this._priceAxisViews;
    }

    _axisSlotCount() {
      const model = this._model;
      if (model.type === 'fib-trend-time') {
        // 垂直时间线不使用价格轴标签（倍数标签绘制在 chart 顶部/底部）。
        return 0;
      }
      return 3;
    }

    // 轴标签条目：fib-trend-time 不输出价格轴标签（倍数标签绘制在 chart 顶部/底部）。
    _axisLabelEntries() {
      const model = this._model;
      if (model.type === 'fib-trend-time') {
        return [];
      }
      return axisLabelPrices(model).map((price) => ({price, backColor: null, textColor: null}));
    }

    formatAxisPrice(price) {
      try {
        const options = this._series && typeof this._series.options === 'function'
          ? this._series.options()
          : null;
        const precision = options && options.priceFormat
          ? Number(options.priceFormat.precision)
          : NaN;
        if (Number.isFinite(precision) && precision >= 0 && precision <= 8) {
          return price.toFixed(precision);
        }
      } catch (error) {
        // 无法读取序列精度时使用自适应精度。
      }
      return formatAdaptivePrice(price);
    }

    axisLabelState(slot) {
      const inactive = {visible: false};
      const model = this._model;
      if (model.hidden || (!model.selected && !model.hovered)) return inactive;
      const entries = this._axisLabelEntries();
      if (!Number.isInteger(slot) || slot < 0 || slot >= entries.length) return inactive;
      const entry = entries[slot];
      const coordinate = this.priceToCoordinate(entry.price);
      if (!Number.isFinite(coordinate)) return inactive;
      // 超出可见区间的档位/锚点不显示轴标签，避免标签堆积在轴边缘。
      if (this._paneBounds
          && (coordinate < 0 || coordinate > this._paneBounds.bottom)) return inactive;
      const text = this.formatAxisPrice(entry.price);
      for (let index = 0; index < slot; index += 1) {
        if (this.formatAxisPrice(entries[index].price) === text) return inactive;
      }
      const colors = entry.backColor
        ? {background: entry.backColor, text: entry.textColor || '#ffffff'}
        : this._resolveAxisLabelColors();
      return {
        visible: true,
        coordinate,
        text,
        textColor: colors.text,
        backColor: colors.background,
      };
    }

    _resolveAxisLabelColors() {
      if (this._axisColorsProvider) {
        try {
          const colors = this._axisColorsProvider();
          if (colors && colors.background && colors.text) return colors;
        } catch (error) {
          // 主题提供器异常时使用默认高亮配色。
        }
      }
      return {background: '#e8ecf1', text: '#131722'};
    }

    projectAnchors() {
      if (!this._chart || !this._series) return [];
      const timeScale = this._chart.timeScale();
      return this._model.anchors.map((anchor) => {
        let projectedTime = anchor.time;
        let x = projectedTimeToCoordinate(timeScale, projectedTime, this._timeProjection);
        if (!Number.isFinite(x) && this._bars.length) {
          const nearest = this._bars.reduce((best, bar) => (
            !best || Math.abs(bar.time - anchor.time) < Math.abs(best.time - anchor.time) ? bar : best
          ), null);
          if (nearest) {
            projectedTime = nearest.time;
            x = timeScale.timeToCoordinate(projectedTime);
          }
        }
        const y = this._series.priceToCoordinate(anchor.price);
        return Number.isFinite(x) && Number.isFinite(y) ? {x, y} : null;
      });
    }

    paneViews() {
      if (!this._chart || this._model.hidden) return [];
      return [this._paneView];
    }

    autoscaleInfo() {
      return null;
    }

    hitTest(x, y) {
      if (this._model.hidden) return null;
      const anchors = this.projectAnchors();
      if (anchors.length === 0 || !anchors.some(Boolean)) return null;
      const point = {x, y};
      if (this._model.locked) {
        const distance = this._bodyDistance(point, anchors, 8);
        if (distance != null) return this._hitItem('body', distance, {locked: true});
        return null;
      }
      if (this._model.selected) {
        const anchorIndex = anchors.findIndex((anchor) => anchor
          && Math.hypot(x - anchor.x, y - anchor.y) <= 8);
        if (anchorIndex >= 0) {
          const anchor = anchors[anchorIndex];
          return this._hitItem('anchor', Math.hypot(x - anchor.x, y - anchor.y), {anchorIndex});
        }
      }
      const distance = this._bodyDistance(point, anchors, 6);
      return distance == null ? null : this._hitItem('body', distance);
    }

    _hitItem(hitKind, distance, extras) {
      const isAnchor = hitKind === 'anchor';
      const anchorSuffix = isAnchor ? `:${extras.anchorIndex}` : '';
      return {
        externalId: `${this._model.id}:${hitKind}${anchorSuffix}`,
        zOrder: 'top',
        cursorStyle: this._model.locked ? 'default' : (isAnchor ? 'grab' : 'move'),
        itemType: 'primitive',
        distance,
        hitTestPriority: isAnchor ? 2 : 1,
        drawingId: this._model.id,
        hitKind,
        ...(extras || {}),
      };
    }

    _bodyDistance(point, anchors, tolerance) {
      const first = anchors[0];
      const second = anchors[1] || first;
      if (!first) return null;
      if (this._model.type === 'horizontal') {
        const distance = Math.abs(point.y - first.y);
        return distance <= tolerance ? distance : null;
      }
      if (this._model.type === 'rectangle' || this._model.type === 'ruler'
          || this._model.type === 'long' || this._model.type === 'short'
          || this._model.type === 'risk-reward') {
        const visibleAnchors = anchors.filter(Boolean);
        if (visibleAnchors.length < 2) return null;
        const xs = visibleAnchors.map((anchor) => anchor.x);
        const ys = visibleAnchors.map((anchor) => anchor.y);
        return point.x >= Math.min(...xs) - tolerance && point.x <= Math.max(...xs) + tolerance
          && point.y >= Math.min(...ys) - tolerance && point.y <= Math.max(...ys) + tolerance ? 0 : null;
      }
      if (this._model.type === 'text') {
        return Math.abs(point.x - first.x) <= 40 && Math.abs(point.y - first.y) <= 16 ? 0 : null;
      }
      if (this._model.type === 'fibonacci') {
        if (!second) return null;
        const left = Math.min(first.x, second.x) - tolerance;
        const right = Math.max(first.x, second.x) + tolerance;
        const distances = calculateFibonacciLevels(
          this._model.anchors[0].price,
          this._model.anchors[1].price,
          this._model.options
        ).map((level) => Math.abs(point.y - this.priceToCoordinate(level.price)));
        const distance = Math.min(...distances);
        return point.x >= left && point.x <= right && distance <= tolerance ? distance : null;
      }
      if (this._model.type === 'fib-trend-time') {
        if (!second) return null;
        // 垂直时间线：纯像素命中（与渲染一致：x = second.x + ratio × |ΔX|）。
        const deltaX = Math.abs(second.x - first.x);
        const distances = (this._model.options.levels || [])
          .filter((level) => level && level.enabled !== false)
          .map((level) => {
            const x = second.x + Number(level.value || 0) * deltaX;
            return Number.isFinite(x) ? Math.abs(point.x - x) : Infinity;
          });
        if (!distances.length) return null;
        const distance = Math.min(...distances);
        return Number.isFinite(distance) && distance <= tolerance ? distance : null;
      }
      if (!second) return null;
      const lineEnd = this._model.type === 'ray' && this._paneBounds
        ? calculateRayEndpoint(first, second, this._paneBounds)
        : second;
      const distance = distanceToSegment(point, first, lineEnd);
      return distance <= tolerance ? distance : null;
    }
  }

  function normalizePointerEvent(event, element) {
    const source = event.touches && event.touches.length
      ? event.touches[0]
      : event.changedTouches && event.changedTouches.length
        ? event.changedTouches[0]
        : event;
    const rect = element.getBoundingClientRect();
    const clientX = assertFinite(source.clientX, 'pointer.clientX');
    const clientY = assertFinite(source.clientY, 'pointer.clientY');
    return {
      x: clientX - rect.left,
      y: clientY - rect.top,
      clientX,
      clientY,
      pointerId: source.pointerId == null
        ? (source.identifier == null ? 1 : source.identifier)
        : source.pointerId,
    };
  }

  const TOOL_POINT_COUNTS = Object.freeze({
    horizontal: 1,
    text: 1,
    trend: 2,
    ray: 2,
    rectangle: 2,
    fibonacci: 2,
    'fib-trend-time': 2,
    ruler: 2,
    long: 3,
    short: 3,
    'long-position': 3,
    'short-position': 3,
    'risk-reward': 3,
  });

  class DrawingController {
    constructor(parameters) {
      if (!parameters || !parameters.chart || !parameters.series || !parameters.element) {
        throw new TypeError('chart, series, and element are required');
      }
      this.chart = parameters.chart;
      this.series = parameters.series;
      this.element = parameters.element;
      this.keyTarget = parameters.keyTarget
        || (typeof document !== 'undefined' ? document : this.element);
      this.store = parameters.store || new DrawingStore();
      this.onError = parameters.onError || null;
      this.onInteractionStateChange = parameters.onInteractionStateChange
        || parameters.onInteractionChange
        || null;
      this.onToolChange = parameters.onToolChange || null;
      this.onSelectionChange = parameters.onSelectionChange || null;
      this.accountSizeProvider = parameters.accountSizeProvider || null;
      this.accountRiskPercent = Number.isFinite(parameters.accountRiskPercent)
        ? parameters.accountRiskPercent
        : 1;
      this.axisLabelColors = parameters.axisLabelColors || null;
      this.defaultDrawingColor = parameters.defaultDrawingColor || null;
      const animationHost = typeof globalThis !== 'undefined' ? globalThis : null;
      this._requestAnimationFrame = parameters.requestAnimationFrame
        || (animationHost && typeof animationHost.requestAnimationFrame === 'function'
          ? animationHost.requestAnimationFrame.bind(animationHost)
          : (callback) => { callback(); return null; });
      this._cancelAnimationFrame = parameters.cancelAnimationFrame
        || (animationHost && typeof animationHost.cancelAnimationFrame === 'function'
          ? animationHost.cancelAnimationFrame.bind(animationHost)
          : () => {});
      this.activeTool = null;
      this.selectedId = null;
      this._hoveredId = null;
      this._draftAnchors = [];
      this._draftPrimitive = null;
      this._gesture = null;
      this._interactionType = null;
      this._capturedPointerId = null;
      this._pendingPointerMove = null;
      this._pointerMoveFrame = null;
      this._bars = clone(Array.isArray(parameters.bars) ? parameters.bars : []);
      this._timeProjection = createTimeProjectionContext(this._bars);
      this._primitives = new Map();
      this._boundPointerDown = (event) => this._onPointerDown(event);
      this._boundPointerMove = (event) => this._onPointerMove(event);
      this._boundPointerUp = (event) => this._onPointerUp(event);
      this._boundPointerCancel = (event) => this._onPointerCancel(event);
      this._boundPointerLeave = () => this._onPointerLeave();
      this._boundKeyDown = (event) => this._onKeyDown(event);
      this._emitSelectionChange = () => {
        if (!this.onSelectionChange) return;
        const model = this.selectedId ? this.store.get(this.selectedId) : null;
        this.onSelectionChange(this.selectedId, model);
      };
      this.element.addEventListener('pointerdown', this._boundPointerDown);
      this.element.addEventListener('pointermove', this._boundPointerMove);
      this.element.addEventListener('pointerup', this._boundPointerUp);
      this.element.addEventListener('pointercancel', this._boundPointerCancel);
      this.element.addEventListener('pointerleave', this._boundPointerLeave);
      this.keyTarget.addEventListener('keydown', this._boundKeyDown);
      this.refresh();
    }

    activateTool(tool) {
      if (tool !== 'select' && !TOOL_POINT_COUNTS[tool]) {
        throw new RangeError(`unsupported drawing tool: ${tool}`);
      }
      this.cancelGesture();
      this.activeTool = tool;
      if (tool !== 'select') this.select(null);
      if (this.onToolChange) this.onToolChange(tool);
      return tool;
    }

    select(id) {
      this.selectedId = id && this.store.get(id) ? id : null;
      this.refresh();
      if (this.onSelectionChange) {
        const selectedModel = this.selectedId ? this.store.get(this.selectedId) : null;
        this.onSelectionChange(this.selectedId, selectedModel);
      }
      return this.selectedId;
    }

    refresh() {
      const drawings = this.store.snapshot();
      const drawingIds = new Set(drawings.map((model) => model.id));
      for (const [id, primitive] of this._primitives) {
        if (!drawingIds.has(id)) {
          this._detachPrimitive(primitive);
          this._primitives.delete(id);
        }
      }
      for (const model of drawings) {
        const viewModel = {
          ...model,
          selected: model.id === this.selectedId,
          hovered: model.id === this._hoveredId,
        };
        let primitive = this._primitives.get(model.id);
        if (!primitive) {
          primitive = new DrawingPrimitive(viewModel);
          this._configurePrimitive(primitive);
          this._primitives.set(model.id, primitive);
          primitive.setBars(this._bars);
          this._attachPrimitive(primitive);
        } else {
          primitive.setModel(viewModel);
          primitive.setBars(this._bars);
        }
      }
    }

    _configurePrimitive(primitive) {
      primitive.setAxisLabelColors(this.axisLabelColors);
      primitive.setDefaultStrokeColor(this.defaultDrawingColor);
    }

    setBars(bars) {
      this._bars = clone(Array.isArray(bars) ? bars : []);
      this._timeProjection = createTimeProjectionContext(this._bars);
      for (const primitive of this._primitives.values()) {
        if (primitive.usesBars()) primitive.setBars(this._bars);
      }
      if (this._draftPrimitive && this._draftPrimitive.usesBars()) {
        this._draftPrimitive.setBars(this._bars);
      }
      return this._bars.length;
    }

    requestUpdate() {
      for (const primitive of this._primitives.values()) primitive.requestUpdate();
      if (this._draftPrimitive) this._draftPrimitive.requestUpdate();
      return this._primitives.size + (this._draftPrimitive ? 1 : 0);
    }

    getRulerMetrics(id) {
      const model = this.store.get(id || this.selectedId);
      if (!model || model.type !== 'ruler') return null;
      return calculateRulerMetrics(
        model.anchors[0],
        model.anchors[1],
        {...model.options, bars: this._bars}
      );
    }

    rebind(parameters) {
      if (!parameters || !parameters.chart || !parameters.series) {
        throw new TypeError('chart and series are required');
      }
      for (const primitive of this._primitives.values()) this._detachPrimitive(primitive);
      if (this._draftPrimitive) this._detachPrimitive(this._draftPrimitive);
      this.chart = parameters.chart;
      this.series = parameters.series;
      for (const primitive of this._primitives.values()) this._attachPrimitive(primitive);
      if (this._draftPrimitive) this._attachPrimitive(this._draftPrimitive);
      this.refresh();
    }

    getFibonacciSettings(id) {
      const model = this.store.get(id || this.selectedId);
      if (!model || (model.type !== 'fibonacci' && model.type !== 'fib-trend-time')) return null;
      const defaults = model.type === 'fib-trend-time'
        ? defaultFibTrendTimeSettings()
        : defaultFibonacciSettings();
      return normalizeFibonacciSettings(model.options, defaults);
    }

    getSelectedFibonacciSettings() {
      return this.getFibonacciSettings();
    }

    updateFibonacciSettings(patch, id) {
      const drawingId = id || this.selectedId;
      const model = this.store.get(drawingId);
      if (!model || model.locked) return null;
      if (model.type !== 'fibonacci' && model.type !== 'fib-trend-time') return null;
      const defaults = model.type === 'fib-trend-time'
        ? defaultFibTrendTimeSettings()
        : defaultFibonacciSettings();
      const incoming = {...(patch || {})};
      if (model.type === 'fib-trend-time' && Array.isArray(incoming.levels)) {
        // 面板行只带 value/color/enabled：标签补成倍数本身（如 2.618），避免百分比样式。
        incoming.levels = incoming.levels.map((level) => (
          level && typeof level === 'object' && level.label == null
            ? {...level, label: `${level.value}`}
            : level
        ));
      }
      const options = normalizeFibonacciSettings({...model.options, ...incoming}, defaults);
      this.store.update(drawingId, {...model, options});
      this.refresh();
      return clone(options);
    }

    updateSelectedFibonacciSettings(patch) {
      return this.updateFibonacciSettings(patch);
    }

    setFibonacciLevelEnabled(indexOrValue, enabled, id) {
      const settings = this.getFibonacciSettings(id);
      if (!settings) return null;
      const index = this._resolveFibonacciLevelIndex(settings.levels, indexOrValue);
      if (index < 0) return null;
      settings.levels[index] = {...settings.levels[index], enabled: Boolean(enabled)};
      return this.updateFibonacciSettings({levels: settings.levels}, id);
    }

    enableFibonacciLevel(indexOrValue, enabled, id) {
      return this.setFibonacciLevelEnabled(indexOrValue, enabled, id);
    }

    addFibonacciLevel(level, index, id) {
      const settings = this.getFibonacciSettings(id);
      if (!settings) return null;
      const model = this.store.get(id || this.selectedId);
      const definition = typeof level === 'number' ? {value: level} : clone(level || {});
      if (model && model.type === 'fib-trend-time' && definition.label == null) {
        definition.label = `${definition.value}`;
      }
      const insertionIndex = Number.isInteger(index)
        ? Math.max(0, Math.min(index, settings.levels.length))
        : settings.levels.length;
      settings.levels.splice(insertionIndex, 0, normalizeFibonacciLevel(definition));
      return this.updateFibonacciSettings({levels: settings.levels}, id);
    }

    removeFibonacciLevel(indexOrValue, id) {
      const settings = this.getFibonacciSettings(id);
      if (!settings) return null;
      const index = this._resolveFibonacciLevelIndex(settings.levels, indexOrValue);
      if (index < 0) return null;
      settings.levels.splice(index, 1);
      return this.updateFibonacciSettings({levels: settings.levels}, id);
    }

    reorderFibonacciLevel(fromIndex, toIndex, id) {
      const settings = this.getFibonacciSettings(id);
      if (!settings || !Number.isInteger(fromIndex) || !Number.isInteger(toIndex)
          || fromIndex < 0 || fromIndex >= settings.levels.length) return null;
      const targetIndex = Math.max(0, Math.min(toIndex, settings.levels.length - 1));
      const [level] = settings.levels.splice(fromIndex, 1);
      settings.levels.splice(targetIndex, 0, level);
      return this.updateFibonacciSettings({levels: settings.levels}, id);
    }

    moveFibonacciLevel(fromIndex, toIndex, id) {
      return this.reorderFibonacciLevel(fromIndex, toIndex, id);
    }

    resetFibonacciSettings(id) {
      const drawingId = id || this.selectedId;
      const model = this.store.get(drawingId);
      if (!model) return null;
      const defaults = model.type === 'fib-trend-time'
        ? defaultFibTrendTimeSettings()
        : defaultFibonacciSettings();
      return this.updateFibonacciSettings(defaults, drawingId);
    }

    /**
     * 通用：获取/更新任意画图工具的线条设置（horizontal/trend/ray/rectangle/ruler/text）。
     * 提供统一接口，前端设置面板按 model.type 分派调用。
     */
    getSelectedLineSettings() {
      const model = this.selectedId ? this.store.get(this.selectedId) : null;
      if (!model) return null;
      const type = normalizeDrawingType(model.type);
      const getMap = {
        fibonacci: () => normalizeFibonacciSettings(model.options),
        'fib-trend-time': () => normalizeFibonacciSettings(model.options, defaultFibTrendTimeSettings()),
        rectangle: () => normalizeRectangleOptions(model.options),
        text: () => normalizeTextOptions(model.options),
      };
      const getter = getMap[type] || (() => normalizeLineOptions(model.options));
      return getter();
    }

    updateSelectedLineSettings(patch) {
      const model = this.selectedId ? this.store.get(this.selectedId) : null;
      if (!model || model.locked) return null;
      const type = normalizeDrawingType(model.type);
      const merged = {...model.options, ...(patch || {})};
      let next;
      try {
        if (type === 'fibonacci') next = normalizeFibonacciSettings(merged);
        else if (type === 'fib-trend-time') next = normalizeFibonacciSettings(merged, defaultFibTrendTimeSettings());
        else if (type === 'rectangle') next = normalizeRectangleOptions(merged);
        else if (type === 'text') next = normalizeTextOptions(merged);
        else next = normalizeLineOptions(merged);
      } catch (error) {
        return null;
      }
      this.store.update(model.id, {...model, options: next});
      this.refresh();
      return clone(next);
    }

    undo() {
      const changed = this.store.undo();
      if (changed) {
        if (this.selectedId && !this.store.get(this.selectedId)) this.selectedId = null;
        this.refresh();
        this._emitSelectionChange();
      }
      return changed;
    }

    redo() {
      const changed = this.store.redo();
      if (changed) {
        this.refresh();
        this._emitSelectionChange();
      }
      return changed;
    }

    clearAll() {
      const changed = this.store.clear();
      if (changed) {
        this.selectedId = null;
        this.refresh();
        this._emitSelectionChange();
      }
      return changed;
    }

    resetAll() {
      const changed = this.store.reset();
      this.selectedId = null;
      this.cancelGesture();
      this.refresh();
      return changed;
    }

    toggleLock() {
      if (!this.selectedId) return false;
      const updated = this.store.update(this.selectedId, (model) => ({...model, locked: !model.locked}));
      if (!updated) return false;
      this.refresh();
      return true;
    }

    toggleHidden() {
      if (!this.selectedId) return false;
      const updated = this.store.update(this.selectedId, (model) => ({...model, hidden: !model.hidden}));
      if (!updated) return false;
      this.refresh();
      return true;
    }

    deleteSelected() {
      if (!this.selectedId) return false;
      const selected = this.store.get(this.selectedId);
      if (!selected || selected.locked) return false;
      const removed = this.store.remove(this.selectedId);
      if (removed) {
        this.selectedId = null;
        this.refresh();
      }
      return removed;
    }

    cancelGesture() {
      const gesture = this._gesture;
      this._cancelPendingPointerMove();
      this._clearDraftPrimitive();
      this._draftAnchors = [];
      this._gesture = null;
      this._releasePointerCapture();
      if (gesture && gesture.type !== 'create') this.refresh();
      if (gesture) this._setInteractionState(false, gesture.type);
    }

    destroy() {
      this.cancelGesture();
      this.element.removeEventListener('pointerdown', this._boundPointerDown);
      this.element.removeEventListener('pointermove', this._boundPointerMove);
      this.element.removeEventListener('pointerup', this._boundPointerUp);
      this.element.removeEventListener('pointercancel', this._boundPointerCancel);
      this.element.removeEventListener('pointerleave', this._boundPointerLeave);
      this.keyTarget.removeEventListener('keydown', this._boundKeyDown);
      for (const primitive of this._primitives.values()) {
        this._detachPrimitive(primitive);
      }
      this._primitives.clear();
      this.selectedId = null;
      this._hoveredId = null;
      this.activeTool = null;
    }

    _attachPrimitive(primitive) {
      if (typeof this.series.attachPrimitive === 'function') this.series.attachPrimitive(primitive);
      if (!primitive._chart) {
        primitive.attached({chart: this.chart, series: this.series, requestUpdate() {}});
      }
    }

    _detachPrimitive(primitive) {
      if (typeof this.series.detachPrimitive === 'function') this.series.detachPrimitive(primitive);
      primitive.detached();
    }

    _resolveFibonacciLevelIndex(levels, indexOrValue) {
      if (Number.isInteger(indexOrValue) && indexOrValue >= 0 && indexOrValue < levels.length) {
        return indexOrValue;
      }
      return levels.findIndex((level) => level.value === indexOrValue);
    }

    _safePointerEvent(event) {
      try {
        return {...normalizePointerEvent(event, this.element), altKey: Boolean(event && event.altKey)};
      } catch (error) {
        return null;
      }
    }

    _setHoveredId(id) {
      const nextId = id && this.store.get(id) ? id : null;
      if (nextId === this._hoveredId) return false;
      this._hoveredId = nextId;
      this.refresh();
      return true;
    }

    _onPointerLeave() {
      if (!this._gesture) this._setHoveredId(null);
    }

    _setInteractionState(active, type) {
      const nextType = active ? type : null;
      if (this._interactionType === nextType) return;
      this._interactionType = nextType;
      if (this.onInteractionStateChange) {
        this.onInteractionStateChange(Boolean(active), {
          type,
          tool: this.activeTool,
          drawingId: this.selectedId,
        });
      }
    }

    _cancelPendingPointerMove() {
      if (this._pointerMoveFrame != null) this._cancelAnimationFrame(this._pointerMoveFrame);
      this._pointerMoveFrame = null;
      this._pendingPointerMove = null;
    }

    _clearDraftPrimitive() {
      if (!this._draftPrimitive) return;
      this._detachPrimitive(this._draftPrimitive);
      this._draftPrimitive = null;
    }

    _setDraftModel(model) {
      if (!this._draftPrimitive) {
        this._draftPrimitive = new DrawingPrimitive(model);
        this._configurePrimitive(this._draftPrimitive);
        this._draftPrimitive.setBars(this._bars);
        this._attachPrimitive(this._draftPrimitive);
      } else {
        this._draftPrimitive.setModel(model);
        this._draftPrimitive.setBars(this._bars);
      }
    }

    _createModelForTool(tool, anchors, id) {
      const normalizedType = normalizeDrawingType(tool);
      const config = {id, selected: Boolean(id)};
      if (normalizedType === 'risk-reward') config.side = 'long';
      if (normalizedType === 'long' || normalizedType === 'short'
          || normalizedType === 'risk-reward') {
        let accountSize = NaN;
        if (this.accountSizeProvider) {
          try {
            accountSize = Number(this.accountSizeProvider());
          } catch (error) {
            accountSize = NaN;
          }
        }
        const riskPerUnit = anchors.length >= 2
          ? Math.abs(anchors[0].price - anchors[1].price)
          : NaN;
        if (Number.isFinite(accountSize) && accountSize > 0 && Number.isFinite(riskPerUnit)
            && riskPerUnit > 0) {
          const accountRiskAmount = accountSize * this.accountRiskPercent / 100;
          config.accountSize = accountSize;
          config.accountRiskPercent = this.accountRiskPercent;
          config.accountRiskAmount = accountRiskAmount;
          config.positionSize = accountRiskAmount / riskPerUnit;
        }
      }
      const model = createDrawingModel(tool, anchors, config);
      if (id === DRAFT_DRAWING_ID) model.hovered = true;
      return model;
    }

    _riskAnchors(tool, start, end) {
      const normalizedType = normalizeDrawingType(tool);
      const side = normalizedType === 'risk-reward' ? 'long' : normalizedType;
      const delta = end.price - start.price;
      if (!Number.isFinite(delta) || delta === 0) return null;
      let stopPrice;
      let targetPrice;
      if (side === 'long') {
        if (delta < 0) {
          stopPrice = end.price;
          targetPrice = start.price + (Math.abs(delta) * DEFAULT_RISK_REWARD_RATIO);
        } else {
          targetPrice = end.price;
          stopPrice = start.price - (Math.abs(delta) / DEFAULT_RISK_REWARD_RATIO);
        }
      } else if (delta > 0) {
        stopPrice = end.price;
        targetPrice = start.price - (Math.abs(delta) * DEFAULT_RISK_REWARD_RATIO);
      } else {
        targetPrice = end.price;
        stopPrice = start.price + (Math.abs(delta) / DEFAULT_RISK_REWARD_RATIO);
      }
      return [
        clone(start),
        {time: end.time, price: stopPrice},
        {time: end.time, price: targetPrice},
      ];
    }

    _creationAnchors(tool, start, end) {
      const normalizedType = normalizeDrawingType(tool);
      if (normalizedType === 'horizontal' || normalizedType === 'text') return [clone(end)];
      if (normalizedType === 'long' || normalizedType === 'short'
          || normalizedType === 'risk-reward') {
        return this._riskAnchors(tool, start, end);
      }
      if (start.time === end.time && start.price === end.price) return null;
      return [clone(start), clone(end)];
    }

    _defaultCreationAnchors(tool, anchor) {
      const normalizedType = normalizeDrawingType(tool);
      if (normalizedType === 'long' || normalizedType === 'short'
          || normalizedType === 'risk-reward') {
        const side = normalizedType === 'risk-reward' ? 'long' : normalizedType;
        const offset = Math.max(Math.abs(anchor.price) * 0.001, 0.000001);
        const end = {
          time: anchor.time,
          price: side === 'long' ? anchor.price - offset : anchor.price + offset,
        };
        return this._riskAnchors(tool, anchor, end);
      }
      if (normalizedType === 'horizontal' || normalizedType === 'text') return [clone(anchor)];
      return [clone(anchor), clone(anchor)];
    }

    _anchorFromPoint(point, altKey) {
      const timeScale = this.chart.timeScale();
      let time = coordinateToProjectedTime(timeScale, point.x, this._timeProjection);
      let price = this.series.coordinateToPrice(point.y);
      if (!altKey && Array.isArray(this._bars) && this._bars.length) {
        let snapBar = null;
        let snapDistance = Infinity;
        for (const bar of this._bars) {
          const barX = timeScale.timeToCoordinate(bar.time);
          if (!Number.isFinite(barX)) continue;
          const distance = Math.abs(point.x - barX);
          if (distance <= SNAP_DISTANCE_PX && distance < snapDistance) {
            snapBar = bar;
            snapDistance = distance;
          }
        }
        if (snapBar) {
          time = snapBar.time;
          let snapPrice = null;
          let priceDistance = Infinity;
          for (const key of ['open', 'high', 'low', 'close']) {
            if (!Number.isFinite(snapBar[key])) continue;
            const coordinate = this.series.priceToCoordinate(snapBar[key]);
            if (!Number.isFinite(coordinate)) continue;
            const distance = Math.abs(point.y - coordinate);
            if (distance <= SNAP_DISTANCE_PX && distance < priceDistance) {
              snapPrice = snapBar[key];
              priceDistance = distance;
            }
          }
          if (snapPrice != null) price = snapPrice;
        }
      }
      try {
        return normalizeAnchor({time, price});
      } catch (error) {
        return null;
      }
    }

    _capturePointer(pointerId) {
      this._capturedPointerId = pointerId;
      if (typeof this.element.setPointerCapture === 'function') {
        this.element.setPointerCapture(pointerId);
      }
    }

    _releasePointerCapture() {
      if (this._capturedPointerId == null) return;
      if (typeof this.element.releasePointerCapture === 'function') {
        try {
          this.element.releasePointerCapture(this._capturedPointerId);
        } catch (error) {
          if (this.onError) this.onError(error);
        }
      }
      this._capturedPointerId = null;
    }

    _onPointerDown(event) {
      const point = this._safePointerEvent(event);
      if (!point) return;
      if (this.activeTool && this.activeTool !== 'select') {
        const anchor = this._anchorFromPoint(point, point.altKey);
        if (!anchor) return;
        try {
          const anchors = this._defaultCreationAnchors(this.activeTool, anchor);
          const preview = this._createModelForTool(this.activeTool, anchors, DRAFT_DRAWING_ID);
          this._gesture = {
            type: 'create',
            tool: this.activeTool,
            startAnchor: anchor,
            preview,
            invalid: false,
          };
          this._setDraftModel(preview);
        } catch (error) {
          if (this.onError) this.onError(error);
          return;
        }
        if (event.preventDefault) event.preventDefault();
        this._capturePointer(point.pointerId);
        this._setInteractionState(true, 'create');
        return;
      }
      const hit = this._hitTest(point.x, point.y);
      if (!hit) {
        this._hoveredId = null;
        this.select(null);
        this._gesture = null;
        return;
      }
      this._hoveredId = hit.drawingId;
      this.select(hit.drawingId);
      if (hit.locked) {
        this._gesture = null;
        return;
      }
      if (event.preventDefault) event.preventDefault();
      this._capturePointer(point.pointerId);
      const model = this.store.get(hit.drawingId);
      this._gesture = {
        type: hit.hitKind === 'anchor' ? 'anchor' : 'body',
        anchorIndex: hit.anchorIndex,
        startPoint: point,
        original: model,
        preview: model,
        invalid: false,
      };
      this._setInteractionState(true, this._gesture.type);
    }

    _processPointerMove(point) {
      const gesture = this._gesture;
      if (!gesture) return;
      if (gesture.type === 'create') {
        const endAnchor = this._anchorFromPoint(point, point.altKey);
        const anchors = endAnchor
          ? this._creationAnchors(gesture.tool, gesture.startAnchor, endAnchor)
          : null;
        if (!anchors) {
          gesture.invalid = true;
          return;
        }
        try {
          const preview = this._createModelForTool(gesture.tool, anchors, DRAFT_DRAWING_ID);
          gesture.invalid = false;
          gesture.preview = preview;
          this._setDraftModel(preview);
        } catch (error) {
          gesture.invalid = true;
        }
        return;
      }
      let anchors;
      if (gesture.type === 'anchor') {
        const movedAnchor = this._anchorFromPoint(point, point.altKey);
        if (!movedAnchor) {
          gesture.invalid = true;
          return;
        }
        anchors = gesture.original.anchors.map((anchor, index) => (
          index === gesture.anchorIndex ? movedAnchor : clone(anchor)
        ));
      } else {
        const deltaX = point.x - gesture.startPoint.x;
        const deltaY = point.y - gesture.startPoint.y;
        anchors = gesture.original.anchors.map((anchor) => {
          const originalX = projectedTimeToCoordinate(
            this.chart.timeScale(), anchor.time, this._timeProjection
          );
          const originalY = this.series.priceToCoordinate(anchor.price);
          if (!Number.isFinite(originalX) || !Number.isFinite(originalY)) return clone(anchor);
          return this._anchorFromPoint(
            {x: originalX + deltaX, y: originalY + deltaY},
            point.altKey
          ) || clone(anchor);
        });
      }
      const candidate = {...gesture.original, anchors};
      try {
        serializeDrawing(candidate);
      } catch (error) {
        gesture.invalid = true;
        return;
      }
      gesture.invalid = false;
      gesture.preview = candidate;
      const primitive = this._primitives.get(gesture.original.id);
      if (primitive) primitive.setModel({...gesture.preview, selected: true});
    }

    _onPointerMove(event) {
      const point = this._safePointerEvent(event);
      if (!point) return;
      if (!this._gesture) {
        const hit = this._hitTest(point.x, point.y);
        this._setHoveredId(hit ? hit.drawingId : null);
        return;
      }
      this._pendingPointerMove = point;
      if (this._pointerMoveFrame == null) {
        let completedSynchronously = false;
        const frame = this._requestAnimationFrame(() => {
          completedSynchronously = true;
          this._pointerMoveFrame = null;
          const pending = this._pendingPointerMove;
          this._pendingPointerMove = null;
          if (pending) this._processPointerMove(pending);
        });
        this._pointerMoveFrame = completedSynchronously ? null : frame;
      }
      if (event.preventDefault) event.preventDefault();
    }

    _onPointerUp(event) {
      const gesture = this._gesture;
      if (!gesture) return;
      const point = this._safePointerEvent(event);
      this._cancelPendingPointerMove();
      if (point) this._processPointerMove(point);
      if (gesture.type === 'create') {
        if (!gesture.invalid && gesture.preview && point) {
          try {
            const model = this._createModelForTool(gesture.tool, gesture.preview.anchors);
            this.store.add(model);
            this.selectedId = model.id;
            this._hoveredId = model.id;
          } catch (error) {
            if (this.onError) this.onError(error);
          }
        }
        this.activeTool = null;
        if (this.onToolChange) this.onToolChange(null);
        this._clearDraftPrimitive();
        this.refresh();
      } else if (gesture.type === 'anchor' || gesture.type === 'body') {
        if (!gesture.invalid
            && JSON.stringify(gesture.preview.anchors) !== JSON.stringify(gesture.original.anchors)) {
          this.store.update(gesture.original.id, gesture.preview);
        }
        this.refresh();
      }
      this._gesture = null;
      this._releasePointerCapture();
      this._setInteractionState(false, gesture.type);
      if (event.preventDefault) event.preventDefault();
    }

    _onPointerCancel(event) {
      this.cancelGesture();
      if (event && event.preventDefault) event.preventDefault();
    }

    _hitTest(x, y) {
      const primitives = Array.from(this._primitives.values()).reverse();
      for (const primitive of primitives) {
        const hit = primitive.hitTest(x, y);
        if (hit) return hit;
      }
      return null;
    }

    _onKeyDown(event) {
      const tagName = event.target && event.target.tagName
        ? String(event.target.tagName).toUpperCase()
        : '';
      if (tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT'
          || (event.target && event.target.isContentEditable)) return;
      const key = String(event.key || '').toLowerCase();
      if (key === 'escape') {
        this.cancelGesture();
        this.activeTool = null;
        if (this.onToolChange) this.onToolChange(null);
        this.select(null);
      } else if (key === 'delete' || key === 'backspace') {
        this.deleteSelected();
      } else if ((event.ctrlKey || event.metaKey) && key === 'z' && event.shiftKey) {
        this.redo();
      } else if ((event.ctrlKey || event.metaKey) && key === 'z') {
        this.undo();
      } else if ((event.ctrlKey || event.metaKey) && key === 'y') {
        this.redo();
      } else {
        return;
      }
      if (event.preventDefault) event.preventDefault();
    }
  }

  return {
    DEFAULT_FIBONACCI_LEVELS,
    DEFAULT_FIB_TREND_TIME_LEVELS,
    SNAP_DISTANCE_PX,
    DEFAULT_RISK_REWARD_RATIO,
    resetFibonacciLevels,
    resetFibTrendTimeLevels,
    defaultFibTrendTimeSettings,
    calculateFibonacciLevels,
    calculateRulerMetrics,
    calculateRiskReward,
    calculateRayEndpoint,
    axisLabelPrices,
    createDrawingModel,
    createTrendModel,
    createHorizontalModel,
    createRayModel,
    createRectangleModel,
    createTextModel,
    createFibonacciModel,
    createFibTrendTimeModel,
    createRulerModel,
    createRiskRewardModel,
    serializeDrawing,
    DrawingStore,
    DrawingPrimitive,
    normalizePointerEvent,
    DrawingController,
  };
}));
