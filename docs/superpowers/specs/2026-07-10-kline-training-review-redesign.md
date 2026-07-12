# KLine Playground Training and Review Redesign

## Goal
Repair report session identity so review summaries and full-chart replay work after a training session ends, then redesign the training, report, and history flows around a focused trading workspace and card-based review experience.

## Confirmed Visual Direction
- Preserve the existing light and dark theme switch instead of copying the reference palette exactly.
- Use a focused chart workspace with a persistent trading panel for the training page.
- Use compact metric cards and readable record cards for reports and history.
- Keep all current trading rules, orders, chart indicators, and user data intact.

## Data Contract
- Every report returned from automatic completion or the explicit end-training endpoint must contain the same `session_id` as the active training.
- The same report object is persisted as `report_data` and later returned from the history API.
- Review summary save and full-chart replay always use the report `session_id`.

## Page Design
### Training workspace
- Chart canvas remains the main area.
- Right panel is a persistent trade console with buy/sell direction, order type, quantities, risk prices, optional reason fields, account metrics, positions, and pending orders.
- Trade reasons remain optional. Filled reasons can be reviewed from trade history.

### Report
- Header presents key training metrics as cards: return, final assets, trade count, win rate, and period.
- Personal review summary is presented as an explicit card with save feedback.
- Trade details use a compact card/table hybrid and expose a reason action per trade.

### History
- Page uses an overview strip, filters, and review cards.
- Each record provides open review, chart replay, and delete actions.
- Empty, loading, and failure states are actionable and do not leave a blank workspace.

## Out of Scope
- No changes to market price rules, trading calculations, offline data downloading, or AI model integration.
- No database migration beyond using existing report/session fields.
