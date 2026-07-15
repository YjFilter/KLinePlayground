# Drawing Tools, Crypto Replay, and Perpetual Futures Design

**Date:** 2026-07-15
**Status:** Approved for implementation
**Project:** KLinePlayground

## 1. Objective

Add a TradingView-style drawing layer to every active and completed-review chart, then add a separately isolated crypto-perpetual market domain with 5-minute historical replay and simplified USDT-margined long/short simulation.

The implementation must preserve the existing A-share `legacy_daily` and `intraday_30m` behavior, keep `.runtime/` untouched and untracked, and maintain the no-future-data invariant in every replay period.

## 2. Delivery Boundaries

The work is delivered in three independently verifiable stages:

1. browser-only drawing tools on the existing chart stack;
2. crypto market data, cache, aggregation, chart windows, and replay;
3. crypto perpetual orders, margin, funding, liquidation, reports, and integrated UI.

Drawing objects are intentionally session-only. They are not written to SQLite, `localStorage`, reports, or server state. Crypto sessions and trades are persisted independently from A-share positions.

## 3. Drawing System

### 3.1 Architecture

Use Lightweight Charts v5.0.8 Series Primitive APIs. A dedicated drawing controller owns tool state, pointer and keyboard input, hit testing, selection, undo/redo, and primitive lifecycle. Drawing anchors are stored as market timestamp and price, never as screen coordinates.

The drawing controller attaches to the main candlestick series and remains independent from volume and indicator panels. It reprojects drawings after resize, pan, zoom, chart-window pagination, active snapshot refresh, and period switching.

### 3.2 Toolbar and editing

A narrow vertical toolbar sits on the left edge of the main K-line panel. It is available in active training and completed-history review for both A-share and crypto sessions.

Tools: select, trend line, horizontal line, ray, rectangle range, text annotation, Fibonacci retracement and extension, ruler, long-position risk/reward, and short-position risk/reward.

Editing supports selecting a drawing, dragging the body, dragging anchors, locking, hiding, deleting, undoing, redoing, and clearing all drawings. `Escape` cancels the current creation gesture and `Delete` removes the selected unlocked drawing. Locked drawings remain visible but ignore pointer edits.

Drawings remain in memory while switching display periods and chart windows. If an anchor is outside the loaded window, the visible portion is clipped naturally. Refreshing or leaving the page clears all drawings.

### 3.3 Fibonacci design

Fibonacci uses two anchors with circular handles and a dashed blue direction guide. Level lines extend rightward from the first anchor through the chart.

Default levels are `0`, `23.6`, `38.2`, `50`, `61.8`, `78.6`, `100`, `138.2`, `161.8`, and `200` percent. Each label displays `percentage (price)` at the left edge. Default colors follow the approved visual reference: purple for upper retracement levels, blue for central retracement levels, pink for lower retracement levels, green for the 138.2/161.8 extensions, and orange for 200.

The selected Fibonacci drawing exposes a settings panel for enabling, disabling, adding, removing, and reordering levels; changing line color, width, style, and label position; reversing the calculation direction; and restoring the approved defaults.

### 3.4 Ruler design

Ruler uses two draggable circular anchors and renders a translucent rectangular range, horizontal and vertical dashed guides, and a direction arrow. Positive movement is teal/green and negative movement is red.

The information card displays absolute price change, percentage change, displayed-period bar count, bullish and bearish candle counts, and elapsed calendar duration. Time and price anchors remain stable across period switches. Bar and bullish/bearish counts are recalculated from the currently rendered period.

### 3.5 Long and short risk/reward drawings

Creation uses three clicks in this order: entry, stop, target. The drawing renders separate risk and reward rectangles, circular anchors, price labels, percentage distances, risk/reward ratio, and optional account-risk amount.

These drawings never submit, prefill, or mutate an order. They remain analysis-only even inside a crypto-futures session.

## 4. Crypto Market Data and Replay

### 4.1 Domain isolation

Introduce `market_type = crypto_perpetual` and `data_mode = crypto_5m`. Crypto uses dedicated source, cache, validator, universe, clock, session, and simulator modules. It may reuse normalized bar DTOs, aggregation helpers, chart-window serialization, and report presentation contracts only where market semantics are genuinely shared.

A-share trading calendars, lunch breaks, price limits, lot sizes, stamp tax, and T+1 sellability must not be called from crypto code.

### 4.2 Sources and normalized data

