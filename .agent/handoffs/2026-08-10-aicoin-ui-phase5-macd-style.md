# Session Handoff

## Session Goal
AiCoin 风格 MACD 副图样式对齐：按用户提供的 AiCoin MACD 截图，优化 DIF/DEA 线色、零轴虚线、线宽。纯前端，未动后端。

## Completed Tasks
- MACD 线色 AiCoin 化：DIF 改为"自动色"——跟随主题文字色（加密暗色下为白 `#eaecef`，浅色为深 `#1e2329`）；DEA 为金色（暗 `#f0b90b` / 浅 `#b98700`）。默认值 `DEFAULT_INDICATOR_SETTINGS.macd.difColor/deaColor` 置 `null` 表示"自动"。
- 新增 `getAutoMacdColors()`/`resolveIndicatorColor()`/`macdColorsAreAuto()`：用户自定义颜色优先，未自定义则按主题解析 AiCoin 色。
- 零轴虚线：`attachMacdZeroLine()` 用 `createPriceLine` 在 MACD 副图 `price:0` 处画灰色虚线（加密 `rgba(132,142,156,0.45)` / 股票 `rgba(93,107,130,0.4)`），AiCoin 同款。
- 线宽加粗：`createIndicatorLineSeries` 增加 `lineWidth` 参数，MACD DIF/DEA 用 `lineWidth 2`（其余指标保持 1）。
- 主题联动：`applyChartTheme` 末尾当 MACD 为自动色且已有 K 线数据时自动重绘，切换明暗主题 DIF/DEA 颜色随之更新。
- 设置表单：MACD 颜色选择器展示解析后的实际颜色；若用户未改动（仍等于自动色），保存时回写 `null` 保持"跟随主题"。

## Active Tasks
- 无（等待用户确认 MACD 样式效果）。

## Blocked Work
- 无。

## Git Status
- 分支 `master`，未创建提交。
- 本会话改动：`frontend/js/main_enhanced.js`（唯一改动文件）。
- 既有未提交改动保持原样；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未触碰。

## Verification
| Command | Exit Code | Result |
| --- | ---: | --- |
| `node --check frontend/js/main_enhanced.js` | 0 | JS_OK |
| `.venv\Scripts\python.exe -m pytest -q` | 0 | 717 passed, 71 subtests passed in 29.63s |
| `git diff --check` | 0 | DIFF_OK |
| 浏览器 DOM 校验 | 0 | 默认 `difColor/deaColor=null`、`macdColorsAreAuto()=true`；加密暗色解析 DIF `#eaecef`、DEA `#f0b90b`，浅色 DIF `#1e2329`、DEA `#b98700`；设置表单展示解析色正确；控制台无报错；localStorage 未被污染（`null`） |

## Decisions
- MACD 线色用"自动色(null)+主题解析"而非写死白色，保证浅色主题下 DIF 不为白（白底白线不可见），同时保留 AiCoin 暗色观感。
- 零轴线挂在 DIF 系列上（`createPriceLine`），随 `clearTechnicalIndicatorSeries` 移除系列时一并清除，切指标无残留。
- 用户自定义颜色后优先于自动色；"恢复默认"回到 `null` 自动态。

## Risks
- 零轴 `createPriceLine` 若 Lightweight Charts 版本行为差异已用 try/catch 兜底，不影响主渲染。
- 浏览器截图仍超时未能自动出图，MACD 实际观感（白线/金线/零轴虚线）需肉眼确认。

## Next Action
开一局币圈训练硬刷新 `http://127.0.0.1:8000/`，切到 MACD 副图，确认 DIF 白线、DEA 金线、y=0 灰色虚线零轴、柱状红绿与 AiCoin 一致；切换明暗主题确认线色自适应。后续可做：KDJ/RSI/BOLL 线色 AiCoin 化、设置弹窗"说明"标签页、交易台下单表单细节。
