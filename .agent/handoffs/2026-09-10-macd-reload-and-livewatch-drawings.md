# Session Handoff

## Session Goal
用户报告两个问题：
1. A股实时看盘上画的图在"重新进入"后不保留（希望保留）。
2. MACD 副图又不显示了（此前出现过），要求定位根因并修复。

## 问题 2：MACD 副图空白 —— 根因与修复

### 复现与定位（CDP 驱动真实 Chromium，非猜测）
用 Chrome DevTools Protocol 直连跑通完整路径（币圈训练 ⇄ A股实时看盘 双向），采集到的决定性证据：

- 症状量化：进入实时看盘后 `latestRenderedKlineData` 已是茅台 800 根（time 1788998400），
  但技术指标仍是币圈的 181 根（time 1719763200）、`dif = -1499.99`。
  两套时间戳不重叠 → 副图绘图区空白，仅图例行残留旧数据集数值。
- 控制台持续报 `加载技术指标失败: Error: Value is undefined`。
- 异常栈（决定性）：

```
Error: Value is undefined
    at Wn.removeSeries (lightweight-charts.standalone.production.js)
    at main_enhanced.js:7029   ← indicatorChart.removeSeries(series)
    at Array.forEach
    at clearTechnicalIndicatorSeries (main_enhanced.js:7029)
```

### 根因
`initializeChart()` 会销毁/重建三个图表实例（主图、成交量、副图），但**没有清空
`currentIndicatorSeries` / `bollSeries` 记账**。于是：

1. 重建后 `currentIndicatorSeries` 里仍是指向**已销毁图表实例**的 series；
2. 下一次 `loadTechnicalIndicator()` → `clearTechnicalIndicatorSeries()` 对旧 series
   调用 `removeSeries()`，Lightweight Charts 抛 `Value is undefined`；
3. 该异常被 `loadTechnicalIndicator` 的 catch 吞掉，`lastIndicatorData` 未更新、
   副图未重绘，但图例行保留上一数据集内容 → 表现为"MACD 又不显示了"。

只在**跨数据集切换**（币圈 ↔ A股实时看盘，或任何会重建图表的路径）时触发，
所以"从主页直接进实时看盘"看起来正常，掩盖了问题。

> 这也是项目记忆里长期挂着的"已知遗留问题：Legacy 盲盒日线模式可能日志
> `加载技术指标失败: Value is undefined`（非阻塞）"——它不是非阻塞，而是同一个 bug。

### 修复（`frontend/js/main_enhanced.js`，两处）
1. `initializeChart()`：重建图表前显式 `currentIndicatorSeries = []; bollSeries = {};`
   （记账与图表生命周期对齐），并写明注释防回归。
2. `clearTechnicalIndicatorSeries()`：`removeSeries` 逐条 try/catch 防御，单条失败不再
   中断整个副图刷新；记账无论如何清空（原实现用 `bollSeries.upper` 判空，还漏了
   BOLL 部分系列的场景）。
3. 顺手修同类状态泄漏：`startTrainingWithConfig()` 从实时看盘直接跳训练的分支里
   补 `asharePreLiveUiState = null;`——该路径不走 `exitAshareLiveWatch`，快照若不
   作废，之后任何一次 exit 都会用过期状态覆盖当前模式的副图/指标。

### 验证（浏览器实测，双向）
| 路径 | 结果 |
| --- | --- |
| 币圈(BTC 181根/1719763200) → 进实时看盘 | 指标 800 根 / 1788998400 / dif -1.99，`match: true` |
| 实时看盘 → 快速测试(BTC) 回币圈 | 指标 181 根 / 1719763200 / dif -1499.99，`match: true`，无 console 报错 |
| 截图 | 副图柱状图 + DIF/DEA 线双模式均正常渲染 |

## 问题 1：实时看盘画图持久化

### 现状（改前）
画图只存在于 `DrawingStore` 内存；`initializeChart()` → `initializeDrawingTools()` 每次
重建 `DrawingController`，故退出/重进（含刷新页面）后画图全丢。项目原本没有任何画图持久化。

### 落地（`frontend/js/main_enhanced.js`）
按"注入 store"方式实现，不改 `drawing_tools.js` 库：
- 新增 `ashareLiveDrawingsKey/readAshareLiveDrawings/persistAshareLiveDrawings/createAshareLiveDrawingStore`；
- **存储键按标的隔离**：`kline-ashare-live-drawings-v1::<symbol>`（600519 / 000858 …）；
- `initializeDrawingTools()` 构造 `DrawingStore` 时用已存快照播种，并包裹 `_commit`
  （所有增删改/undo/redo/clear 的唯一漏斗）与 `reset` 自动回写；空集合时删除键，不留垃圾；
- `switchAshareLiveStock()` 换股后重建绘图控制器 → 每只股票只显示自己的画图；
- **仅对实时看盘生效**：回放训练保持"每次训练从干净画布开始"（`clearSessionDrawings`）语义不变；
- 无 `DrawingStore` 或存储不可用时静默降级为纯内存画图。

### 验证（浏览器实测）
进入实时看盘 → 新增 1 条 trend → localStorage 出现
`kline-ashare-live-drawings-v1::600519` 长度 1 → 退出 → 重进 ⇒ store.size = 1、
types = ['trend']，画图恢复。

## 质量门禁
| Command | Result |
| --- | --- |
| `node --check frontend/js/main_enhanced.js` | Pass |
| `node --test tests/js/*.test.js` | **51 passed** |
| `.venv\Scripts\python.exe -m pytest -q` | **810 passed, 89 subtests passed** |

## 新增回归测试
`tests/test_indicator_rebuild_and_drawing_persistence.py`（10 项）——锁定上述两个修复的
结构不变式（记账重置先于图表创建、removeSeries 防御、store 注入、换股重建、快照作废），
防止再次回退。该 bug 已反复出现，值得长期看守。

## 涉及文件
- 修改：`frontend/js/main_enhanced.js`（4 处，见上）
- 新增：`tests/test_indicator_rebuild_and_drawing_persistence.py`

## 备注 / 待用户确认
- 未执行 git 提交与推送。
- 全程遵守禁令：未清理/覆盖既有未提交改动，未触碰 `.runtime/`、`.gitignore`、`启动项目.bat`。
- 验证期间通过界面的"一键极速开局"在 **default_user**（演示账号）下创建了几条币圈训练会话记录，
  属测试副产物，未删除（如需清理请指示）。
- 浏览器自动化用独立 Chrome 临时 profile（`%TEMP%\cdp-profile`），未污染用户日常浏览器 localStorage。
- 现有 `git diff --check` 遗留行尾空白仍存在（`main_enhanced.js` 约 10135 行，09-08 遗留，未触碰）。