Binance USD-M Futures is the primary source and Bybit Linear Perpetual is the fallback. Both adapters expose the same normalized contracts for trade-price 5-minute OHLCV, mark-price 5-minute OHLC, historical funding, active USDT perpetual instruments, listing time, price and quantity rules, status, and 24-hour quote turnover.

Source fallback occurs per request. Data from different exchanges is never silently merged into one candle series. A session records its selected source and continues using that source. Fallback is allowed only before session creation or when the requested cached range was already produced by the same source.

### 4.3 Dynamic universe

The default blind-box universe contains active USDT perpetual contracts that have at least 180 days of history. It ranks candidates by 24-hour quote turnover and keeps the top 50.

Specified mode provides server-backed symbol search. It may select another active, sufficiently old USDT perpetual contract outside the default top 50. Delisted, settling, newly listed, or insufficient-history contracts are rejected with an actionable error.

### 4.4 Cache

Cache normalized crypto data beneath `data/crypto/`, segmented by source, symbol, data kind, and UTC month. Use compressed CSV files and atomic temporary-file replacement so no new binary dependency is required.

The cache is populated on demand for the selected symbol and requested range. The application never predownloads the complete top-50 universe. Coverage metadata records source, symbol, kind, interval, first timestamp, last timestamp, validation result, and synchronization time.

Network failure may use cache only when every required trade-price and mark-price timestamp is covered. Partial cache must not create a shortened session silently.

### 4.5 Periods and time semantics

The canonical replay timeline is ordered 5-minute UTC timestamps. Supported display periods are `5m`, `15m`, `30m`, `1h`, `4h`, `daily`, and `weekly`.

All display periods aggregate only revealed 5-minute bars. Daily and weekly boundaries follow exchange UTC conventions. The browser displays timestamps in Asia/Shanghai and labels crypto time as `UTC+8`.

Crypto replay is continuous 24x7. `max_training_days` means UTC calendar days for crypto and distinct data-bearing trading dates for A-share. UI helper text changes with the selected market.

## 5. Crypto Futures Simulation

### 5.1 Account and position model

Each crypto training starts with an independent USDT balance. It uses isolated margin, one-way net position mode, one symbol per session, leverage from 1x through 20x, and a default of 5x.

Order sizing is entered as isolated-margin USDT. Contract quantity is derived from margin, leverage, execution price, quantity step, and minimum-notional rules. The UI provides 25%, 50%, 75%, and 100% available-margin shortcuts.

An opposite-side order first reduces or closes the current position. Any remaining quantity opens a position in the opposite direction. Leverage can change only while flat and without active orders.

### 5.2 Orders and deterministic execution

Supported orders are market and limit orders for open long, open short, and close. Close operations are reduce-only.

Market orders execute at the currently revealed trade-price close. Limit orders become eligible on subsequent canonical 5-minute bars and fill at the limit price when the bar range crosses the limit. Every order and fill records the exact canonical timestamp.

For each newly revealed 5-minute timestamp, processing order is:

1. update trade and mark prices;
2. settle unprocessed funding events at or before the timestamp;
3. test liquidation using the mark-price bar range;
4. process active reduce-only orders;
5. process remaining active limit orders;
6. commit the replay clock.

If liquidation and an ordinary fill are both possible in one bar, liquidation has priority. This conservative rule avoids inventing an unknowable intrabar path.

### 5.3 Fees, funding, and liquidation

Default training parameters are maker fee `0.02%`, taker fee `0.05%`, maintenance margin rate `0.50%`, and liquidation fee `0.50%`. They are editable crypto-training settings and are explicitly labeled as simulation parameters rather than exact exchange account terms.

Historical funding uses the selected source's published timestamp and rate. Positive funding transfers from longs to shorts; negative funding transfers from shorts to longs. Funding uses position notional at the funding timestamp's mark price.

Liquidation evaluates isolated equity against maintenance margin plus the liquidation-fee reserve using mark price. Long positions test the mark-bar low and short positions test the mark-bar high. When crossed, the simulator closes at the solved liquidation price, applies the liquidation fee, records a liquidation event, cancels all orders, and never allows account equity below zero.

### 5.4 Reports

Crypto reports include initial and final equity, realized and unrealized P&L, total return, maximum drawdown, maker/taker fees, funding paid and received, liquidation fees, liquidation count, order count, fill count, win rate, leverage, source, symbol, and display period.

Trade markers use `L`, `S`, and `X` semantics for open long, open short, and close/liquidation while retaining `B` and `S` for A-share sessions.

## 6. UI Integration

