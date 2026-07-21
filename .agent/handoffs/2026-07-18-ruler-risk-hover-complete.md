# Ruler and Risk Hover UX Complete

## Requested Changes
- Recreate the compact ruler shown in the supplied reference.
- Hide long/short risk labels unless the pointer is inside the risk area.
- Show the entry price on the middle risk line.

## Implementation
- frontend/js/drawing_tools.js: ruler card reduced from four rows to three rows and moved above the measured region when space permits.
- The ruler uses a centered vertical dashed guide, horizontal dashed guide, horizontal and vertical arrowheads, and visible endpoint handles.
- Positive ruler deltas and percentages omit redundant plus signs; negative values retain their minus sign.
- Risk overlays always render the red/green zones and boundary lines, while labels render only when the drawing model is hovered.
- Hover labels are now: stop price and percent, entry price and RR, target price and percent. Account and quantity details are omitted from the chart overlay.
- DrawingController tracks hovered drawing ids from pointermove and clears hover on pointerleave; draft risk drawings remain readable while dragging.

## Verification
- python -m pytest tests/test_drawing_tools_frontend.py -q: 31 passed.
- Frontend-focused regression set: 101 passed.
- python -m pytest -q: 600 passed and 37 subtests passed.
- JavaScript syntax, Python compile, and git diff check passed.

## Runtime and Safety
- Server: http://127.0.0.1:8000/, PID 22376, bound to 0.0.0.0.
- No commit was created.
- Existing unrelated uncommitted changes were preserved.
- .runtime/ and offline market data were not modified or staged.
