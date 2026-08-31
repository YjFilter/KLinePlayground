# AI 接手入口

这份文件是新 AI 接手项目时的最短入口。不要让新 AI 先读取全部聊天记录，也不要把整个仓库一次性塞进上下文。

## 项目位置

`D:\AI_work\KLinePlayground`

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

- 分支：`main`（另有 `backup/pre-multiperiod-20260812` 备份分支）。
- 当前存在大量尚未提交的功能改动，不能清理、覆盖、回滚或统一格式化。
- 最近完成币圈默认两年历史、按月离线缓存准备、5m/15m 分段加载、跨周期连续性和下一根性能优化；随后完成 AICoin 风格 UI 多阶段改造、画图工具扩展与浮动工具条、斐波那契趋势时间（价格档位版）、基于风险的仓位计算、MACD(10,20,5)/MA(10,20,40,80,160) 默认参数。
- 2026-08-17 ~ 08-26 完成 Stage 2/3 前后端模块化拆分、币圈回放周期失步修复、快照刷新替换图表窗口修复；对应 19 项未提交改动（详见回填交接）。2026-08-30 接手后在此基础上继续治理优化。
- 最新完整验证：`784 passed, 89 subtests passed`（2026-08-30 晚复核，全绿；含 19 个 JS node:test 单测门禁）。
- 最新交接：`.agent/handoffs/2026-08-30-frontend-module-wiring.md`（此前同日：governance-optimization、08-26 回填、08-14 git 修复）。
- 本地服务应监听 `0.0.0.0:8000`；接手时必须重新检查，不能相信旧 PID。
- 已知控制面遗留问题：`python scripts/agent_status.py .agent/tasks` 会报告 `.agent/tasks/done/TASK-023-result.md` 缺少任务元数据。它是结果报告而不是标准任务包，未获得主 Agent 审查前不要移动或改写。
- 2026-08-14 修复过本地 git 对象库缺失（HEAD 提交 `338bb62` 的对象被整体删除，git 全命令报 `fatal: bad object HEAD`）。恢复方式：curl 走 git smart-http 下载 packfile + `git index-pack`；注意本执行环境 git 自带 TLS 直连 GitHub 会被间歇性重置（`SSL_ERROR_SYSCALL`），网络取数用 `curl.exe` 更稳。

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
cd D:\AI_work\KLinePlayground
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
请按 D:\AI_work\KLinePlayground\AI_TAKEOVER.md 接手项目，先完成其中的状态检查，再等待并执行我的下一项需求。不要清理现有未提交改动，不要处理 .runtime/。
```
