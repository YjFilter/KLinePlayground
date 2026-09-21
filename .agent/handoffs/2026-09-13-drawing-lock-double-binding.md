# Fix: 画图「锁定」按钮点了没反应 —— 按钮被绑定了两次，toggle 两次等于没点

- 日期：2026-09-13
- 用户报告：选中画线后按浮动工具条的 🔒 锁定，**毫无反应**，对象照样能被拖动。
- 修复后：全量 `pytest -q` → **859 passed / 89 subtests**（853 → +6）。

## 1. 根因（真实浏览器取证，非猜测）

一次点击 → `toggleLock()` 被调用 **2 次** → `locked: false → true → false`，净效果为零。
同时状态栏最终显示「🔓 已解锁」，所以用户看到的就是"没反应"。

双绑定来源（两个绑定器都匹配到了同一批按钮）：

| 绑定器 | 位置 | 选择器 |
|---|---|---|
| 通用绑定 | `bindDrawingEventHandlers()` | `document.querySelectorAll('[data-drawing-action]')` |
| 浮动工具条专属 | `bindDrawingFloatingToolbar()` | `toolbar.querySelectorAll('[data-drawing-action]')` |

浮动工具条（`#drawing-floating-toolbar` 里的 sync-order / drag / settings / **lock** / **hide** / delete）
同时命中两者 → 每个按钮挂了 2 个 click 监听。

**为什么只有「锁定 / 隐藏」坏**：
- `lock` / `hide` 是**纯 toggle** → 跑两次 = 原样，看起来"没反应"；
- `delete` 跑两次，第二次因选中已清空而是 no-op → 看起来正常；
- `settings` / `sync-order` / `drag` 不在通用 `methodMap` 里，通用那次是空操作 → 看起来正常。

取证过程（CDP + 真实 Chromium）：
1. 注入一条水平线并选中 → 点击锁定 → `locked` 仍为 `false`，但状态栏出现「🔓 已解锁」
   ⇒ 证明 `invokeDrawingAction('lock')` 确实执行了，只是 `toggleLock` 净效果为零；
2. 给 `drawingController.toggleLock` 打计数桩 → **一次点击 `calls: 2`**；
3. 用 `cloneNode` 克隆按钮（不带任何旧监听）手动只挂一个 click → `calls: 1`、
   `locked: true`、按钮高亮、锁体闭合 ⇒ 功能本身完全正常，纯粹是重复绑定。

> ⚠️ 上一轮我结论错误的原因：我直接调用 `drawingController.toggleLock()` 验证，**绕过了按钮与事件链**，
> 所以测不到双重绑定，还误判成"功能正常、只是缺视觉反馈"。用户被打脸两次，这是我的验证方法错误。

## 2. 修复

**`frontend/js/main_enhanced.js`**
1. 通用绑定**跳过浮动工具条内的按钮**（它们由专属处理器接管，含 settings/sync-order/drag 分支）：
   ```js
   document.querySelectorAll('[data-drawing-action]').forEach((button) => {
       if (button.dataset.drawingBound === '1') return;
       if (button.closest('#drawing-floating-toolbar')) return;   // ← 新增
       button.dataset.drawingBound = '1';
       button.addEventListener('click', () => invokeDrawingAction(button.dataset.drawingAction));
   });
   ```
   注意：跳过必须发生在写入 `drawingBound` 标记**之前**，否则按钮会被标记成"已绑定"却没人管。
2. 顺手修一个隐患：`applyDrawingLockVisualState()` 原来对**所有** `[data-drawing-action="lock"]`
   按钮无脑重写锁体路径，而主工具条的锁是 **16×16 几何**（`M5.6 7V5.6a2.4…`），写入 24×24 的锁体
   会把图形画到 viewBox 外 → 图标消失。现在只在当前 `d` 等于已知的 24×24 锁体几何时才替换。

控制器侧（`drawing_tools.js`）**没有改动** —— 它本来就是对的：
`hitTest` 对锁定对象只返回 `{locked:true}` 且不再绘制锚点手柄；`_onPointerDown` 命中
`hit.locked` 直接 `return` 不建手势；`deleteSelected` / `updateSelectedLineSettings` /
`updateFibonacciSettings` 也都有 `locked` 守卫。

## 3. 验证（带阳性对照，结论才可信）

第一次合成拖动测试时，连**未锁定**的线也"拖不动" —— 说明是测试手段的问题，不是应用的问题。
定位：`_capturePointer()` 调 `element.setPointerCapture(pointerId)`，合成事件的 pointerId
没有活动指针 → 抛 `NotFoundError` → 手势根本没建立。给该元素垫一层 try/catch 垫片后重测：

| 步骤 | 结果 |
|---|---|
| **阳性对照**：未锁定线，同法拖动 | `59853.66 → 66446.1`，`moved: true` ✅（证明拖动手段有效） |
| 同一条线锁定后再拖 | `66446.1 → 66446.1`，`moved: false` ✅ **锁住，拖不动** |
| 隔离性：另配一条未锁定线 | `63555.94 → 56472.44`，`moved: true`，锁定的那条未被牵连 ✅ **锁 A 不影响 B** |
| 点击锁定按钮 | `locked:true`、按钮高亮、锁体闭合、提示「🔒 已锁定：该图形不可拖动/缩放（仅对这一个图形生效）」 ✅ |
| 再点一次解锁 | `locked:false` ✅ |
| 控制台错误 | 无 ✅ |
| 全量 `pytest -q` | **859 passed, 89 subtests** ✅ |

新增 `tests/test_drawing_lock_binding_static.py`（6 项）：通用绑定必须跳过浮动工具条、
跳过必须先于"已绑定"标记、lock→toggleLock 映射、锁定后状态回刷、锁体替换不得污染 16×16 图标、
控制器侧 `hit.locked` 拦截仍在。

## 4. 经验（写给自己）

1. **测 UI 按钮必须走真实事件序列**（pointerdown → click，`detail:1`），不能直接调 `controller.method()`——
   直接调方法会绕过事件链，测不出重复绑定这类问题。这次就是被"直接调方法"骗了一轮。
2. **"没反应"要分流两个方向排查**：事件根本没到？还是到了但被抵消？给目标方法打计数桩一眼分辨。
3. **合成 pointer 拖动会被 `setPointerCapture` 卡死**：先垫 try/catch 垫片，且必须先做**阳性对照**
   （证明未锁定时能拖），否则"没动"这个结论不可信。
4. toggle 型按钮（lock/hide）是重复绑定的天然探针：只要哪天某个 toggle "没反应"，
   第一反应查是不是被绑了两次。

## 5. 影响范围

- 仅前端 `frontend/js/main_enhanced.js`（2 处）+ 新增测试文件；**无需重启后端**，硬刷新（Ctrl+Shift+R）即生效。
- 主工具条的 锁定/隐藏/删除/撤销/重做/清空 仍走通用绑定，行为不变。
- 未提交未推送；`.runtime/`、`.gitignore`、`启动项目.bat` 未触碰。
