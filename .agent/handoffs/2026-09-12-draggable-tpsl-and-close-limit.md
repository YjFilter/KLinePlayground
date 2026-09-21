# Session Handoff

## Session Goal
用户回复了上一轮的 4 个决策问题：
1. 松手后**立即提交**止盈止损单；
2. 拖动 = **修改这张已有的**止盈止损单；
3. 显示**像 AICoin 那样**（预估收益 / 距当前价 / 金额）；
4. 范围：币圈，A股实时看盘的持仓**也要**；
5. 补充 #4：**订单成交后，平仓不应再限制方向**——他要的就是止盈/止损效果，可能先在某价位止盈/止损一部分。

## 关键发现（先纠正了两处认知）

### 发现 1：拖拽改价的基建**早就存在**
`main_enhanced.js` 的「主图持仓均价线与止盈止损/挂单线可视化」段（约 8016 行起）已经实现：
- `updateChartTradePriceLines()` 画出 持仓均价线 / 挂单线（含 TP/SL）/ 兜底保护价线 / 强平线；
- `initChartTradeLineDragging()` 支持**拖动改价**，松手后真的提交 `PUT /training/{id}/orders/{orderId}`，
  拖动中还有 tooltip 显示 `距现价% | 预估收益`。
**所以"拖动改价"不用重做，缺的是"开仓后没有途径创建止盈止损"。**

### 发现 2：「到价止损」能力后端**本来就有**
`backend/crypto/futures_orders.py` 的 `_validate_pending_direction()`：
- 平多**突破**价必须低于现价 → 这本身就是"到价止损"；
- 平多**限价**必须高于现价 → 这才是用户被卡住的地方（他输 70000 低于现价）。
即：能力存在，但埋在一个不直观的「突破」单里，且报错信息没有给出路。

## 已完成

### A. 平仓限价解除方向限制（#4）
- `backend/crypto/futures_orders.py`：删除 limit 分支里两条 `reduce_only` 方向校验。
  **开仓限价仍保留限制**（避免误下会立刻成交的挂单）；突破单的方向校验保持不变。
  注释写明语义：平仓单会一直挂到价格触及才成交，低于现价的平多单 = 止损，高于现价 = 止盈。
- `frontend/js/main_enhanced.js` · `validateCryptoPendingPrice()`：`action === 'close'` 时跳过方向校验
  （只保留"当前没有可平仓持仓"的判断）。
- `tests/test_crypto_binance_orders.py`：`test_strict_limit_direction_rejects_equal_and_reversed_prices`
  的平仓循环由"断言被拒"改为"断言成功受理"，与新语义一致。

### B. 开仓后可拖动创建/修改止盈止损（#3）
`frontend/js/main_enhanced.js`：
- 新增 `buildChartProtectiveLineTitle()`：AICoin 风格文案
  `止盈 (TP): 62,938.9 距现价 +2.00% 预估 +3.7 USDT`（价格 + 距现价% + 预估盈亏），
  用于真实 TP/SL 线与占位线。
- 新增「**占位止盈/止损线**」：持仓已建立但缺少 TP/SL 时，在 `entry ± 2%` 处画虚线占位线
  （标题带「拖动设置」），**拖动即创建**真实平仓单。
- 兜底保护价线（`position.tp_price/sl_price`，无 orderId 无法改单）标记为 `isPlaceholder`，
  拖动时改为"按新价创建真实单"，不再是死线。
- `getHoveredTradeLine()` 放开对 `orderId` 的硬要求（占位线也可命中）。
- `finishDrag()` 增加占位线分支 → `createProtectiveOrderFromDrag()`：
  `POST /training/{id}/trade` body `{action:'close', order_type:'limit', limit_price}`，
  成功后用返回的 `pending_orders` 重渲染（占位线自动被真实线替换）。
- `frontend/index_enhanced.html`：面板提示由"止盈止损仅随开仓单生效"改为
  "开仓后也可直接在图上拖动止盈/止损线补设或改价（平仓限价任意价位皆可挂）"。

## Verification

| Command | Result |
| --- | --- |
| `node --check frontend/js/main_enhanced.js` | Pass |
| Python AST parse（futures_orders.py / 测试） | Pass |
| `pytest -q` | **838 passed, 89 subtests passed** |

`test_strict_limit_direction_rejects_equal_and_reversed_prices` 通过 = **后端引擎改动已被独立验证**
（低于/等于现价的平仓限价现在会被受理）。

### 浏览器实测（CDP + 真实 Chromium，币圈 BTCUSDT 现价 61704.8）
市价开多 0.003 @ 61704.8 后：
| 观察点 | 结果 |
| --- | --- |
| 持仓均价线 | `多 0.003 @ 61,704.8 [+0 USDT, +0.02%]` |
| 止盈占位线 | 62,938.9，标题 `止盈 (TP) 拖动设置: 62,938.9 距现价 +2.00% 预估 +3.7 USDT` |
| 止损占位线 | 60,470.7，标题 `止损 (SL) 拖动设置: 60,470.7 距现价 -2.00% 预估 -3.7 USDT` |
| 拖动止损线到 54,744.69 | **确实发出** `POST /trade` body `{"action":"close","order_type":"limit","limit_price":54744.69}` |
| 该请求结果 | `400 平多限价必须高于当前价格。` ← **运行中的后端是旧进程** |
| 失败后回滚 | 线位还原为 60,470.7，未产生挂单 ✓ |

### ⚠️ 必须重启后端
`启动项目.bat` 用的是 `python -m flask --app backend.app_enhanced run`（**没有 --debug**），
所以**没有自动重载**：正在跑的 8000 端口进程仍是旧代码，A 项改动尚未生效。

**用户需关闭当前 KLinePlayground 控制台窗口并重新运行 `启动项目.bat`**，
之后拖动创建、以及任意价位的平仓限价才会真正成功（引擎逻辑已由单测证明正确）。

> 我没有替用户重启：从 Agent 侧起的后台进程可能在会话结束时被回收，
> 反而会让用户的本地服务彻底消失，风险大于收益。

## 未完成 / 待确认
1. **AICoin 药丸样式的轴标签**：现在信息（价格/距现价%/预估收益）已在**线的标题**上，
   但还没做成"贴在价格轴上、带颜色圆角、可点 ✕"的药丸。
   可复用 A股预警那套 chip 基建（`createPriceLine` + DOM 标签 + `priceScale('right').width()` 定位）。
2. **A股实时看盘的止盈止损**：用户说"也要"，但 A股实时盘是**客户端模拟账户**
   （positions/pending_orders 存 localStorage，`matchAshareLimitOrders` 纯前端撮合），
   没有服务端条件单引擎。而且 A股限价撮合是"卖出限价 ≤ 现价即成交"，
   所以**低于现价的卖出限价会立刻成交，而不是挂着等触发**——
   要真正实现 A股止盈止损，需要新增一类"触发价到位才成交"的条件单（前端撮合逻辑内）。
   工作量与币圈这边不同量级，需确认后再做。

## 涉及文件
- 修改：`backend/crypto/futures_orders.py`、`frontend/js/main_enhanced.js`、
  `frontend/index_enhanced.html`、`tests/test_crypto_binance_orders.py`

## 备注
- 未执行 git 提交与推送；未清理既有未提交改动；未触碰 `.runtime/`、`.gitignore`、`启动项目.bat`（仅读取）。
- 浏览器验证用独立临时 profile，未污染用户日常浏览器。
