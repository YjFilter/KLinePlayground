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

  function normalizeFibonacciSettings(options) {
    const defaults = defaultFibonacciSettings();
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
    const modelOptions = normalizedType === 'fibonacci'
      ? normalizeFibonacciSettings(config.options)
      : clone(config.options || {});
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

  function drawLabel(context, text, x, y, color, ratioX, ratioY) {
    const paddingX = 4 * ratioX;
    const height = 18 * ratioY;
    const width = context.measureText(text).width + (paddingX * 2);
    context.fillStyle = color;
    context.fillRect(x, y - height, width, height);
    context.fillStyle = '#ffffff';
    context.fillText(text, x + paddingX, y - (4 * ratioY));
  }

  function applyLineStyle(context, lineStyle, ratio) {
    if (lineStyle === 'dashed') context.setLineDash([6 * ratio, 4 * ratio]);
    else if (lineStyle === 'dotted') context.setLineDash([2 * ratio, 3 * ratio]);
    else context.setLineDash([]);
  }

  function formatDuration(seconds) {
    const totalSeconds = Math.abs(seconds);
    if (totalSeconds < 60) return `${totalSeconds}s`;
    if (totalSeconds < 3600) return `${Math.round(totalSeconds / 60)}m`;
    if (totalSeconds < 86400) return `${Math.round(totalSeconds / 3600)}h`;
    return `${Math.round(totalSeconds / 86400)}d`;
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
        const strokeColor = model.options.color || '#5b8ff9';
        context.save();
        context.beginPath();
        context.rect(0, 0, width, height);
        context.clip();
        context.strokeStyle = strokeColor;
        context.fillStyle = model.options.fillColor || 'rgba(91, 143, 249, 0.16)';
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
          drawLine(context, {x: 0, y: first.y}, {x: width, y: first.y});
        } else if (model.type === 'ray') {
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
          context.fillRect(left, top, rectWidth, rectHeight);
          context.strokeRect(left, top, rectWidth, rectHeight);
        } else if (model.type === 'text') {
          context.fillStyle = strokeColor;
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
        } else if (model.type === 'ruler') {
          const left = Math.min(first.x, second.x);
          const top = Math.min(first.y, second.y);
          const rectWidth = Math.abs(second.x - first.x);
          const rectHeight = Math.abs(second.y - first.y);
          const metrics = primitive.rulerMetrics();
          const directionColor = metrics.direction === 'bull'
            ? 'rgba(38, 166, 154, 0.20)'
            : 'rgba(239, 83, 80, 0.20)';
          context.fillStyle = directionColor;
          context.strokeStyle = metrics.direction === 'bull' ? '#26a69a' : '#ef5350';
          context.fillRect(left, top, rectWidth, rectHeight);
          context.strokeRect(left, top, rectWidth, rectHeight);
          context.save();
          context.setLineDash([5 * ratioX, 4 * ratioX]);
          drawLine(context, {x: first.x, y: first.y}, {x: second.x, y: first.y});
          drawLine(context, {x: second.x, y: first.y}, {x: second.x, y: second.y});
          context.restore();
          drawLine(context, first, second);
          const angle = Math.atan2(second.y - first.y, second.x - first.x);
          const arrowSize = 8 * Math.max(ratioX, ratioY);
          context.beginPath();
          context.moveTo(second.x, second.y);
          context.lineTo(
            second.x - arrowSize * Math.cos(angle - Math.PI / 6),
            second.y - arrowSize * Math.sin(angle - Math.PI / 6)
          );
          context.moveTo(second.x, second.y);
          context.lineTo(
            second.x - arrowSize * Math.cos(angle + Math.PI / 6),
            second.y - arrowSize * Math.sin(angle + Math.PI / 6)
          );
          context.stroke();
          context.fillText(
            `${metrics.absolutePriceChange.toFixed(2)} (${metrics.percentChange.toFixed(2)}%) `
              + `${metrics.barCount} bars ${metrics.bullishCount} bull ${metrics.bearishCount} bear `
              + `${formatDuration(metrics.elapsedDuration)}`,
            left,
            top
          );
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
          drawLine(context, {x: entry.x, y: entry.y}, {x: right, y: entry.y});
          drawLine(context, {x: entry.x, y: stop.y}, {x: right, y: stop.y});
          drawLine(context, {x: entry.x, y: target.y}, {x: right, y: target.y});
          const side = model.type === 'risk-reward' ? model.side : model.type;
          const metrics = calculateRiskReward(
            side,
            model.anchors[0].price,
            model.anchors[1].price,
            model.anchors[2].price,
            model.options
          );
          const labelX = entry.x + (4 * ratioX);
          drawLabel(context, `入场 ${metrics.entry.toFixed(2)}`, labelX, entry.y, '#2962ff', ratioX, ratioY);
          drawLabel(
            context,
            `止损 ${metrics.stop.toFixed(2)} (${metrics.riskPercent.toFixed(2)}%)`,
            labelX,
            stop.y,
            '#ef5350',
            ratioX,
            ratioY
          );
          drawLabel(
            context,
            `止盈 ${metrics.target.toFixed(2)} (${metrics.rewardPercent.toFixed(2)}%)`,
            labelX,
            target.y,
            '#26a69a',
            ratioX,
            ratioY
          );
          const centerY = (stop.y + target.y) / 2;
          drawLabel(
            context,
            `盈亏比 ${metrics.rewardRiskRatio.toFixed(2)}`,
            labelX,
            centerY,
            '#7c4dff',
            ratioX,
            ratioY
          );
          if (Number.isFinite(metrics.accountSize)) {
            drawLabel(
              context, `账户 ${metrics.accountSize.toFixed(2)}`, labelX, centerY + (20 * ratioY),
              '#ff9800', ratioX, ratioY
            );
          }
          if (Number.isFinite(metrics.positionSize)) {
            drawLabel(
              context, `仓量 ${metrics.positionSize}`, labelX, centerY + (40 * ratioY),
              '#00897b', ratioX, ratioY
            );
          }
          if (Number.isFinite(metrics.accountRiskAmount)) {
            drawLabel(
              context, `风险 ${metrics.accountRiskAmount.toFixed(2)}`, labelX, centerY + (60 * ratioY),
              '#f4511e', ratioX, ratioY
            );
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

  class DrawingPrimitive {
    constructor(model) {
      this._model = serializeDrawing(model);
      this._bars = [];
      this._chart = null;
      this._series = null;
      this._requestUpdate = null;
      this._paneBounds = null;
      this._paneView = new DrawingPaneView(this);
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

    projectAnchors() {
      if (!this._chart || !this._series) return [];
      const timeScale = this._chart.timeScale();
      return this._model.anchors.map((anchor) => {
        let projectedTime = anchor.time;
        let x = timeScale.timeToCoordinate(projectedTime);
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
      this.accountSizeProvider = parameters.accountSizeProvider || null;
      this.accountRiskPercent = Number.isFinite(parameters.accountRiskPercent)
        ? parameters.accountRiskPercent
        : 1;
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
      this._draftAnchors = [];
      this._draftPrimitive = null;
      this._gesture = null;
      this._interactionType = null;
      this._capturedPointerId = null;
      this._pendingPointerMove = null;
      this._pointerMoveFrame = null;
      this._bars = clone(Array.isArray(parameters.bars) ? parameters.bars : []);
      this._primitives = new Map();
      this._boundPointerDown = (event) => this._onPointerDown(event);
      this._boundPointerMove = (event) => this._onPointerMove(event);
      this._boundPointerUp = (event) => this._onPointerUp(event);
      this._boundPointerCancel = (event) => this._onPointerCancel(event);
      this._boundKeyDown = (event) => this._onKeyDown(event);
      this.element.addEventListener('pointerdown', this._boundPointerDown);
      this.element.addEventListener('pointermove', this._boundPointerMove);
      this.element.addEventListener('pointerup', this._boundPointerUp);
      this.element.addEventListener('pointercancel', this._boundPointerCancel);
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
        const viewModel = {...model, selected: model.id === this.selectedId};
        let primitive = this._primitives.get(model.id);
        if (!primitive) {
          primitive = new DrawingPrimitive(viewModel);
          this._primitives.set(model.id, primitive);
          primitive.setBars(this._bars);
          this._attachPrimitive(primitive);
        } else {
          primitive.setModel(viewModel);
          primitive.setBars(this._bars);
        }
      }
    }

    setBars(bars) {
      this._bars = clone(Array.isArray(bars) ? bars : []);
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
      if (!model || model.type !== 'fibonacci') return null;
      return normalizeFibonacciSettings(model.options);
    }

    getSelectedFibonacciSettings() {
      return this.getFibonacciSettings();
    }

    updateFibonacciSettings(patch, id) {
      const drawingId = id || this.selectedId;
      const model = this.store.get(drawingId);
      if (!model || model.type !== 'fibonacci' || model.locked) return null;
      const options = normalizeFibonacciSettings({...model.options, ...(patch || {})});
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
      const insertionIndex = Number.isInteger(index)
        ? Math.max(0, Math.min(index, settings.levels.length))
        : settings.levels.length;
      settings.levels.splice(insertionIndex, 0, normalizeFibonacciLevel(level));
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
      return this.updateFibonacciSettings(defaultFibonacciSettings(), id);
    }

    undo() {
      const changed = this.store.undo();
      if (changed) {
        if (this.selectedId && !this.store.get(this.selectedId)) this.selectedId = null;
        this.refresh();
      }
      return changed;
    }

    redo() {
      const changed = this.store.redo();
      if (changed) this.refresh();
      return changed;
    }

    clearAll() {
      const changed = this.store.clear();
      if (changed) {
        this.selectedId = null;
        this.refresh();
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
      this.keyTarget.removeEventListener('keydown', this._boundKeyDown);
      for (const primitive of this._primitives.values()) {
        this._detachPrimitive(primitive);
      }
      this._primitives.clear();
      this.selectedId = null;
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
      return createDrawingModel(tool, anchors, config);
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
      let time = timeScale.coordinateToTime(point.x);
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
        this.select(null);
        this._gesture = null;
        return;
      }
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
          const originalX = this.chart.timeScale().timeToCoordinate(anchor.time);
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
      if (!this._gesture) return;
      const point = this._safePointerEvent(event);
      if (!point) return;
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
    SNAP_DISTANCE_PX,
    DEFAULT_RISK_REWARD_RATIO,
    resetFibonacciLevels,
    calculateFibonacciLevels,
    calculateRulerMetrics,
    calculateRiskReward,
    calculateRayEndpoint,
    createDrawingModel,
    createTrendModel,
    createHorizontalModel,
    createRayModel,
    createRectangleModel,
    createTextModel,
    createFibonacciModel,
    createRulerModel,
    createRiskRewardModel,
    serializeDrawing,
    DrawingStore,
    DrawingPrimitive,
    normalizePointerEvent,
    DrawingController,
  };
}));
