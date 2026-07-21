# Future Whitespace Drawing Complete

## Reported Symptom
Drawing tools could not start or end inside the blank chart area to the right of the last revealed candle. Existing future anchors also collapsed back to the nearest revealed candle.

## Root Cause
Lightweight Charts returns null from coordinateToTime() and timeToCoordinate() for whitespace beyond loaded data, while coordinateToLogical() and logicalToCoordinate() remain available. DrawingController treated the null time as an invalid anchor, and DrawingPrimitive fell back to the nearest candle. Body dragging also used timeToCoordinate() directly.

## Changes
- frontend/js/drawing_tools.js: adds cached median bar-interval context and shared logical-coordinate/timestamp projection helpers.
- Creation, live preview, anchor dragging, body dragging, hit testing, and rendering now share the future projection path.
- Existing OHLC/time snapping and Alt bypass behavior are preserved.
- tests/test_drawing_tools_frontend.py: adds future-whitespace creation/projection and anchor/body dragging regression coverage.

## Verification
- node --check frontend/js/drawing_tools.js: passed.
- pytest tests/test_drawing_tools_frontend.py -q: 30 passed.
- pytest tests/test_crypto_workspace_interactions.py tests/test_chart_workspace_frontend.py tests/test_crypto_frontend_static.py -q: 64 passed.
- python -m pytest -q: 599 passed and 37 subtests passed.
- git diff --check for the touched drawing files: passed with only existing line-ending warnings.

## Runtime and Safety
- Server: http://127.0.0.1:8000/, PID 25164, bound to 0.0.0.0.
- No commit was created.
- Existing unrelated uncommitted changes were preserved.
- .runtime/ and offline market data were not modified or staged.
