# Session Handoff

## Session Goal
画图工具快捷键：量尺/做多/做空/水平线/斐波那契等常用工具键盘快速选择（用户已确认 Alt+ 方案）。

## Keymap（Alt+ 层，TradingView 惯例）
Alt+M 量尺 / Alt+L 做多 / Alt+S 做空 / Alt+H 水平线 / Alt+F 斐波那契 / Alt+Q 选择 / Alt+T 趋势线 / Alt+R 射线 / Alt+B 矩形 / Alt+X 文字。
裸键 B/S/空格/Enter/数字已被币圈做单与回放推进占用——Alt 修饰键层先行拦截，Alt+S 做空与裸 S 卖出零冲突。

## Changes
1. `main_enhanced.js`：
   - 新增 `DRAWING_TOOL_SHORTCUTS / DRAWING_TOOL_LABELS / DRAWING_TOOL_KEY_HINTS` 映射；
   - 从工具按钮 click handler 提取共享 `activateDrawingTool(tool)`（激活/高亮/状态条含快捷键提示/fib-trend-time 面板特例），click 与 keydown 单一事实源；
   - keydown 训练段新增 Alt 分发层（守卫：training 可见 + 非只读 + 非输入框焦点 + 非 repeat + preventDefault）；
   - 新增 isAshareLiveMode 裸键守卫：A股看盘下 B/S/空格/数字不再误触币圈下单与回放推进（顺手修复的历史耦合），Alt 画图层不受影响。
2. `index_enhanced.html`：10 个工具按钮 title 追加 "(Alt+X)"。

## Verification
| Command | Result |
| --- | --- |
| `node --check frontend/js/main_enhanced.js` | Pass |
| `node --test tests/js/*.test.js` | 49 passed |
| `npx eslint@8.57.0 frontend/js/modules/ tests/js/` | 0 告警 |
| `.venv\Scripts\python.exe -m pytest -q` | **800 passed, 89 subtests passed** |

## Incident Note
title 批量替换脚本曾误删按钮 data-drawing-tool/aria-label/aria-pressed 属性（静态测试 test_drawing_controls_publish_accessible_names_and_state 当场抓出），已完整恢复并复核——静态断言测试再次证明其价值。

## Next Action
用户硬刷新验收三种模式（币圈回放/A股回放/A股实时）Alt+* 快捷键与 A股看盘裸键屏蔽。

未执行 git 提交与推送。
