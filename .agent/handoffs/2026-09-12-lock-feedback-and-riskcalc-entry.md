# Session Handoff

## Session Goal
用户一次性提了 4 项（附 5 张截图），并要求"重新梳理一下这些逻辑对不对，有不懂问我"。

**本会话交付：修好 #1、#2；#3（AICoin 风格拖动止盈止损线）与 #4（平仓限价方向限制）已完成逻辑梳理，等用户决策后再实现。**

---

## 已完成 #1：锁定按钮"看不出锁没锁上"

### 结论（先纠正一个前提）
代码层面**锁定是按单个对象生效的，且确实能阻止拖动**——用 CDP 驱动真实 Chromium 实测：
- `锁定 A 后拖动 A` → 价格未变（`priceMoved:false`）、图表也没被平移（`chartPanned:false`）
- `拖动未锁的 B（对照）` → 正常移动
- 锁定 A 时 B 仍是 `locked:false` → **不会"一锁全锁"**，用户担心的这点不成立
- 现有单测 `tests/test_drawing_tools_frontend.py` 也已覆盖"锁定后不可拖动"

所以真正的问题是**没有任何视觉反馈**，导致误判：
- `syncDrawingFloatingToolbar()` 只在**选中变化**时被调用（挂在 `onSelectionChange`），
  而 `toggleLock()/toggleHidden()` 改完模型只调 `refresh()`、不触发选中变化
  → 实测：`locked:true` 但 `toolbarLockActive:false`，浮动工具条的锁定高亮**从来不亮**
- 锁体图标是静态 SVG（始终是闭合挂锁），锁定/未锁**长得一模一样**

用户截图放大后也印证：唯一的白框是**焦点环**，不是"已锁定"状态。

### 改动
- `frontend/js/drawing_tools.js`：`toggleLock()` / `toggleHidden()` 在 `refresh()` 后补
  `this._emitSelectionChange()`——锁定对象仍处选中态，必须通知上层。
- `frontend/js/main_enhanced.js`：新增 `applyDrawingLockVisualState(model)`，统一更新
  **主工具条 + 浮动工具条**两处锁定按钮的 `.active` / `aria-pressed` / `title`，
  并切换锁体形状（闭合 `M8 11V7a4 4 0 0 1 8 0v4` ↔ 开口 `M8 11V7a4 4 0 0 1 7.7-1.6`）；
  由 `syncDrawingFloatingToolbar()` 调用（取消选中时也复位）。
- `invokeDrawingAction()`：锁定/隐藏/删除后显式回刷一次状态，锁定后给出提示文案
  「🔒 已锁定：该图形不可拖动/缩放（仅对这一个图形生效）」。

### 实测
| 时机 | active | 锁体 d | 提示 |
| --- | --- | --- | --- |
| 点击前 | false | 开口 | 锁定当前对象（锁定后不可拖动） |
| 点击后 | **true** | **闭合** | 🔒 已锁定：该图形不可拖动/缩放（仅对这一个图形生效） |
| 再点一次 | false | 开口 | — |

主工具条同步高亮（`mainToolbarActive:true`）。

> 「还是会被拖动」在标准拖动路径下**无法复现**。若用户仍能拖动，需要他提供确切步骤
> （哪个图形类型、当时激活的是哪个工具、是否重新进入过看盘）。注意截图里选中对象带了
> 「同步到下单区」按钮，说明**选中的是做多/做空测算框**（`isRiskDrawing`），不是普通水平线，
> 复现时应以测算框为对象。

---

## 已完成 #2：市价单的"以损定仓·开仓价"不跟随实时价

### 根因
`getCryptoRiskCalcParams()` 原是：
```js
entryPrice: entryInput > 0 ? entryInput : preview.entryPrice
```
`getCryptoOrderPreview()` 对市价单已正确取 `entryPrice = currentPrice`（面板"计算价格"显示的就是现价），
但只要用户在「开仓价」输入框里**填过一次**，那个旧值就会**永远覆盖实时价**——
用户截图里 93878.43 的旧值 vs 实际 71321.1 就是这么来的，于是每次都得手改一遍。

