---
id: TASK-018
title: Add historical chart-window static controls
status: ready
priority: P0
owner: unassigned
depends_on:
  - TASK-016
write_scope:
  - frontend/index_enhanced.html
  - frontend/css/style_enhanced.css
  - tests/test_intraday_context_static_ui.py
read_scope:
  - frontend/js/main_enhanced.js
  - tests/test_intraday_frontend_static.py
  - docs/superpowers/specs/2026-07-14-historical-context-trading-day-blind-box-design.md
  - docs/superpowers/plans/2026-07-14-historical-context-blind-box.md
quality_profiles:
  - frontend
---

## Goal
Add the static HTML and CSS controls required for one-year historical chart-window loading and clarify that the training limit counts actual trading days.

## Acceptance Criteria
- [ ] The HTML contains exactly one `#load-earlier-year-btn`.
- [ ] The HTML contains exactly one `#load-later-year-btn`.
- [ ] The HTML contains exactly one `#chart-window-status` with an appropriate live-region attribute.
- [ ] The HTML contains exactly one `#training-day-limit-help`.
- [ ] The limit label contains `训练交易日限制（0=不限制）`.
- [ ] Old wording that describes the value as a K-line count is removed from the setup UI.
- [ ] The earlier button is available for active training.
- [ ] The later button is hidden by default so JavaScript can expose it only for completed read-only review.
- [ ] Loading, disabled, hidden, and compact toolbar states are styled without redesigning unrelated panels.
- [ ] Focused tests pass and the existing JavaScript remains syntactically valid.

## Required Markup Contract
Use these exact IDs and button text:

```html
<button id="load-earlier-year-btn" type="button">往前加载一年</button>
<button id="load-later-year-btn" type="button" class="hidden">往后加载一年</button>
<span id="chart-window-status" aria-live="polite"></span>
```

The controls may share one reusable chart toolbar. Do not add duplicate active/history copies with the same IDs.

## Constraints
Modify only the three write-scope files. Do not modify JavaScript, backend files, dependencies, existing tests, task files, or Git state. Do not commit.

## Required Verification

```powershell
python -m pytest tests/test_intraday_context_static_ui.py -q
node --check frontend/js/main_enhanced.js
git diff --check -- frontend/index_enhanced.html frontend/css/style_enhanced.css tests/test_intraday_context_static_ui.py
git diff --stat -- frontend/index_enhanced.html frontend/css/style_enhanced.css tests/test_intraday_context_static_ui.py
```
