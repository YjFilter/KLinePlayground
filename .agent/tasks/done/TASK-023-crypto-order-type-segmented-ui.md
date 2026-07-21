---
id: TASK-023
title: Add segmented crypto order type control
status: done
priority: P1
owner: WorkBuddy
depends_on: []
write_scope:
  - frontend/index_enhanced.html
  - frontend/css/style_enhanced.css
  - tests/test_crypto_frontend_static.py
read_scope:
  - frontend/js/main_enhanced.js
  - backend/crypto/futures_orders.py
quality_profiles:
  - focused
---

## Goal
Replace the crypto order-type dropdown with one compact A-share-style segmented control: `市价 | 限价 | 突破`.

## Constraints
- Preserve every pre-existing uncommitted change in owned files.
- Keep the three equal-width buttons inside one rounded container, matching the supplied reference.
- Use `data-order-type=market|limit|breakout`; keep one hidden form value with id `crypto-order-type` for existing JavaScript compatibility.
- Show one shared `触发价` field for limit and breakout; hide it for market.
- Do not edit JavaScript, backend, `.runtime/`, offline data, or unrelated layouts.

## Acceptance Criteria
- [ ] The crypto console renders a single-row three-way segmented control without a select element.
- [ ] Active, hover, focus-visible, and pressed states are clear on the dark workspace.
- [ ] Existing A-share order control remains unchanged.
- [ ] Static tests verify all three order types, shared trigger-price UI, and unique ids.

## Required Commands
```powershell
python -m pytest tests/test_crypto_frontend_static.py -q
git diff --check -- frontend/index_enhanced.html frontend/css/style_enhanced.css tests/test_crypto_frontend_static.py
```

## Result Contract
Move this task to `.agent/tasks/review/` and write `.agent/tasks/review/TASK-023-result.md` using `.agent/templates/result.md`. Report only changed files, commands/results, risks, and unresolved items.