### 改动（main_enhanced.js）
- `getCryptoRiskCalcParams()`：市价单强制使用 `preview.entryPrice`（实时标记价），忽略输入框旧值。
- 新增 `syncCryptoRiskCalcEntryPrice()`：市价单把「开仓价」输入框同步为实时价并 `readOnly`
  （`title` 说明"市价单按当前标记价成交，无需填写"），价格变化时顺带 `refreshCryptoRiskCalcResult()`；
  限价/突破单恢复可编辑，由用户填预计成交价。
- 在 `refreshCryptoOrderPreview()` 中调用，保证跟着行情走。

### 实测（真实币圈训练会话，BTCUSDT 现价 61704.8）
| 场景 | 结果 |
| --- | --- |
| 注入旧值 93878.43 + 市价单 | 输入框被拉回 **61704.8**、`readOnly:true`、`matchesLive:true`、`calcEntry:61704.8` |
| 以损定仓结果 | 数量 ≈ 0.00176708 · 名义 109.04 USDT（按实时价重算） |
| 切到限价单 | `readOnly:false`，恢复可编辑 |

---

## 待用户决策 #3：AICoin 风格"直接拖价格线设止盈止损"

用户要的是：**开仓后能在图上拖动价格线来设止盈/止损**，像 AICoin 那样带彩色药丸标签
（`止盈 市价 预估收益4.14 (191.09%) 距当前价: +1.66% 221.02 ✕` + 轴上的绿色 2570.00），
以及持仓线本身的快捷操作（`平 / 市 / 反`）。

现状：已有「止盈止损」弹窗按钮（持仓卡片上），但没有图上拖动。
**可直接复用本会话前一轮为 A股预警做的那套基建**：`candlestickSeries.createPriceLine()` 画虚线 +
贴价格轴的 DOM 标签（含拖动柄、✕、`priceToCoordinate`/`priceScale('right').width()` 定位、
在时间轴/resize/crosshair 多处 rAF 重定位）。

需用户确认的点：
- 拖动松手后是**立即提交**止盈止损单，还是**先预览再确认**？
- 止盈止损是**跟随持仓**（改价即改挂单）还是**每次新增一张条件单**？
- 药丸上要显示哪些字段（预估收益 / 收益率 / 距当前价 / 金额）？币圈的"预估收益"按什么口径算？
- 是否也要 A股实时看盘的持仓一起支持？

## 待用户决策 #4：为什么"平仓不能设价格"

### 现状（这是设计约束，不是 bug）
`backend/crypto/futures_orders.py:186-192`：
```
开多限价必须低于当前价格。
开空限价必须高于当前价格。
平多限价必须高于当前价格。   ← 用户撞的就是这条
平空限价必须低于当前价格。
```
即：**限价单只允许挂在"不会立刻成交"的一侧**（挂单才能挂进簿），
用户持仓 71321.1、想用限价 70000 平多 → 低于现价 → 立刻会被拒（`invalid_limit_direction`）。
前端 `validateCryptoPendingPrice()`（main_enhanced.js:8490-8503）只做同规则的前置提示。

### 需要用户决策
- 想"到价平仓"（含止损方向）→ **正解是止盈止损**（对应 #3），不是限价平仓；
- 或者希望**允许可立即成交的限价平仓**（市价化成交）→ 这是引擎语义变更，需明确后再动；
- 或者希望**平仓也能挂到任意价位**（例如挂一个远端的止盈）→ 当前规则下"平多挂高价"本来就是允许的，
  只是低于现价不行。

---

## 质量门禁
| Command | Result |
| --- | --- |
| `node --check main_enhanced.js / drawing_tools.js` | Pass |
| `pytest -q` | **838 passed, 89 subtests passed** |

## 涉及文件
- 修改：`frontend/js/drawing_tools.js`（toggleLock/toggleHidden 通知上层）
- 修改：`frontend/js/main_enhanced.js`（锁定视觉状态、以损定仓跟随实时价）

## 备注
- 未执行 git 提交与推送；未清理既有未提交改动；未触碰 `.runtime/`、`.gitignore`、`启动项目.bat`。
- 浏览器验证用独立临时 profile，未污染用户日常浏览器。
- #3、#4 未动代码，等用户回复。
