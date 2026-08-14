---
id: TASK-024
title: 修复前端弹窗 z-index 遮挡问题（第一批）
status: done
priority: P1
owner: QoderWork
depends_on: []
write_scope:
  - frontend/css/style_enhanced.css
read_scope:
  - frontend/index_enhanced.html
  - AI_TAKEOVER.md
  - .agent/STATE.md
quality_profiles:
  - control-plane
---

## Background
前端存在两个 z-index 层级导致的弹窗遮挡 bug：
1. chart-focus-mode z-index=10000 远高于弹窗 z-index=1000，全屏模式下未隐藏的弹窗（#data-sync-modal、#crypto-history-prepare-modal）被完全遮挡，用户点了按钮看不到弹窗
2. loading-overlay 与 modal 同为 z-index=1000，loading-overlay 在 HTML 中位于所有 modal 之后渲染，同层级后渲染盖住前面的，导致弹窗里的"取消/重试"按钮无法点击

## Goal
统一 z-index 层级，使弹窗始终可显示在最上层，加载遮罩不遮挡弹窗。

## 修复方案
最终层级关系：全屏模式(900) < 加载遮罩(1000) < 弹窗(1100)

具体修改（全部在 frontend/css/style_enhanced.css）：

| 选择器 | 行号（约） | 当前值 | 改为 |
|--------|-----------|--------|------|
| `.modal` | 384 | `z-index: 1000` | `z-index: 1100` |
| `#main-app.chart-focus-mode` | 3888 | `z-index: 10000` | `z-index: 900` |
| `.loading-overlay` | 1745 | `z-index: 1000` | 不改 |

## Non-Goals
- 不改 chart-focus-mode 的 display:none 隐藏列表（第3895-3902行保持不变）
- 不改 loading-overlay 的 z-index
- 不改任何其他文件
- 不做 z-index 全局统一规范（第三批任务）
- 不创建 commit、分支或推送

## Constraints
- 保留现有未提交改动，不清理/覆盖/回滚
- write_scope 之外的文件只读
- 如方案超出此范围，停下来报告 blocker

## Acceptance Criteria
- [ ] `git diff` 只显示 frontend/css/style_enhanced.css 改动
- [ ] `node --check frontend/js/main_enhanced.js` 通过
- [ ] `python -m compileall -q backend` 通过
- [ ] `git diff --check` 无空白错误
- [ ] 浏览器验证：币圈全屏模式下弹窗可显示在最上层；加载遮罩出现时弹窗按钮仍可点击

## Required Commands
```powershell
cd D:\AI_work\KLinePlayground
git diff --stat
node --check frontend/js/main_enhanced.js
python -m compileall -q backend
git diff --check
python -m flask --app backend.app_enhanced run --host 0.0.0.0 --port 8000
```

## Result Contract
Move the task to `.agent/tasks/review/` and attach a result report using `.agent/templates/result.md`. Do not mark the task done.
