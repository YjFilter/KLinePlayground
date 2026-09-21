"""
KLinePlayground - State Synchronization Routes
提供桌面端与 Web 端多端状态（活动用户、A股模拟持仓账户、自选股列表、画图数据、界面布局）持久化与实时同步 API
"""
from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

state_bp = Blueprint('state', __name__, url_prefix='/api/state')

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
USERS_DIR = PROJECT_ROOT / "users"
SYNC_FILE = DATA_DIR / "app_sync_state.json"

DEFAULT_ASHARE_WATCHLIST = [
    {"code": "601727", "name": "上海电气", "symbol": "sh601727"},
    {"code": "002261", "name": "拓维信息", "symbol": "sz002261"},
    {"code": "600519", "name": "贵州茅台", "symbol": "sh600519"},
    {"code": "300750", "name": "宁德时代", "symbol": "sz300750"},
    {"code": "002594", "name": "比亚迪", "symbol": "sz002594"},
    {"code": "601318", "name": "中国平安", "symbol": "sh601318"},
    {"code": "300059", "name": "东方财富", "symbol": "sz300059"},
    {"code": "000001", "name": "平安银行", "symbol": "sz000001"},
    {"code": "600036", "name": "招商银行", "symbol": "sh600036"},
    {"code": "000858", "name": "五粮液", "symbol": "sz000858"},
]

DEFAULT_ASHARE_ACCOUNT = {
    "cash": 973589.73,
    "cash_frozen": 0.0,
    "positions": {
        "002261": {
            "total_shares": 1000,
            "frozen_today": 0,
            "frozen_sell": 0,
            "avg_cost": 25.08,
            "name": "拓维信息",
            "symbol": "sz002261"
        },
        "601727": {
            "total_shares": 200,
            "frozen_today": 0,
            "frozen_sell": 0,
            "avg_cost": 6.57,
            "name": "上海电气",
            "symbol": "sh601727"
        }
    },
    "trade_history": [
        {
            "time": "16:10:42",
            "date": "2026-09-16",
            "type": "买入",
            "symbol": "sz002261",
            "code": "002261",
            "name": "拓维信息",
            "lots": 10,
            "shares": 1000,
            "price": 25.08,
            "cost": 25080.0,
            "fee": 46.27,
            "note": "限价成交"
        },
        {
            "time": "13:28:00",
            "date": "2026-09-11",
            "type": "买入",
            "symbol": "sh601727",
            "code": "601727",
            "name": "上海电气",
            "lots": 1,
            "shares": 100,
            "price": 6.57,
            "cost": 657.0,
            "fee": 45.0,
            "note": "限价成交"
        },
        {
            "time": "13:27:54",
            "date": "2026-09-11",
            "type": "买入",
            "symbol": "sh601727",
            "code": "601727",
            "name": "上海电气",
            "lots": 1,
            "shares": 100,
            "price": 6.57,
            "cost": 657.0,
            "fee": 45.0,
            "note": "限价成交"
        }
    ],
    "pending_orders": [],
    "last_date": datetime.now().strftime("%Y-%m-%d")
}


def load_sync_state() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SYNC_FILE.exists():
        try:
            with open(SYNC_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                if isinstance(state, dict):
                    return state
        except Exception as e:
            logger.warning(f"读取全局同步状态失败: {e}")

    # 若未初始化，尝试从已有的 yj 用户或默认模板读取
    initial_state = {
        "active_user": "yj",
        "ashare_account": DEFAULT_ASHARE_ACCOUNT,
        "ashare_watchlist": DEFAULT_ASHARE_WATCHLIST,
        "drawings": {},
        "alerts": {},
        "crypto_console_layout": {"collapsed": False},
        "updated_at": datetime.now().isoformat()
    }
    save_sync_state(initial_state)
    return initial_state


def save_sync_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().isoformat()
    try:
        with open(SYNC_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        # 同时备份到对应用户的目录下
        active_user = state.get("active_user") or "yj"
        user_dir = USERS_DIR / active_user
        if user_dir.exists():
            user_backup = user_dir / "sync_state.json"
            with open(user_backup, "w", encoding="utf-8") as uf:
                json.dump(state, uf, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存同步状态异常: {e}")


@state_bp.route('/sync', methods=['GET'])
def get_state():
    """获取最新同步状态"""
    state = load_sync_state()
    return jsonify({
        "status": "ok",
        **state
    })


@state_bp.route('/sync', methods=['POST'])
def update_state():
    """更新同步状态（支持增量合并）"""
    payload = request.get_json(silent=True) or {}
    state = load_sync_state()

    for key in ["active_user", "ashare_account", "ashare_watchlist", "drawings", "alerts", "crypto_console_layout"]:
        if key in payload and payload[key] is not None:
            if isinstance(payload[key], dict) and isinstance(state.get(key), dict) and key in ["drawings", "alerts"]:
                state[key].update(payload[key])
            else:
                state[key] = payload[key]

    save_sync_state(state)
    return jsonify({"status": "ok", "updated_at": state.get("updated_at")})
