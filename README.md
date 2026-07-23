![KLinePlayground](https://github.com/user-attachments/assets/9da63388-b17e-4235-a691-0e15c03c4fd3)

# KLinePlayground

面向个人投资者的本地 K 线复盘与模拟交易训练工具，支持 **A 股**和 **币圈 USDT 永续合约**。项目以历史行情回放为核心，提供多周期 K 线、模拟订单、画线分析、账户与仓位管理、训练报告，以及可选的 AI 复盘能力。

> 本项目只用于学习、研究和交易训练，不构成投资建议，也不会连接真实交易账户自动下单。

## 功能概览

### A 股复盘

- 指定股票和盲盒随机训练模式。
- 支持 30 分钟、4 小时、日线和周线等复盘周期。
- 模拟 T+1、涨跌停、交易费用、持仓和可用资金。
- 支持市价、限价、突破、止盈和止损等训练操作。
- 支持 AKShare、BaoStock、mootdx 等数据能力；具体可用性取决于本机环境和数据覆盖。
- 自动生成训练记录、交易明细、收益、胜率和复盘报告。

### 币圈永续合约复盘

- 支持 Binance、Bybit 的 USDT 永续合约数据，常用训练标的包括 `BTCUSDT`、`ETHUSDT`。
- 支持 `5m`、`15m`、`30m`、`1h`、`4h`、日线和周线七个周期。
- 新建训练默认准备训练起点之前 **2 年**历史数据，可选择 `2–5` 年。
- 缺失行情按自然月自动下载，并保存到本地月度离线缓存；同一训练不会混用不同交易所数据。
- 5m 和 15m 使用每段最多 12,000 根 K 线的分段加载，向左浏览时自动补充更早历史。
- 支持逐根推进和自动播放；1h/4h 推进会按顺序处理全部底层 5m K 线。
- 支持逐仓杠杆、可配置 Maker/Taker 手续费、市价单、限价单、突破单、止盈止损和挂单撤销。
- 服务重启后可从本地数据库和离线缓存恢复活动训练状态。

### 图表与画线

- 基于 TradingView Lightweight Charts 的 K 线、成交量和技术指标视图。
- 支持 MACD、KDJ、RSI、BOLL 和自定义均线。
- 支持趋势线、水平线、射线、矩形、文本、斐波那契、量尺、做多和做空风险收益框。
- 绘图支持拖动预览、时间/价格磁吸、跨周期投影和锚点交互。
- 绘图只保留在当前训练运行态；结束、重置或新建训练后自动清除。
- 币圈工作区支持明暗主题、图表全屏、成交量/指标折叠和可调整交易台。

### 用户与复盘

- 多用户数据隔离。
- 保存账户、仓位、订单、成交、手续费、交易理由和训练报告。
- 可选 AI 复盘与策略测试；需要用户自行配置兼容的模型 API。

## 快速开始

### Windows 一键启动

1. 安装 Python 3.11 或 3.12。
2. 双击根目录的 `启动项目.bat`。
3. 首次运行会自动创建 `.venv` 并安装 `requirements.txt`。
4. 浏览器会自动打开本地地址。

启动脚本依次尝试端口 `8000`、`5000`、`5050`，并绑定到 `0.0.0.0`，方便同一局域网内访问。

### 手动启动

```powershell
cd E:\Desktop\01_TODO\mimo\KLinePlayground

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python -m flask --app backend.app_enhanced run --host 0.0.0.0 --port 8000
```

本机访问：

```text
http://127.0.0.1:8000/
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

## 局域网访问

服务启动后，查找当前电脑的 IPv4 地址：

```powershell
ipconfig
```

其他设备使用下面的格式访问：

```text
http://你的IPv4地址:8000/
```

例如：

```text
http://192.168.1.24:8000/
```

如果可以 `ping` 通但网页无法打开，请检查：

- Flask 是否监听 `0.0.0.0:8000`，而不是只监听 `127.0.0.1`。
- Windows 防火墙是否允许当前 Python 程序或 TCP 8000 入站。
- 浏览器或系统代理是否错误代理了局域网地址。
- 路由器是否启用了 AP 隔离或访客网络隔离。

## 数据与隐私

- 用户数据默认保存在本机 `users/`。
- 离线行情保存在本机 `data/`，币圈行情按数据源、合约、月份保存为压缩文件。
- `.runtime/`、本地用户、凭据和离线行情不应提交到 Git。
- 币圈历史准备任务只在内存中保留有限时间；已经下载的月度缓存可以重复使用。
- 训练图表只能看到当前回放时间及以前的数据，不会展示未来行情。

## 测试与质量检查

安装依赖后可执行：

```powershell
node --check frontend/js/main_enhanced.js
python -m compileall -q backend
python -m pytest -q
git diff --check
```

截至 2026 年 7 月 22 日，当前开发工作区完整测试基线为：

```text
717 passed, 71 subtests passed
```

## 项目结构

| 路径 | 说明 |
| --- | --- |
| `backend/app_enhanced.py` | Flask 主入口、训练 API 和运行态集成 |
| `backend/crypto/` | 币圈数据源、缓存、聚合、回放、订单和持久化 |
| `backend/intraday/` | A 股分钟级行情、聚合和回放能力 |
| `frontend/` | 页面、样式、图表、交易台和前端交互 |
| `tests/` | 后端、前端静态契约、交易规则和回归测试 |
| `.agent/` | 项目状态、架构说明、任务包、质量门禁和交接记录 |
| `AI_TAKEOVER.md` | 新 AI 接手项目的低上下文入口 |
| `启动项目.bat` | Windows 一键安装依赖并启动服务 |
| `requirements.txt` | 本地 Python 依赖 |
| `vercel.json` | Vercel 部署配置 |

## AI 协作与项目接手

项目包含文件化的 AI 协作控制面，不需要依赖长聊天记录恢复上下文。

- 接手入口：[`AI_TAKEOVER.md`](AI_TAKEOVER.md)
- 主 Agent 提示词：[`.agent/prompts/MAIN_AGENT_PROMPT.md`](.agent/prompts/MAIN_AGENT_PROMPT.md)
- WorkBuddy 任务模板：[`.agent/prompts/WORKBUDDY_TASK_PROMPT.md`](.agent/prompts/WORKBUDDY_TASK_PROMPT.md)
- 当前状态：[`.agent/STATE.md`](.agent/STATE.md)
- 质量门禁：[`.agent/QUALITY_GATES.md`](.agent/QUALITY_GATES.md)

新 AI 接手时必须保护现有未提交改动，并避免处理 `.runtime/`、用户数据、凭据和离线行情。

## 部署说明

本地 Windows 运行是完整功能的推荐方式，因为币圈多年行情和用户训练状态需要可持续的本地存储。

仓库包含 Vercel 配置，但无状态 Serverless 环境不适合直接保存大量离线行情。若部署到 Vercel，需要额外配置持久化用户存储、认证和外部行情数据策略；本地 `.runtime/`、`users/` 和 `data/` 不会自动同步到云端。

## 许可证与来源

项目使用 [MIT License](LICENSE)。本仓库基于原始 [KLinePlayground](https://github.com/fat7/KLinePlayground) 项目持续扩展，请同时遵守原项目许可证和第三方数据源的使用条款。

## 免责声明

本项目仅用于学习、研究和历史行情训练。行情数据可能存在延迟、缺失或来源差异，模拟结果不代表真实交易表现。

**投资有风险，交易需谨慎。**
