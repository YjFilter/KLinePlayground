# Session Handoff

## Session Goal
修复币圈图表时间显示比 AICoin 慢 8 小时的问题：同一根 ETH K线（低点 2440.22），AICoin 显示 2026-09-08 21:40，本项目显示 13:40。

## Root Cause
币圈数据源时间为 UTC 原文；`formatChartCrosshairTime` 显式取 `getUTC*` 分量、主图未配置 `tickMarkFormatter`，Lightweight Charts 默认按 UTC 渲染时间轴——显示层整条链路停留在 UTC。数据本身正确，纯显示层问题。

## Changes（方案 A：显示层集中换区）
1. `frontend/js/main_enhanced.js`
   - 新增 `chartTimeDisplayOffsetSeconds()`：isAshareLiveMode→0；isCryptoMode→+28800s；其余 0。注意该函数声明位于 `formatChartCrosshairTime` **之后**——`tests/test_chart_workspace_frontend.py` 的 node eval 片段从 `function formatChartCrosshairTime` 截取到 `// 图表管理`，helper 必须落在片段内（函数声明提升，调用可用）。
   - `formatChartCrosshairTime` Date/数字分支统一加偏移。
   - 新增 `formatChartTickMarkTime` 并接入主图 `timeScale.tickMarkFormatter`（零点整刻度 MM-DD，日内 HH:mm）。副图 timeScale 均 `visible:false`，无需处理。
2. `frontend/js/modules/trading_hours.js`：`computeTradingHourSegments` 默认 `tzOffsetMinutes` 0→480。09-07 改 0 是迁就"X 轴显示 UTC"的错误显示；显示层修正后恢复 480 才是真正的北京时间对齐。显式传参可覆盖。
3. 测试同步：
   - `tests/js/trading_hours.test.js` 期望按 +480 重算 + 新增显式 0 覆盖用例；
   - `tests/test_chart_workspace_frontend.py` node eval 测试补 `isAshareLiveMode` 桩、期望改 UTC+8、新增 A股原文反向断言。

## Invariants（未动）
数据层时间戳、订单、资金费率、周期快照缓存键全部保持 UTC 单一事实源；A股 Intraday/实时看盘显示行为不变（原文即北京时间）；极值标签仅价格不受影响。

## Verification
| Command | Result |
| --- | --- |
| `node --check frontend/js/main_enhanced.js` / `trading_hours.js` | Pass |
| `node --test tests/js/*.test.js` | 40 passed |
| `npx eslint@8.57.0 frontend/js/modules/ tests/js/` | 0 告警 |
| `.venv\Scripts\python.exe -m pytest -q` | **800 passed, 89 subtests passed** |

## Legacy Whitespace（遗留，非本次引入，按禁令未触碰）
`git diff --check`：`main_enhanced.js:10025` 行尾空白、`style_enhanced.css:6300` EOF 空行——均来自 2026-09-08 ashare 会话未提交改动，待用户指示。

## Next Action
等待用户浏览器验收：
1. 同一段币圈行情与 AICoin 并排对照——十字光标与时间轴应显示北京时间（如 21:40）；
2. 做单时段色带与北京时间 08:00–24:00 对齐；
3. A股 30m 回放 / A股实时看盘时间显示确认无变化。

未执行 git 提交与推送。
