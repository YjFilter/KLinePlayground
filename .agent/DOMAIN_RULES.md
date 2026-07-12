# Protected Domain Rules

Changes to the following rules require focused regression tests and Codex review.

## Trading Calendar and Replay
- The visible training window and current replay bar must remain deterministic.
- Training progress, preview bars, and maximum training bars must use consistent definitions.

## T+1 Sellability
- Shares bought on the current trading day cannot be sold until an eligible later trading day.
- Forced liquidation and pending exits must not silently bypass T+1 rules unless an approved rule explicitly says so.

## Price Limits
- Main-board instruments use the applicable 10 percent daily price limit.
- ChiNext and STAR Market instruments use the applicable 20 percent daily price limit.
- Limit-up and limit-down states can block otherwise triggered orders.

## Costs
- Commission rate and minimum commission must be applied consistently.
- Stamp tax applies on the correct side of the transaction.
- Account cash, cost basis, realized profit, and final report totals must reconcile.

## Pending Orders
- Trigger price, gap behavior, priority, active state, cancellation, and generated exit orders must remain deterministic.
- A blocked order remains active unless the documented order rule cancels it.

## Adjustment and Market Data
- No-adjustment, forward-adjustment, backward-adjustment, and dynamic adjustment must preserve documented chart and trade semantics.
- Changing adjustment must not corrupt replay position, markers, account state, or report identity.

## Reports and Identity
- A training report retains the active session identifier through API response and persistence.
- Trade counts, win rates, returns, final capital, reasons, and history summaries must be derived consistently.

## Required Evidence
A change to any rule above requires a focused test demonstrating the intended behavior, the full relevant backend test profile, and an explicit note in the task result.
