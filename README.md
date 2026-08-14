# KLinePlayground 📈
### 专业级 A 股 & 币圈永续合约 K 线复盘与交易模拟训练平台

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?style=flat-square&logo=python" alt="Python Version" />
  <img src="https://img.shields.io/badge/Frontend-TradingView%20Lightweight%20Charts-green?style=flat-square" alt="Charts" />
  <img src="https://img.shields.io/badge/Tests-783%20passed-brightgreen?style=flat-square" alt="Tests" />
  <img src="https://img.shields.io/badge/License-MIT-orange?style=flat-square" alt="License" />
</p>

---

## 🌟 项目简介

**KLinePlayground** 是一款专为交易员与个人投资者打造的**本地化、专业级 K 线复盘与裸 K 策略模拟训练工具**。

系统全面支持 **A 股** 与 **币圈 USDT 永续合约**，深度还原真实交易环境与撮合规则。界面交互对标 **AICoin** 与 **TradingView**，提供流畅的多周期行情回放、主图拖动挂单与改单、全仓/逐仓杠杆模拟、毫秒级磁吸画线分析、多维度资金风控以及详尽的复盘评估报告。

> ⚠️ **声明**：本项目仅用于个人学习、策略研究及历史行情模拟训练，不构成任何投资建议，亦不会连接真实资金账户执行实盘交易。

---

## ✨ 核心特性

### 1. 🪙 币圈 USDT 永续合约复盘（深度对标 AICoin / TradingView）
- **多数据源直连与离线缓存**：内置 Binance / Bybit USDT 永续合约行情引擎，支持按月自动下载并持久化压缩至本地缓存；
- **海量高频历史与分段加载**：支持 `2 ~ 5 年` 超长历史数据，`5m`、`15m`、`30m`、`1h`、`4h`、日线、周线全周期覆盖；向左拖拽图表自动分段补齐更早历史；
- **全仓（Cross Margin）与杠杆模拟**：
  - 支持 `1x ~ 100x` 自定义杠杆；
  - 真实全仓破产强平计算：精准绘制 **主图专属红色强平爆仓线**（`💀 强平 (Liq): xxx [爆仓线]`）；
  - 价格触及强平线自动执行破产清算，账户资产真实归零；
- **主图拖动改单（Drag-to-Modify）**：
  - 止盈（TP）、止损（SL）、限价单（Limit）、突破单（Breakout）在主图上均有专属价格线；
  - 直接在 K 线图上拖动价格线即可修改挂单与止损，悬浮提示实时计算预期盈亏与收益率；
- **分批平仓与快捷仓位控制**：
  - 支持 `25%`、`50%`、`75%`、`全部` 快捷保证金/持仓比例一键填入；
  - 支持一键市价全平、以损定仓与保护性止盈止损联动；
- **分钟级高精度时间轴**：底部时间轴与十字光标胶囊精确显示 `YYYY-MM-DD HH:mm`（如 `2024-07-01 19:30`）。

### 2. 🇨🇳 A 股市场复盘
- **多种训练模式**：支持指定股票代码训练与盲盒随机选股盲测模式；
- **多周期复盘**：支持 30 分钟、4 小时、日线与周线；
- **真实 A 股交易规则**：模拟 T+1 交易制度、涨跌停限制、印花税/佣金手续费及可用资金划转；
- **灵活交易委托**：市价单、限价单、条件突破单与持仓止盈止损；
- **数据源生态**：兼容 AKShare、BaoStock、mootdx 等主流 A 股数据接口。

### 3. 🎨 专业画线分析工具箱与磁吸模式
- **丰富工具集合**：趋势线、水平射线、水平线、矩形区域、文本标注、斐波那契回撤、价格测量尺、做多/做空风险收益比（RR）测算框；
- **🧲 OHLC 四价强力磁吸（Magnetic Snap）**：画线时自动高灵敏捕捉光标附近的开盘价（O）、最高价（H）、最低价（L）、收盘价（C），画线极度精准；
- **跨周期自动投影**：在高周期绘制的趋势线或支撑阻力位，切换到小周期自动对齐投影；
- **沉浸式工作区**：支持明亮/暗黑主题切换、图表全屏、成交量/副图指标高度自由拖拽拉伸。

