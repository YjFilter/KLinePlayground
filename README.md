# KLinePlayground 📈
### 专业级 A 股 & 币圈永续合约 K 线复盘与实战交易模拟平台 (Desktop & Web)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?style=flat-square&logo=python" alt="Python Version" />
  <img src="https://img.shields.io/badge/Frontend-TradingView%20Lightweight%20Charts%20v4-green?style=flat-square" alt="Charts" />
  <img src="https://img.shields.io/badge/Architecture-Desktop%20%7C%20Web%20Dual--Mode-purple?style=flat-square" alt="Architecture" />
  <img src="https://img.shields.io/badge/Tests-800%2B%20Passing-brightgreen?style=flat-square" alt="Tests" />
  <img src="https://img.shields.io/badge/License-MIT-orange?style=flat-square" alt="License" />
</p>

---

## 🌟 项目简介

**KLinePlayground** 是一款专为量化交易员、技术分析爱好者与个人投资者打造的**专业级、本地化 K 线复盘与裸 K 实战模拟训练平台**。

系统全面支持 **A 股实时看盘与历史复盘** 以及 **币圈 USDT 永续合约高精度拟真撮合**。交互与视觉深度对标 **AICoin** 与 **TradingView**，提供原生流畅的多周期无缝推演、图上拖拽挂单与止盈止损微调、全仓/逐仓高倍杠杆强平模拟、毫秒级 OHLC 极值磁吸画线分析、独立多副图自由分屏以及详尽的资金风控评测报告。

支持 **独立桌面原生客户端（PyWebView）** 与 **现代浏览器 Web 模式** 双模架构，开箱即用，数据完全本地持久化，安全私密。

> ⚠️ **声明**：本项目仅供个人编程学习、量化策略研究及历史行情模拟训练使用，不构成任何投资建议，亦不会连接任何真实资金账户进行实盘交易。市场有风险，投资需谨慎！

---

## ✨ 核心特性

### 1. 🪙 币圈 USDT 永续合约复盘（深度对标 AICoin / TradingView）
- **多数据源直连与本地智能离线缓存**：内置 Binance / Bybit USDT 永续合约行情拉取引擎，支持按月份分片下载、自动解压与本地紧凑缓存；
- **多年高频历史与分段回溯加载**：支持主流币种（BTC、ETH、SOL 等）`2 ~ 5 年` 超长历史数据，`1m`、`5m`、`15m`、`30m`、`1h`、`4h`、日线、周线全周期覆盖；向左拖拽图表自动分段补齐更早历史；
- **全仓（Cross Margin）与逐仓（Isolated）杠杆模拟**：
  - 支持 `1x ~ 100x` 自定义杠杆调节与双向持仓；
  - **真实全仓破产强平计算**：精准动态推导并绘制**主图专属红色强平爆仓线**（`💀 强平 (Liq): xxx [爆仓线]`）；
  - 价格触及强平线自动执行破产清算，精准模拟滑点与爆仓穿仓机制；
- **主图拖拽改单（Drag-to-Modify）**：
  - 止盈（TP）、止损（SL）、限价单（Limit）、突破触发单（Breakout）在主图均有专属交互价格线；
  - 直接在 K 线图上拖拉价格线即可修改挂单与止损，悬浮提示实时计算预期盈亏额与收益率（ROI）；
- **快捷仓位控制与分批平仓**：
  - 支持 `25%`、`50%`、`75%`、`全部` 快捷保证金/持仓比例一键填入；
  - 支持一键市价全平、分批限价平仓与保护性止损联动；
- **零未来数据泄露保障（No Future Data Leakage）**：
  - 严格限制图表与计算引擎只能获取当前回放时钟前的数据，确保复盘真实性。

---

### 2. 🇨🇳 A 股市场复盘 & 实时看盘系统
- **16 周期极速切换**：全面支持 `1分`、`5分`、`15分`、`30分`、`60分`、`120分`、`日K`、`周K`、`月K` 等 16 档周期即时切换；
- **自选股池管理（Watchlist）**：
  - 支持股票代码、名称智能拼音首字母模糊检索；
  - 一键加入/移除自选股，悬浮卡片展示自选标的实时价格与涨跌幅；
- **模拟持仓调账面板**：
  - 支持随时根据实盘情况或推演需求，自由调整账户现金余额、持仓股数与平均持仓成本；
- **A 股智能价格预警系统（Price Alerts）**：
  - 支持设置指定股票的“涨至”或“跌至”价格阈值；
  - 3 秒定时轮询并支持跳空穿透检测，触发时主图声光告警，自动归档触发历史；
