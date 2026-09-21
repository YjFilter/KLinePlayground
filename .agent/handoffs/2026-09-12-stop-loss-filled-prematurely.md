# Fix: 止损线未到价就被平仓 —— 平仓单必须区分「限价=止盈 / 突破=止损」

- 日期：2026-09-12
- 用户报告：开多后把止损线拖到现价下方，价格还没到，点一下"下一根 K 线"就立刻被平仓。
- 结论：**上一轮改动的回归**。修毕，全量 `pytest -q` → 853 passed / 89 subtests。

## 1. 根因（一句话）

拖动创建保护单时**无条件发平仓限价单**，而引擎对"卖出限价"的撮合条件是 `high >= 限价`。
止损挂在现价**下方** → `high >= 止损价` 恒成立 → **下一根 K 线必然成交**。

上一轮我以"平仓不设限制"为由删掉了 `_validate_pending_direction` 里
"平多限价必须高于现价"的校验，恰好拆掉了唯一能拦住这个组合的护栏。

> 领域规则（必须记住）：**"限价平仓挂在现价外侧"在交易所语义里是可立即成交的单，
> 它只能当止盈，不能当止损。** 止损必须用突破单（价格穿越触发价才成交）。

引擎里其实一直是正确实现（`_create_tp_sl_orders`）：TP → `limit`，SL → `breakout`。
缺的只是把这条规则用到"用户手工拖出来的保护单"上。

## 2. 修复清单

### 前端 `frontend/js/main_enhanced.js`
| 位置 | 改动 |
|---|---|
| `resolveCloseOrderType()` | **新增**，唯一真源：多头价在上=止盈(limit)/在下=止损(breakout)；空头相反 |
| `createProtectiveOrderFromDrag()` | 复用解析器；止损发 `breakout + trigger_price`，止盈发 `limit + limit_price`；新增"等于标记价"与"无持仓"守卫 |
| `submitCryptoOrder()` | `action==='close'` 时按价位自动改判类型，用户只填价位；成功提示注明自动选择结果 |
| `validateCryptoPendingPrice()` | 恢复平仓方向校验，文案指路"改用突破单" |
| `updateChartTradePriceLines()` | 角色**以订单类型为准**（原来按成本价上下侧判断，浮盈时会把止损误标成止盈） |
| `getCryptoProtectivePrices()` | 不再要求 `parent_order_id`，按类型识别 → 手工保护单也进持仓卡片 |
| `buildChartTradeLinePill()` | 浮层第二段原来写死「市价」→ 改为真实类型（限价/突破） |

### 后端 `backend/crypto/futures_orders.py`
- `_validate_pending_direction()`：恢复平仓限价方向护栏（文案指路改用突破单）。
- `_retarget_reduce_only_order()`（新）：保护单拖过现价另一侧时**自动改判类型**（limit↔breakout，
  `protection_type` 同步）；拖到正好等于标记价 → `invalid_limit_direction`。
- `modify_order_price(order_id, new_price, timestamp, current_price=None)`：接入上述改判；
  并新增 `_validate_amend_direction()` 拒绝把**开仓挂单**改到会立即成交的一侧。
- `_protective_priority()`（新，模块级）：把"手工平仓突破单=止损"纳入同根 K 线撮合优先级
  （止损优先于止盈，保守撮合），与显式子单同规则。

### 路由 `backend/routes/training_routes.py`
`PUT /orders/{id}` 透传 `current_price`（取 `simulator.last_mark_price or position.entry_price`），
并把 `FuturesOrderError` 映射为 400 + code（原来会掉成 500）。

## 3. 验证

| 项目 | 结果 |
|---|---|
| `node --check main_enhanced.js` | ✅ |
| 全量 `pytest -q` | ✅ **853 passed, 89 subtests**（838 → +15） |
| 浏览器：拖动止损的请求体 | ✅ `{"action":"close","order_type":"breakout","trigger_price":55534.32}` → 200 |
| 浏览器：浮层文案 | ✅ `止损 \| 突破 \| 预估收益 -98.73 (-100.00%) \| 距当前价 -10.00% \| 0.016 \| ✕` |
| 浏览器：**点下一根 K 线** | ✅ `sideBefore=long → sideAfter=long`，**未提前平仓** |
| 浏览器：对称验证 | ✅ bar1 low 62464.4 > 止损 62435.75 → 仍持仓；bar2 low 61779.6 穿越 → 成交平仓 |
| 控制台错误 | ✅ 无 |

新增测试：
- `tests/test_crypto_binance_orders.py` — 平仓限价方向护栏 + 穿越前不成交 + 拖过界改判 + 边界拒绝
- `tests/test_crypto_futures_api.py::test_stop_loss_survives_bars_that_do_not_reach_it` — HTTP 级复刻用户场景
- `tests/test_crypto_order_modification.py` — `PUT /orders/{id}` 改判类型 / 拖到标记价 400
- `tests/test_crypto_protective_order_type_static.py`（新，9 项）— 含 Node 真跑 `resolveCloseOrderType` 几何用例

> 守卫当场抓到一次漂移：拖动路径最初自己内联算类型、没复用 `resolveCloseOrderType`。已改为一处真源。

## 4. ⚠️ 必须重启后端

8000 端口的进程启动于 22:07，本轮后端改动在 22:14 之后 → **跑的是旧代码**（`flask run` 无 `--debug`）。
- 前端由 static 直接 serving，**硬刷新即生效**（"止损不再提前平仓"仅靠前端改动就已修复）；
- **"拖动改价跨过现价自动改判类型"与 API 层护栏需要重启后端**才生效。

## 5. 未做 / 待确认
- 规格"挂单还没成交时就挂止盈止损"仍需后端支持（`modify_order_price` 现在只处理价格与类型，
  不接受事后补挂 tp/sl）。
- AICoin 持仓行的「平 / 市 / 反」快捷按钮仍未做。
- A股实时看盘的"穿越式止损"仍未实施（前端撮合无服务端条件单引擎）。
