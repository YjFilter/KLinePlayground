# Session Handoff

## Session Goal
用户指出两个具体问题（附截图）：
1. **交易记录没有日期** —— 只显示 `12:28:00`，不知道是哪天买的。
2. **图上没有买入的标志** —— 成交后 K 线图上完全看不到买卖点。

两条都已实现并通过真实浏览器验证。另外上一轮已完成的「当前持仓只显示本股票」见
`2026-09-11-position-card-current-symbol-only.md`。

## 问题 1：交易记录补日期

### 改动前
`renderAshareLiveAccount()` 的历史成交行只输出 `${t.time}`。
且更早的**限价成交**记录（`matchAsharePendingOrders` 里的两处 `trade_history.unshift`）
根本没有写 `date` 与 `symbol` 字段——即使补了显示，这些记录也没有日期可用。

### 改动（`frontend/js/main_enhanced.js`）
- 新增 `formatAshareTradeStamp()`（`MM-DD HH:MM:SS`）与 `formatAshareTradeStampFull()`（完整日期）。
- 历史成交行改为显示 `MM-DD HH:MM:SS`，并把完整时间挂到 `title`（悬停可见），
  两处输出都过 `escapeHtml`（原实现 `t.name` 未转义，顺带收紧）。
- 限价成交记录补齐 `date` / `symbol` / `lots` / `bar_time`，与市价记录字段对齐。

> 没有日期的历史遗留记录会退化为只显示时间（无日期可显示），不报错。

## 问题 2：K 线上显示买入/卖出标志

### 设计：从成交记录反推标记，不另存一份
`trade_history` 本身已持久化在 `kline-ashare-live-account` 里，标记直接从它推导，
天然随账户保存/恢复，不会出现"标记与记录不一致"。

新增三个函数：
- `currentAshareBarTime()`：取当前渲染的最后一根 K 线时间。
- `ashareTradeBarTime(record)`：把一条成交记录映射到图表 K 线时间。
  1. 优先用成交瞬间写入的 `bar_time`（同周期下精确到具体 K 线，含分钟线）；
  2. 回退：把 `date + time` 换算到图表时间域再交给既有
     `alignTradeMarkerTimeToRenderedBar()` 对齐（换周期后仍能落回当日/当周那根 K 线）。
     日线尤其重要——日线 bar 时间是"该日 UTC 零点"，直接用浏览器本地时间戳会整整差一天。
  3. 两者都落不到当前 K 线上则跳过（避免把标记丢到图表外）。
- `updateAshareLiveTradeMarkers()`：按 `symbol` 过滤本标的成交，渲染成标记。
  买入=红色/箭头上/贴在 K 线**下方**，卖出=绿色/箭头下/贴在 K 线**上方**（买卖文字）。

### 顺带扩展 `updateTradeMarkers()`
新增可选覆盖 `marker.position / color / shape / label`（原实现只认 `type`）。
- 不传时行为与原来完全一致 —— 币圈/回放标记零影响。
- 传了就用显式值：解决"箭头上下位置跟着 K 线涨跌翻转"导致同一笔成交忽上忽下的问题。
- `label` 用于显示中文「买/卖」，原来是英文 `B/S`。

### 刷新时机（6 条路径全部覆盖）
`loadAshareLiveData`（进入看盘 / 换股 / 换周期）、市价买入、市价卖出、限价成交、
清空成交记录、重置账户。

## Verification
| Command | Result |
| --- | --- |
| `node --check frontend/js/main_enhanced.js` | Pass |
| `node --test tests/js/*.test.js` | **69 passed** |
| `pytest -q` | **838 passed, 89 subtests passed** |

### 浏览器实测（CDP + 真实 Chromium，A股实时看盘 · 600519）
用一份包含 5 条记录的成交历史（含跨标的、含无日期遗留记录、含只有 `code` 的早期限价成交）验证：
| 场景 | 结果 |
| --- | --- |
| 带 `bar_time` 的买入 | 精确落在记录的 bar（2026-09-09），红色「买」/ belowBar |
| 只有 `date` 的卖出 | 回退按日期对齐到 2026-09-10，绿色「卖」/ aboveBar |
| 只有 `code` 的早期限价成交 | 兼容通过，落在 2026-09-11，红色「买」 |
| 其他标的（601727）的成交 | **不出现**在本标的图上 |
| 完全没有日期的遗留记录 | 跳过且不报错 |
| 交易记录行 | 显示 `09-09 10:15:30 · 费¥30.00`，`title` 为完整 `2026-09-09 10:15:30` |

截图：`outputs/成交标记-K线上买入卖出.png`（放大后的买/卖箭头）、
`outputs/成交标记-全貌含交易记录日期.png`（全貌 + 右栏交易记录带日期）。

## 涉及文件
- 修改：`frontend/js/main_enhanced.js`
- 新增：`tests/test_ashare_trade_markers_static.py`（11 项静态守卫）

> 写守卫时踩到一个坑并已修好：`main_enhanced.js` 里留着被注释掉的旧
> `// function updateTradeMarkers(...)`，朴素 `str.find` 会命中注释体，导致断言对着死代码跑。
> 测试里的 `_extract_function` 现已跳过行首为 `//` 的定义。

## 备注
- 未执行 git 提交与推送；未清理既有未提交改动；未触碰 `.runtime/`、`.gitignore`、`启动项目.bat`。
- 浏览器验证用独立临时 profile，未污染用户日常浏览器。
- 未改「限价挂单」区块：它按设计就是跨标的的（含撤单），用户本次未提及。
- 若之后想让**交易记录**也只显示本股票，是同一处渲染里的一个 filter，随时可加。