- **真实 A 股撮合规则**：
  - 完整模拟 T+1 交易制度、涨跌停限制（主板 10%、科创/创业板 20%、ST 5%）、印花税、过户费及券商佣金扣除。

---

### 3. ✂️ K 线切片历史回放系统 (Bar Replay)
- **自由截断时间穿越**：激活剪刀裁切工具，在任意历史 K 线上点击，即可将时间倒流至该时刻；
- **多档播放速度调节**：支持从 0.5x、1x、2x 到 10x 倍速自动播放，亦支持手动单步推进（Step Forward）；
- **全周期时钟同步**：日线推进时自动驱动小周期多时钟对齐，随时暂停、重选裁切点或退出回放。

---

### 4. 📊 顶级多副图技术指标系统（零内存抖动与自适应量程）
- **多副图自由分屏（Multi-Subcharts）**：
  - 支持同时打开 `MACD`、`MACD2`、`KDJ`、`RSI` 等多种技术指标副图，各副图并存显示；
- **可拖拽高度调节（Splitter Resizing）**：
  - 副图之间提供平滑的拖拽分割线，支持自由调整各副图的高矮比例，并自动持久化到本地；
- **Series 零抖动复用机制（Zero-churn Reuse）**：
  - 高频单步推进时复用既有图表系列（`series.setData`），告别反复创建/销毁图表带来的内存泄露与界面闪烁；
- **价格轴自适应量程保障（AutoScale Guarantee）**：
  - 副图右侧价格轴实时自适应极值缩放，即使遇到行情断崖暴跌（如 MACD DIF 骤降至 -212 等极端负值），也能自适应延展量程，彻底杜绝曲线被画布下底边截断平躺失真的现象；
- **主图指标定制**：
  - 支持配置多周期移动平均线（MA 5/10/20/60/120/250）与布林带（BOLL）参数及颜色定制。

---

### 5. 🎨 专业矢量画线分析工具箱 (Vector Drawing Tools v2)
- **全套经典绘图工具**：
  - 趋势线（Trendline）、水平线（Horizontal）、水平射线（Ray）、连续折线（Polyline）；
  - 矩形区间（Rectangle）、价格/周期测量尺（Ruler）、文字标注（Text）、斐波那契回调线（Fibonacci Retracements）；
- **🧲 OHLC 极值强力磁吸（Magnetic Snap）**：
  - 光标靠近 K 线时毫秒级自动吸附开盘价（O）、最高价（H）、最低价（L）、收盘价（C），画线极度平整精确；
- **每种工具独立样式记忆（Per-tool Isolated Style）**：
  - 每种工具单独记忆颜色、线条粗细、线型（实线/虚线/点线）、填充透明度，避免不同工具之间相互污染样式；
- **图元锁定与一键隐藏**：
  - 锁定按钮（Lock）：防止复盘分析过程中误触拖拽或缩放关键画线；
  - 眼睛按钮（Hide）：支持选中单条画线隐藏，亦支持在左侧工具栏一键“隐藏所有画线 / 恢复显示所有画线”；
- **跨周期坐标自适应投影（Anchor Projection）**：
  - 在日线或高周期绘制的画线，切换至 120分、30分、5分周期时精准自适应对齐，拒绝跨屏乱线；
- **画线直连下单（Drawing-to-Order）**：
  - 选中水平线或趋势线，可在浮动工具栏一键将线位价格带入下单面板，实现“按线开仓”。

---

### 6. 🖥️ 桌面原生端与 Web 统一双模架构
- **基于 PyWebView 的原生独立客户端**：
  - 提供无边框/沉浸式独立应用窗体体验，无浏览器地址栏与快捷键干扰；
- **纯 Web 服务器模式**：
  - 原生标准 Flask API 后端，支持局域网设备（iPad、手机、同网笔记本）无缝跨端看盘。

---

## 🚀 快速开始

### 环境要求
- **Python**：3.11 或 3.12（推荐使用 Anaconda 或官方 Python）
- **Node.js**（可选，仅用于运行前端算法单元测试）：18.x 以上

---

### 方式一：Windows 一键快速启动（最推荐）

1. 双击仓库根目录下的 **`启动项目.bat`**；
2. 脚本将自动检测环境、初始化虚拟环境 `.venv`、安装所有依赖并唤起默认模式。

---

### 方式二：命令行启动

```powershell
# 1. 克隆仓库
git clone https://github.com/YjFilter/KLinePlayground.git
cd KLinePlayground

# 2. 创建并激活 Python 虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. 安装依赖包
pip install -r requirements.txt

# 4. 运行应用
# 【模式 A】启动独立桌面客户端 (推荐)
python main.py
# 或使用快捷入口: python run_desktop.py

# 【模式 B】启动纯 Web 服务模式
python main.py --mode web --port 5000
# 或使用快捷入口: python run_web.py
```

