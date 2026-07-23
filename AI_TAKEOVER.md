# AI 接手入口

这份文件是新 AI 接手项目时的最短入口。不要让新 AI 先读取全部聊天记录，也不要把整个仓库一次性塞进上下文。

## 项目位置

`E:\Desktop\01_TODO\mimo\KLinePlayground`

## 推荐读取顺序

1. `AGENTS.md`
2. 本文件 `AI_TAKEOVER.md`
3. `.agent/STATE.md` 最后 120 行
4. `.agent/handoffs/` 中按修改时间排序后的最新一份交接文档
5. 当前需求涉及目录下的代码和测试

只有需要架构背景时再读取：

- `.agent/ARCHITECTURE.md`
- `.agent/DOMAIN_RULES.md`
- `.agent/WORKFLOW.md`
- `.agent/QUALITY_GATES.md`

## 当前状态摘要

- 分支：`master`。
- 当前存在大量尚未提交的功能改动，不能清理、覆盖、回滚或统一格式化。
- 最近完成币圈默认两年历史、按月离线缓存准备、5m/15m 分段加载、跨周期连续性和下一根性能优化。
- 最新完整验证：`717 passed, 71 subtests passed`。
- 最新交接：`.agent/handoffs/2026-07-22-crypto-two-year-history-continuity.md`。
- 本地服务应监听 `0.0.0.0:8000`；接手时必须重新检查，不能相信旧 PID。
- 已知控制面遗留问题：`python scripts/agent_status.py .agent/tasks` 会报告 `.agent/tasks/done/TASK-023-result.md` 缺少任务元数据。它是结果报告而不是标准任务包，未获得主 Agent 审查前不要移动或改写。

## 绝对禁止

- 不删除、覆盖、回滚、暂存或提交现有未提交改动。
- 不处理 `.runtime/`、本地用户、凭据、离线行情文件和 Vercel 本地绑定信息。
- 不修改 `.gitignore` 和 `启动项目.bat`，除非用户明确要求。
- 不混用 Binance 与 Bybit 的同一训练数据。
- 不破坏未来数据隔离、订单执行顺序、手续费、仓位和报告持久化规则。
- 不创建 commit、分支或推送，除非用户明确要求。

## 协作规则

- 主 Agent 负责架构、拆分、代码审查、集成、测试和最终验收。
- WorkBuddy 或其他 AI 只执行边界清晰的任务包。
- 每个并行任务必须有互不重叠的 `write_scope`。
- 外部 AI 完成后只能提交结果报告，不能自行宣布项目完成。
- 任务包使用 `.agent/templates/task.md`；结果报告使用 `.agent/templates/result.md`。
- 大任务结束后更新 `.agent/STATE.md`，并在 `.agent/handoffs/` 新增简洁交接。

## 常用命令

```powershell
cd E:\Desktop\01_TODO\mimo\KLinePlayground
git status --short
git log -5 --oneline
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/
node --check frontend/js/main_enhanced.js
python -m compileall -q backend
python -m pytest -q
git diff --check
```

启动服务：

```powershell
python -m flask --app backend.app_enhanced run --host 0.0.0.0 --port 8000
```

## 给用户的使用方式

- 新的主 AI：复制 `.agent/prompts/MAIN_AGENT_PROMPT.md` 全文。
- WorkBuddy 实现任务：复制 `.agent/prompts/WORKBUDDY_TASK_PROMPT.md`，填好占位内容。
- 只想继续当前项目：把下面一句发给主 AI：

```text
请按 E:\Desktop\01_TODO\mimo\KLinePlayground\AI_TAKEOVER.md 接手项目，先完成其中的状态检查，再等待并执行我的下一项需求。不要清理现有未提交改动，不要处理 .runtime/。
```
