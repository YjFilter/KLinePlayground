/**
 * KLinePlayground - 主图持仓均价线、止盈止损线、挂单线与强平爆仓线可视化及拖拽改单模块
 */

function clearChartTradePriceLines() {
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
            if (!item?.orderId || !item?.price) continue;
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
                let title = '';
                let typeClass = 'limit';
                if (item.type === 'tp') {
                    title = `止盈 (TP): ${priceFormatted}`;
                    typeClass = 'tp';
                } else if (item.type === 'sl') {
                    title = `止损 (SL): ${priceFormatted}`;
                    typeClass = 'sl';
                } else {
                    title = `修改挂单: ${priceFormatted}`;
                    typeClass = 'limit';
                }

                try {
                    item.line.applyOptions({
                        price: currentDraggedTradeLine.tempPrice,
                        title: title,
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
        if (hovered) {
            e.preventDefault();
            e.stopPropagation();
            currentDraggedTradeLine = {
                item: hovered,
                originalPrice: hovered.price,
                tempPrice: hovered.price,
            };
            chartEl.setPointerCapture?.(e.pointerId);
        }
    });

    async function handleDragEnd(e) {
        if (!currentDraggedTradeLine) return;
        const { item, originalPrice, tempPrice } = currentDraggedTradeLine;
        currentDraggedTradeLine = null;
        chartEl.releasePointerCapture?.(e.pointerId);

        const tooltip = getChartDragTooltip();
        tooltip.style.display = 'none';
        chartEl.style.cursor = 'crosshair';

        if (!tempPrice || Math.abs(tempPrice - originalPrice) < 0.01) {
            updateChartTradePriceLines();
            return;
        }

        try {
            setCryptoOrderStatus(`正在将挂单价格更新为 ${formatCryptoValue(tempPrice)}...`, 'loading');
            const response = await fetch(`${API_BASE}/training/${currentTraining.id}/orders/${encodeURIComponent(item.orderId)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ price: tempPrice }),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || '更新挂单价格失败');
            }
            setCryptoOrderStatus(`已更新挂单价格至 ${formatCryptoValue(tempPrice)}`, 'success');
            if (data.account || data.position) renderCryptoAccount(data);
            else await updateAccountInfo();
        } catch (err) {
            console.error('拖动改单失败:', err);
            setCryptoOrderStatus(err.message || '拖动改单失败', 'error');
            updateChartTradePriceLines();
        }
    }

    chartEl.addEventListener('pointerup', handleDragEnd);
    chartEl.addEventListener('pointercancel', handleDragEnd);
}

function updateChartTradePriceLines() {
    clearChartTradePriceLines();
    if (typeof candlestickSeries === 'undefined' || !candlestickSeries || typeof isCryptoMode !== 'function' || !isCryptoMode() || typeof currentTraining === 'undefined' || !currentTraining?.id) return;
    initChartTradeLineDragging();

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
        const unrealized = Number(position.unrealized_pnl || 0);
        const margin = Number(position.isolated_margin || 0);
        const pnlPercent = margin > 0 ? (unrealized / margin) * 100 : 0;
        const pnlFormatted = (unrealized >= 0 ? '+' : '') + formatCryptoValue(unrealized, 2) + ' USDT';
        const pctFormatted = (pnlPercent >= 0 ? '+' : '') + pnlPercent.toFixed(2) + '%';
        const title = (isLong ? '多 ' : '空 ') + formatCryptoValue(quantity) + ' @ ' + formatCryptoValue(entryPrice) + ' [' + pnlFormatted + ', ' + pctFormatted + ']';
        const lineColor = isLong ? '#2196f3' : '#f6465d';

        try {
            const posLine = candlestickSeries.createPriceLine({
                price: entryPrice,
                color: lineColor,
                lineWidth: 2,
                lineStyle: lineStyleSolid,
                axisLabelVisible: true,
                title: title,
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
        const isTp = isProtective && order.protection_type === 'tp';
        const isSl = isProtective && order.protection_type === 'sl';
        const price = Number(order.limit_price ?? order.trigger_price ?? 0);
        if (!Number.isFinite(price) || price <= 0) return;

        let lineColor = '#848e9c';
        let lineStyle = lineStyleDashed;
        let title = '';

        if (isTp) {
            lineColor = '#0ecb81';
            title = '止盈 (TP): ' + formatCryptoValue(price) + ' [可拖动]';
        } else if (isSl) {
            lineColor = '#f6465d';
            title = '止损 (SL): ' + formatCryptoValue(price) + ' [可拖动]';
        } else {
            const actionText = actionMap[order.action] || '挂单';
            if (order.order_type === 'breakout') {
                lineColor = '#f0b90b';
                title = '突破' + actionText + ': ' + formatCryptoValue(price) + ' (' + formatCryptoValue(order.quantity || 0) + ') [可拖动]';
            } else {
                lineColor = '#2962ff';
                title = '限价' + actionText + ': ' + formatCryptoValue(price) + ' (' + formatCryptoValue(order.quantity || 0) + ') [可拖动]';
            }
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
    const protective = getCryptoProtectivePrices(pendingOrders);
    const tpPrice = Number(protective.tp || position.tp_price || 0);
    const slPrice = Number(protective.sl || position.sl_price || 0);
    if (tpPrice > 0 && !drawnPrices.has(tpPrice)) {
        try {
            const tpLine = candlestickSeries.createPriceLine({
                price: tpPrice,
                color: '#0ecb81',
                lineWidth: 1,
                lineStyle: lineStyleDashed,
                axisLabelVisible: true,
                title: '止盈 (TP): ' + formatCryptoValue(tpPrice),
            });
            activeChartTradePriceLines.push({
                line: tpLine,
                type: 'tp',
                price: tpPrice,
                entryPrice: entryPrice,
            });
        } catch (e) {}
    }
    if (slPrice > 0 && !drawnPrices.has(slPrice)) {
        try {
            const slLine = candlestickSeries.createPriceLine({
                price: slPrice,
                color: '#f6465d',
                lineWidth: 1,
                lineStyle: lineStyleDashed,
                axisLabelVisible: true,
                title: '止损 (SL): ' + formatCryptoValue(slPrice),
            });
            activeChartTradePriceLines.push({
                line: slLine,
                type: 'sl',
                price: slPrice,
                entryPrice: entryPrice,
            });
        } catch (e) {}
    }

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
}