### 4. 📊 复盘分析与多用户管理
- **多用户本地隔离**：支持多账户切换，独立保存各自的训练进度、交易记录与分析报告；
- **详尽统计指标**：自动生成资产净值曲线、累计收益率、最大回撤（MDD）、胜率、盈亏比、平均持仓时间；
- **AI 智能复盘助手**：支持接入兼容的 LLM 模型 API，基于全量成交流水对交易心理与策略执行进行智能复盘诊断。

---

## 🚀 快速启动

### 方式一：Windows 一键启动（推荐）

1. 确保电脑已安装 **Python 3.11** 或 **3.12**；
2. 双击运行根目录下的 **`启动项目.bat`**；
3. 脚本会自动初始化虚拟环境 `.venv`、安装依赖并启动服务，自动唤起浏览器打开应用。

---

### 方式二：命令行手动启动

```powershell
# 1. 克隆代码仓库
git clone https://github.com/YjFilter/KLinePlayground.git
cd KLinePlayground

# 2. 创建并激活 Python 虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. 安装依赖包
pip install -r requirements.txt

# 4. 启动 Flask 后端服务
python -m flask --app backend.app_enhanced run --host 0.0.0.0 --port 5000
```

打开浏览器访问：
- **本机访问**：[http://127.0.0.1:5000](http://127.0.0.1:5000)
- **健康检查接口**：[http://127.0.0.1:5000/api/health](http://127.0.0.1:5000/api/health)

---

### 📱 局域网/多设备访问（手机/平板/同网电脑）

服务默认监听 `0.0.0.0`，在同一局域网下的其他设备（如 iPad、手机）可通过本机局域网 IP 访问：

1. 在终端运行 `ipconfig` 查看本机 IPv4 地址（例如 `192.168.1.100`）；
2. 在同一 WiFi 下的设备浏览器中打开：
   ```text
   http://192.168.1.100:5000
   ```

---

## 📁 目录结构

```text
KLinePlayground/
├── backend/                  # 后端核心源码
│   ├── app_enhanced.py       # Flask API 主入口与训练生命周期管理
│   ├── crypto/               # 币圈永续合约引擎（回放、撮合、缓存、全仓强平）
│   ├── intraday/             # 分钟级行情聚合与分段回放流
│   └── ...
├── frontend/                 # 前端界面与可视化
│   ├── index_enhanced.html   # 主交互界面
│   ├── css/                  # 现代化 UI 样式与主题配置
│   └── js/
│       ├── main_enhanced.js  # 图表生命周期、挂单拖拽与交易交互
│       ├── drawing_tools.js  # 矢量画线工具箱与 OHLC 磁吸算法
│       └── risk_calc.js      # 风险收益与仓位计算器
├── tests/                    # 完整单元测试与端到端回归测试套件
├── users/                    # 用户数据与复盘历史（本地存储）
├── data/                     # 历史 K 线离线缓存数据
├── requirements.txt          # Python 依赖清单
└── 启动项目.bat              # Windows 一键启动脚本
```

---

## 🧪 自动化测试与质量保障

项目配备了完善的回归测试套件，涵盖后端撮合逻辑、全仓强平计算、分批平仓算法及前端契约：

```powershell
# 运行全量测试套件
pytest -q
```

**当前测试基线**：
```text
783 passed, 89 subtests passed (100% 全绿)
```

---

## 📄 许可证 (License)

本项目采用 [MIT License](LICENSE) 开源许可证。

---

## 💡 免责声明

本软件仅供个人编程学习、量化策略研究与历史复盘模拟使用。模拟交易中的收益表现不代表任何实盘投资回报。市场有风险，投资需谨慎！