启动后在浏览器打开：
- 本机访问：[http://127.0.0.1:5000](http://127.0.0.1:5000)
- 健康检查：[http://127.0.0.1:5000/api/health](http://127.0.0.1:5000/api/health)

---

### 📱 局域网 / 多设备访问（iPad / 手机 / 异机电脑）

Web 服务启动时默认绑定 `0.0.0.0`，在同一局域网下的其他设备可通过本机 IPv4 地址直接访问：
```text
http://192.168.x.x:5000
```

---

## 📁 目录结构

```text
KLinePlayground/
├── backend/                       # 后端核心源码
│   ├── app_enhanced.py            # 主 API 服务入口与应用编排
│   ├── crypto/                    # 币圈永续合约引擎（回放、撮合、缓存、全仓强平计算）
│   ├── services/                  # A 股实时看盘与批量行情服务
│   ├── routes/                    # 分模块 REST API 路由 (A股、加密、状态)
│   ├── intraday/                  # 分时与分钟级 K 线聚合
│   └── data_manager.py            # A 股离线与在线数据源接入
├── desktop/                       # 桌面原生应用集成
│   └── desktop_app.py             # 基于 PyWebView 的桌面窗体管理器
├── frontend/                      # 前端交互与图表渲染
│   ├── index_enhanced.html        # 交易工作台主界面
│   ├── css/                       # 样式表与深浅色主题定义
│   └── js/
│       ├── main_enhanced.js       # 主控脚本：图表生命周期、多副图管理、挂单拖拽
│       ├── drawing_tools.js       # 矢量画线引擎：OHLC 磁吸、独立样式记忆、图元锁定
│       ├── indicator_math.js      # 本地纯 JS 技术指标计算引擎 (MACD/KDJ/RSI/BOLL)
│       └── modules/               # 功能模块 (A股交易、K线裁切回放、价格预警、时区转换)
├── scripts/                       # 运维与构建脚本
│   ├── build_desktop.py           # PyInstaller 独立打包构建脚本
│   └── create_desktop_shortcut.py # 创建桌面快捷方式工具
├── tests/                         # 自动化测试套件
│   ├── js/                        # 前端核心算法单元测试 (Node.js Test Runner)
│   └── test_*.py                  # Python 单元测试与端到端静态契约测试
├── data/                          # 历史 K 线离线数据与分片缓存
├── users/                         # 用户本地数据与复盘进度存档
├── requirements.txt               # Python 核心依赖清单
├── main.py                        # 统一启动入口（桌面/Web双模）
├── run_desktop.py                 # 桌面端快捷启动脚本
├── run_web.py                     # Web 端快捷启动脚本
└── 启动项目.bat                   # Windows 一键启动脚本
```

---

## 🧪 自动化测试与质量保障

项目拥有一套完备的自动化测试防护网，涵盖后端行情聚合、撮合引擎、全仓强平数学模型、画线坐标系映射与前端关键状态契约：

```powershell
# 1. 运行 Python 前端静态契约与核心逻辑测试套件 (250+ Tests)
python -m pytest tests/test_drawing_tools_frontend.py tests/test_chart_workspace_frontend.py tests/test_indicator_rebuild_and_drawing_persistence.py tests/test_ashare_holding_sync_and_drawing_settings.py tests/test_intraday_frontend_static.py tests/test_intraday_history_frontend_static.py tests/test_crypto_frontend_static.py tests/test_ashare_live_frontend_static.py tests/test_ashare_trade_markers_static.py tests/test_bar_replay_frontend_static.py tests/test_price_alerts_frontend_static.py tests/test_drawing_lock_binding_static.py

# 2. 运行 Node.js 算法单元测试套件 (80+ Tests)
node --test tests/js/*.test.js
```

---

## 🙏 致谢与开源传承 (Acknowledgments)

本项目最初基于开源项目 [fat7/KLinePlayground](https://github.com/fat7/KLinePlayground)（原作者：[@fat7](https://github.com/fat7)）进行深度重构、功能扩展与生态演进。在此向原作者的开源探索与基础架构工作致以诚挚的敬意与感谢！

---

## 📄 开源许可证 (License)

本项目遵循 [MIT License](LICENSE) 开源许可证。

---

## 💡 免责声明

本软件仅供个人编程学习、量化策略研究与历史复盘模拟使用。模拟交易中的收益表现不代表任何实盘投资回报。市场有风险，投资需谨慎！