The new-training dialog adds a top-level `A股 / 币圈` market selector above the existing specified/blind-box tabs.

For crypto, specified mode uses asynchronous symbol search and a date-time selector; blind-box mode uses the dynamic top-50 universe and a date range; period options become the seven crypto periods; initial capital is labeled USDT; data source shows Binance with automatic Bybit fallback; and training length helper explains UTC calendar days.

The active crypto trading panel replaces A-share quantity, T+1, price-limit, and stamp-tax controls with direction, leverage, isolated margin, order type, limit price, position summary, mark price, liquidation price, margin ratio, funding, and pending orders.

The same chart, replay controls, panel resizing, local indicators, historical chart windows, and report navigation remain shared. Market-specific DOM sections are toggled explicitly rather than inferred from symbol text.

## 7. API and Persistence Contracts

### 7.1 Public API additions

```http
GET /api/crypto/instruments?query=&limit=
GET /api/crypto/sources/status
```

`POST /api/training/start` accepts crypto requests with `market_type`, `data_mode`, `mode`, optional `symbol`, start or random date range, `period`, `max_training_days`, `initial_capital`, and `leverage`.

The existing training `data`, `next`, `period`, `chart-window`, `account`, `orders`, cancel-order, reset, end, and history-chart routes branch by the stored market type and return the same top-level envelope where possible.

Crypto trade requests use the existing training trade route with this market-specific body:

```json
{
  action: open_long|open_short|close,
  order_type: market|limit,
  margin: 1000,
  leverage: 5,
  limit_price: 64000
}
```

Responses include normalized account, position, active orders, fill, funding events, liquidation events, trade markers, `market_type`, and `data_mode`.

### 7.2 Additive persistence

Add nullable market metadata to saved training sessions: `market_type`, `symbol`, `quote_currency`, `base_interval`, `timezone`, `source`, and `simulator_type`.

Create new idempotent crypto-specific tables for futures fills, orders, funding events, liquidation events, and equity snapshots. Do not change A-share integer quantity or position-lot tables. Existing sessions remain readable with `market_type = a_share` defaults.

Rollback consists of disabling crypto routes and UI sections; additive columns and tables may remain without affecting older application versions.

## 8. Verification and Acceptance

### 8.1 Drawing tests

- tool registry, toolbar structure, keyboard commands, selection, lock, hide, delete, undo, redo, and clear;
- timestamp/price anchoring through resize, pan, window merge, and period switching;
- exact approved Fibonacci defaults, labels, reverse mode, custom settings, and reset;
- ruler price delta, percentage, bar count, bullish/bearish counts, elapsed time, and positive/negative styling;
- long/short three-click creation and analysis-only behavior;
- browser pointer and touch acceptance with zero console errors.

### 8.2 Crypto data tests

- Binance and Bybit response normalization using fixtures only;
- primary/fallback selection without cross-source candle merging;
- monthly cache merge, deduplication, coverage, corruption handling, and atomic save;
- dynamic top-50 filtering and bounded blind-box selection;
- 5m through weekly aggregation with UTC boundaries and no future leakage;
- 24x7 replay across midnight, weekend, month, and year boundaries;
- active chart-window future caps and completed-history rehydration after restart.

### 8.3 Futures tests

- margin sizing, precision, minimum notional, long/short P&L, reversal, and leverage restrictions;
- market and limit fills with exact timestamps and conservative event priority;
- maker/taker fees, positive and negative funding, funding while flat, and repeated-event protection;
- long and short liquidation using mark-price extremes, order cancellation, fee application, and nonnegative equity;
- additive schema migration and legacy A-share compatibility;
- large-period advance equivalence to repeated 5-minute advances.

### 8.4 Final acceptance

- full existing suite remains green before new tests are counted;
- BTCUSDT and ETHUSDT specified sessions start from cache or network;
- a blind-box session selects an eligible top-50 contract;
- all seven periods preserve replay time and reveal no future OHLCV;
- long, short, limit order, funding, and forced-liquidation browser scenarios pass;
- approved Fibonacci, ruler, and risk/reward visuals match the references at desktop size;
- completed crypto history reloads after a Flask restart;
- `.runtime/` is absent from every staged diff and commit.

## 9. Implementation Ownership

Codex owns architecture, implementation integration, database migrations, public API contracts, trading invariants, browser acceptance, final review, and release state. Sub-agents may be used only for isolated modules or independent verification with disjoint write scopes. Codex remains responsible for every merged change and final acceptance.
