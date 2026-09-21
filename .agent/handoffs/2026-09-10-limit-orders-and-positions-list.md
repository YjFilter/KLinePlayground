# Session Handoff

## Session Goal
A股实时看盘下单面板补齐限价挂单；持仓卡片升级为全部持仓列表（用户资金为全部 A 股共用一个池子，单子状态需一卡片看清）。

## Changes
1. `frontend/js/modules/ashare_trading.js`：新增 normalizeAshareAccount / computeAvailableShares / matchLimitOrders / validateLimitBuy / validateLimitSell；本次起该模块被 main 真实消费（此前只拆不接）。
2. `frontend/index_enhanced.html`：补 modules script 标签；买卖子面板委托方式改为市价/限价切换 + 限价输入框；持仓卡片新增"限价挂单"小节容器。
3. `frontend/js/main_enhanced.js`：
   - 账户模型扩展（向后兼容）：cash_frozen / pending_orders / positions[].frozen_sell / last_date 跨日清理挂单；
   - executeAshareLiveBuy/Sell 限价分支 → submitAshareLimitBuy/Sell（提交即冻结）；
   - matchAsharePendingOrders：轮询快照（3s）撮合当前标的，跨日失效退冻结；cancelAsharePendingOrder 撤单退冻结；
   - renderAshareLiveAccount：全标的持仓列表（当前标的 ★置顶高亮、冻结标记 T+1/挂卖）、挂单小节（撤单事件委托）、总资产=现金+冻结+全持仓市值、持仓市值改全持仓口径、最大可卖扣挂卖冻结；
   - updateAshareOrderPreview 限价按输入价；价格内存缓存 asharePriceCache + recordAshareLastPrice。
4. `frontend/css/style_enhanced.css`：order-type-switch / limit-input / order-row / cancel-btn / current-symbol 高亮（全走 --crypto-* 变量，双主题适配）。

## Verification
| Command | Result |
| --- | --- |
| `node --check frontend/js/main_enhanced.js` | Pass |
| `node --test tests/js/*.test.js` | 47 passed（新增限价挂单 7 用例） |
| `npx eslint@8.57.0 frontend/js/modules/ tests/js/` | 0 告警 |
| `.venv\Scripts\python.exe -m pytest -q` | **800 passed, 89 subtests passed** |

## Notes
- 账户仍在 localStorage `ashare_live_account_v1`，旧数据无新字段读取时自动补齐。
- 挂单撮合仅对当前查看标的实时进行（轮询为单标的快照）；跨日失效在 getAshareLiveAccount 读取时全局清理兜底。多标的并行撮合需批量快照，暂不必要（单标的看盘场景）。
- 买卖手续费仍未模拟（用户未确认，此前方案待拍板项）。

## Next Action
用户硬刷新验收：市价/限价切换、挂单→撤单、限价成交、跨标的持仓列表、双主题观感。

未执行 git 提交与推送。

## Addendum: 手续费模拟 (2026-09-10 同会话追加)
- 费率（写死默认，简化口径）：佣金万 2.5 单笔最低 5 元双边；印花税 0.05% 仅卖出；过户费不计。纯函数 `computeAshareTradeFees(side, amount)` 入 ashare_trading.js + 2 用例。
- 接入点：市价买卖（资金检查/成本均价含买入佣金/回笼扣佣金+印花税）；限价买入冻结额含佣金（挂单新增 `frozen_amount` 字段，成交/撤单/跨日失效统一按其退回，向后兼容旧挂单按 price*shares 退）；成交记录与买卖预览显示费用（买入预览含佣、卖出预览扣费）。
- 门禁：node --check OK；JS 单测 **49 passed**；ESLint 0；pytest **800 passed, 89 subtests**。未提交未推送。
