# Session Handoff

## Session Goal
对标 AICoin，在 **A股实时看盘** 上新增「价格预警」：在图上落一条价位线，价格穿越该价位时弹出提醒。
用户通过四选一确认了范围（见下），已按确认范围实现并完成浏览器实测。

## 已确认的需求边界（用户选择）
| 维度 | 结论 |
| --- | --- |
| 触发条件 | 只做**价格穿越**（P1）；涨跌幅 / 成交量 / 指标预警留作后续分期 |
| 提醒方式 | **应用内弹窗 + 提示音** 与 **浏览器系统通知**（两者都要） |
| 添加方式 | 独立「预警」按钮 + 右侧可拖标签（对标截图） |
| 生效范围 | **仅 A股实时看盘**；按标的持久化，刷新/重进保留 |

## 实现

### 新增纯逻辑模块 `frontend/js/modules/price_alerts.js`
UMD（`root.KLinePriceAlertsModule` / `module.exports`），保持纯净以便 `node --test`：
`normalizeAlertPrice`（按 A股 0.01 元归一）、`normalizeAlertDirection`、`buildAlertId`、
`deriveAlertDirection`（高于现价=涨至，否则=跌至；相等归跌至避免创建瞬间误报）、
`normalizeAlert` / `normalizeAlertList`（补 id/时间戳、去重、按标的过滤）、
**`evaluateAlertCrossing`**、`findTriggeredAlerts`、`formatAlertLabel/Price/TriggeredAt`、
`alertStorageKey`、`selectPersistableAlerts`。

### 核心判定：必须用"穿越"
```
涨至：prev < target && now >= target
跌至：prev > target && now <= target
```
用**上一价**做严格比较，既避免价格停在阈值上反复触发，也保证 A股 3 秒轮询之间的**跳空不漏报**
（对比"当前价 ≤ 阈值"的写法会漏）。单测专门覆盖了跳空、恰好等于阈值、已触发/已禁用/无效价。

### 前端接线（`frontend/js/main_enhanced.js`）
- 状态：`ashareAlerts` / `ashareAlertPriceLines`(Map) / `ashareAlertChipEls`(Map) /
  `ashareAlertLastPrice`（上一轮快照价，穿越基准） / `ashareAlertAdding` / 音频上下文。
- 渲染：`priceLine`（橙色虚线，`axisLabelVisible:false`）+ 贴价格轴左侧的 DOM 标签
  `.alert-chip`（文字 + ✕ + 拖动柄）。定位复用已有「DOM 标签贴图表坐标」模式
  （`priceToCoordinate` + `priceScale('right').width()`），在**时间轴范围变化 / resize /
  每次轮询 / 十字光标移动**四处用 rAF 调度重定位（纵向缩放不改时间轴范围，故补了 crosshair 订阅）。
- 交互：`Alt+A` 或工具栏按钮进入落线模式 → 图区点击按 `coordinateToPrice` 落线；
  Esc 取消；拖动柄上下拖动改价（松手按现价重推方向）；✕ 删除；创建后弹「添加成功」Toast。
  标签上的指针事件全部 `stopPropagation`，不会漏回图表触发落线/画线。
- 触发：在 `startAshareLivePolling` 的价格更新处判定——**必须在覆盖基准价之前**执行
  （`checkAshareAlerts(ashareAlertLastPrice, snap.price)` 紧接 `ashareAlertLastPrice = snap.price`）。
  命中后置 `triggeredAt` + `enabled=false`（触发即失效，不重复打扰），并三通道提醒：
  弹窗卡片（12s 自动关）+ WebAudio 双音提示 + `Notification` 系统通知。
- 生命周期：`launchAshareLiveWatch` 显示按钮、绑定落线、按标的装载预警并重置基准价；
  `exitAshareLiveWatch` 隐藏按钮并清理图上元素；`switchAshareLiveStock` 重新装载该标的预警。
- 持久化：`kline-ashare-live-alerts-v1::<symbol>`，**只存"仍生效且未触发"**的项
  （已触发的仅作本次会话留痕，刷新自然清掉，避免堆积）；空集合时删除键。

### 样式 / 结构
- `index_enhanced.html`：`#drawing-toolbar` 内新增 `#alert-add-btn`（默认 `hidden`，仅看盘模式显示，
  铃铛图标，title 标 Alt+A）；脚本区在 `ashare_trading.js` 之后引入 `modules/price_alerts.js`。
- `style_enhanced.css`：`.alert-chip`（含 `is-triggered` 置灰态、✕、拖动柄）、`.alert-adding` 十字光标、
  `.alert-popup(-stack)`、`.alert-toast(-stack/icon)`，并补 light 主题覆盖 —— 与 `.chart-extreme-price-tag`
  的既有主题约定保持一致。

## Verification
| Command | Result |
| --- | --- |
| `node --check main_enhanced.js / modules/price_alerts.js` | Pass |
| `node --test tests/js/*.test.js` | **69 passed**（含新增 18 项 price_alerts 单测） |
| `.venv\Scripts\python.exe -m pytest -q` | **827 passed, 89 subtests passed** |

### 浏览器实测（CDP 驱动真实 Chromium，A股实时看盘 · 贵州茅台 600519 · 现价 1276.73）
| # | 场景 | 结果 |
| --- | --- | --- |
| A1 | 进入看盘 | 模块已加载；「预警」按钮可见；K线 800 根 |
| A2 | 点「预警」 | 落线模式开启，按钮 `is-adding`，图表十字光标 |
| A3 | 点击图区 | 生成「价格涨至: 1400.67」（高于现价→涨至），1 标签 + 1 价格线 + Toast「✓添加成功」 |
| A4 | 持久化 | `kline-ashare-live-alerts-v1::600519` 写入成功 |
| A5 | 拖动柄改价 | 1400.67 → 1292.31，标签文字实时跟随 |
| A6 | 穿越触发（1291.81→1292.81 跨 1292.31） | `triggeredAt` 置位 / `enabled=false` / 弹窗「贵州茅台 600519 · 价格涨至: 1292.31 现价 1292.81 · 触发时间 13:41:26」/ 标签转「· 已触发」置灰 / 存储键已清空 |
| A7 | 重复判定 | 不再二次触发 |
| A8 | 退出→重进 | 预警按标的恢复（1 条 / 1 标签 / 1 价格线），按钮正常 |

截图（临时目录，未入库）：`alert-1-added.png`（标签+Toast）、`alert-2-triggered.png`（置灰+弹窗）。

## 涉及文件
- 新增：`frontend/js/modules/price_alerts.js`、`tests/js/price_alerts.test.js`、
  `tests/test_price_alerts_frontend_static.py`（17 项静态接线守卫）
- 修改：`frontend/js/main_enhanced.js`、`frontend/index_enhanced.html`、`frontend/css/style_enhanced.css`

## 备注 / 待用户验收
- 未执行 git 提交与推送；未清理既有未提交改动；未触碰 `.runtime/`、`.gitignore`、`启动项目.bat`。
- 浏览器验证用独立临时 profile（`%TEMP%\cdp-profile2`），未污染用户日常浏览器。
- 系统通知需用户首次授权（点「预警」或落线时请求）；若被拒绝则静默跳过，不影响弹窗与提示音。
- 验收建议：硬刷新 → 进实时看盘 → Alt+A 或点铃铛 → 图上点一下 → 拖动改价 → 等价格穿越看弹窗；
  再试换股 / 退出重进确认按标的隔离。
- 后续可分期：P2 涨跌幅预警、P3 成交量与指标（MACD/KDJ 金叉死叉）预警。
