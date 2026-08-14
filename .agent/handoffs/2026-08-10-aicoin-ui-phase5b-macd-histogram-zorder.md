# Session Handoff

## Session Goal
修复 MACD 副图与 AiCoin 的两处关键差距（用户对照截图指出）：柱子实心/空心区分、DIF/DEA 线被柱子遮挡。纯前端，未动后端。

## Completed Tasks
- 柱子实心/空心（AiCoin 动能语义）：MACD 柱不再只看正负，改为按动能方向着色——
  - 正且增强（histogram ≥ 前一根）→ 实心绿 `palette.positive`
  - 正但减弱 → 半透明绿（空心观感）`hexColorWithAlpha(positive, 0.4)`
  - 负且增强（更负）→ 实心红 `palette.negative`
  - 负但收敛（向 0 回升）→ 半透明红（空心观感）
  新增 `hexColorWithAlpha(hex, alpha)` 把 `#rrggbb` 转 `rgba()`（支持 3/6 位 hex，非 hex 原样返回）。
- 线条层级修复：把 `histogramSeries` 的创建移到 `difSeries`/`deaSeries` 之前。Lightweight Charts 中后创建的系列画在上层，原来柱子最后创建导致盖住线；现在柱子先建在底层，白/金 DIF/DEA 线画在顶层，对齐 AiCoin"黄白线在顶层"。

## Active Tasks
- 无（等待用户确认修复效果）。

## Blocked Work
- 无。

## Git Status
- 分支 `master`，未创建提交。
- 本会话改动：`frontend/js/main_enhanced.js`。
- 既有未提交改动保持原样；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未触碰。

## Verification
| Command | Exit Code | Result |
| --- | ---: | --- |
| `node --check frontend/js/main_enhanced.js` | 0 | JS_OK |
| `.venv\Scripts\python.exe -m pytest -q` | 0 | 717 passed, 71 subtests passed in 24.98s |
| `git diff --check` | 0 | DIFF_OK |
| 浏览器 DOM 校验 | 0 | `hexColorWithAlpha('#0ecb81',0.4)→rgba(14,203,129,0.4)`、`#f6465d→rgba(246,70,93,0.4)`、3 位 hex 与非 hex 兜底正确；动能映射 `solidUp/hollowUp/solidDown/hollowDown` 四象限全对；控制台无报错；localStorage 未污染 |

## Decisions
- Lightweight Charts 的 HistogramSeries 无法画真"描边空心"，用半透明填充（alpha 0.4）模拟空心观感——这是该类库的标准做法，暗色背景下与 AiCoin 观感接近。
- 动能判定以"当前 histogram ≥ 前一根"为增强；首根与 0 比较。
- 层级靠系列创建顺序实现（无需 z-index 之类的额外 API）。

## Risks
- 半透明空心与 AiCoin 的"真描边空心"在细节上仍有差异，属库能力限制；若用户强烈要求真描边，需要自定义渲染（成本高）。
- 浏览器截图仍超时未能自动出图，实际观感需肉眼确认。

## Next Action
开一局币圈训练硬刷新 `http://127.0.0.1:8000/`，切到 MACD 副图确认：白 DIF/金 DEA 线压在柱子上层、柱子有实心/半透明之分（增强实心、减弱空心）、零轴虚线仍在。若空心观感偏淡可微调 alpha（当前 0.4）。
