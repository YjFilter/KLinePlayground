from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import json
import base64
import random
import requests
from datetime import datetime, timedelta
import sqlite3
import pandas as pd
import numpy as np

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.data_manager import DataManager
from backend.kline_processor_enhanced import KLineProcessorEnhanced
from backend.market_rules import get_limit_status, is_buy_blocked, is_sell_blocked
from backend.order_manager import PendingOrderManager
from backend.trade_simulator_enhanced import TradeSimulatorEnhanced
from backend.user_manager_enhanced import UserManagerEnhanced

# 配置Flask以提供静态文件，支持开发环境和 PyInstaller 打包环境
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # 打包后环境
    frontend_folder = os.path.join(sys._MEIPASS, 'frontend')
else:
    # 开发环境
    frontend_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

app = Flask(__name__, static_folder=frontend_folder, static_url_path='/')
CORS(app)  # 允许跨域请求

# 获取项目根目录，确保路径在项目内
if getattr(sys, 'frozen', False):
    # project_root = os.path.dirname(sys.executable)
    project_root = os.path.join(os.path.dirname(sys.executable), '..')
else:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
users_dir_path = os.path.join(project_root, 'users')
data_dir_path = os.path.join(project_root, 'data')

# 初始化管理器
data_manager = DataManager(data_dir=data_dir_path)
# user_manager = UserManager()
user_manager = UserManagerEnhanced(users_dir=users_dir_path)
active_trainings = {}  # 存储活跃的训练会话

# ----------------------------------------------------------------------
# Intraday replay 数据模式与周期常量
# ----------------------------------------------------------------------
# legacy_daily: 旧日线训练路径，未传 data_mode 时的默认行为，保持完全兼容
# intraday_30m: 基于 30 分钟底层行情的多周期回放路径
DATA_MODE_LEGACY_DAILY = "legacy_daily"
DATA_MODE_INTRADAY_30M = "intraday_30m"
# intraday_30m 支持的四个显示周期
VALID_INTRADAY_PERIODS = ("30m", "4h_session", "daily", "weekly")
# 懒加载的 IntradayDataService 单例；legacy_daily 路径不会触发其创建，
# 因此旧用户不会因缺少 baostock 等可选依赖而受影响。
_intraday_service_instance = None


def _get_intraday_data_service():
    """懒加载 IntradayDataService。

    legacy_daily 路径不会调用此函数，避免在旧环境中引入 baostock 等依赖。
    测试可通过直接覆盖 ``app_enhanced._intraday_service_instance`` 或
    patch 本函数来注入 mock 服务，禁止访问真实 BaoStock 网络。
    """
    global _intraday_service_instance
    if _intraday_service_instance is None:
        from backend.intraday.baostock_source import BaoStockSource
        from backend.intraday.cache import IntradayCache
        from backend.intraday.service import IntradayDataService

        cache_root = os.path.join(data_dir_path, 'intraday')
        _intraday_service_instance = IntradayDataService(
            source=BaoStockSource(),
            cache=IntradayCache(root=cache_root),
        )
    return _intraday_service_instance


def _get_chart_window_service():
    from backend.intraday.chart_window import ChartWindowService

    return ChartWindowService(_get_intraday_data_service())


def _intraday_candidate_provider(sector, date_start, date_end):
    service = _get_intraday_data_service()
    cache = getattr(service, 'cache', None)
    data_dir = getattr(cache, 'data_dir', None)
    if data_dir and os.path.isdir(data_dir):
        cached_codes = sorted({
            os.path.splitext(filename)[0]
            for filename in os.listdir(data_dir)
            if filename.endswith('.csv')
            and os.path.splitext(filename)[0].isdigit()
            and len(os.path.splitext(filename)[0]) == 6
        })
        cached_codes = data_manager._filter_stock_codes_by_sector(cached_codes, sector)
        if cached_codes:
            return random.choice(cached_codes)

    stock_code, _ = data_manager.get_random_stock(
        sector,
        date_start,
        date_end,
        source='akshare',
        interval='daily',
    )
    return stock_code


def _get_intraday_random_selector():
    from backend.intraday.random_selector import IntradayRandomSelector

    return IntradayRandomSelector(
        candidate_provider=_intraday_candidate_provider,
        data_service=_get_intraday_data_service(),
    )


def _parse_datetime_arg(name):
    value = request.args.get(name)
    if not value:
        raise ValueError(f'缺少 {name} 参数')
    return datetime.fromisoformat(value)


def _format_datetime(value):
    return pd.Timestamp(value).to_pydatetime().isoformat(sep=' ')


def _chart_window_payload(result, training):
    payload = result.to_dict()
    payload.update({
        'stock_code': training['stock_code'],
        'training_start': training['training_start'],
        'training_end': training.get('training_end'),
    })
    return payload


def _trade_markers(trades):
    markers = []
    for trade in trades or []:
        timestamp = trade.get('trade_time') or trade.get('trade_date')
        if not timestamp:
            continue
        is_buy = trade.get('action') == 'buy'
        markers.append({
            'time': timestamp,
            'type': 'B' if is_buy else 'S',
            'price': float(trade.get('price', 0) or 0),
            'text': '买入' if is_buy else '卖出',
        })
    return markers


def _legacy_history_chart_payload(report, period, range_start, range_end):
    frame = data_manager.get_stock_data(
        report['stock_code'],
        source=report.get('data_source', 'akshare'),
        interval=period,
    )
    if frame is None or frame.empty:
        rows = pd.DataFrame()
    else:
        rows = frame.copy()
        time_column = next(
            (name for name in ('date', 'datetime', 'trade_date') if name in rows.columns),
            None,
        )
        if time_column is None:
            rows = rows.reset_index().rename(columns={rows.index.name or 'index': 'date'})
            time_column = 'date'
        rows[time_column] = pd.to_datetime(rows[time_column], errors='coerce')
        rows = rows.loc[
            rows[time_column].notna()
            & (rows[time_column] >= pd.Timestamp(range_start))
            & (rows[time_column] <= pd.Timestamp(range_end))
        ].sort_values(time_column)

    kline_data = []
    volume_data = []
    for _, row in rows.iterrows():
        timestamp = _format_datetime(row[time_column])
        bar = {
            'period': period,
            'start_time': timestamp,
            'end_time': timestamp,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(row.get('volume', 0) or 0),
            'amount': float(row.get('amount', 0) or 0),
            'source_bar_count': 1,
            'complete': True,
        }
        kline_data.append(bar)
        volume_data.append({
            'time': timestamp,
            'value': bar['volume'],
            'color': '#ff4d4f' if bar['close'] >= bar['open'] else '#008000',
        })

    return {
        'stock_code': report['stock_code'],
        'period': period,
        'window_start': _format_datetime(range_start),
        'window_end': _format_datetime(range_end),
        'kline_data': kline_data,
        'volume_data': volume_data,
        'has_earlier': False,
        'has_later': False,
        'read_only': True,
        'training_start': report['training_start'],
        'training_end': report['training_end'],
        'trade_markers': _trade_markers(report.get('trade_details')),
    }


def _resolve_data_mode(data_mode, period):
    """根据显式 data_mode 和 period 解析最终数据模式。

    优先级：
    1. 显式 ``data_mode == "intraday_30m"`` → intraday_30m
    2. 显式 ``data_mode == "legacy_daily"`` → legacy_daily
    3. 未传 data_mode → legacy_daily（保持旧行为）
    """
    if data_mode in (None, ""):
        return DATA_MODE_LEGACY_DAILY
    if data_mode == DATA_MODE_INTRADAY_30M:
        return DATA_MODE_INTRADAY_30M
    if data_mode == DATA_MODE_LEGACY_DAILY:
        return DATA_MODE_LEGACY_DAILY
    raise ValueError(f'不支持的数据模式: {data_mode}')


def _parse_start_date(start_date_str):
    """将 'YYYY-MM-DD' 解析为当日 00:00:00 的 datetime 对象。"""
    return datetime.strptime(start_date_str, '%Y-%m-%d')


def _choose_initial_time(base_bars, start_dt):
    """选择 base_bars 中第一根 datetime >= start_dt 的 timestamp。

    若 start_dt 之后无数据或 base_bars 为空则抛出 ValueError。
    """
    if base_bars is None or base_bars.empty:
        raise ValueError("intraday base_bars 为空，无法启动回放")
    ts = pd.Timestamp(start_dt)
    mask = base_bars["datetime"] >= ts
    if mask.any():
        return base_bars.loc[mask, "datetime"].iloc[0].to_pydatetime()
    raise ValueError("起始日期之后没有可用的 intraday 数据")


def _intraday_snapshot_response(training):
    """构造 intraday 会话的完整响应：snapshot + 元数据字段。"""
    session = training['intraday_session']
    snap = session.snapshot()
    snap['data_mode'] = training['data_mode']
    snap['stock_code'] = training['stock_code']
    snap['mode'] = training.get('mode', '')
    snap['data_source'] = training.get('data_source', 'akshare')
    snap['initial_capital'] = training.get('initial_capital', 0)
    return snap


def _is_intraday_session(training):
    """判断 training 是否为 intraday_30m 模式。"""
    return training.get('data_mode') == DATA_MODE_INTRADAY_30M


def _intraday_current_trade_date(training):
    """返回 intraday 会话当前 base bar 的交易日字符串 (YYYY-MM-DD)。"""
    session = training['intraday_session']
    snap = session.snapshot()
    current_time_str = snap.get('current_time', '')
    if not current_time_str:
        return ''
    try:
        return datetime.strptime(current_time_str, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
    except ValueError:
        return current_time_str[:10]


def _intraday_current_trade_time(training):
    """返回 intraday 会话当前 base bar 的完整时间字符串 (YYYY-MM-DD HH:MM:SS)。"""
    session = training['intraday_session']
    snap = session.snapshot()
    return snap.get('current_time', '')


def _parse_optional_price(value):
    if value in (None, "", 0, "0"):
        return None
    price = float(value)
    if price <= 0:
        return None
    return price


def _execute_simulated_trade(training, action, quantity, price, trade_date, reason=''):
    trade_simulator = training['trade_simulator']
    kline_processor = training['kline_processor']
    result = trade_simulator.buy(quantity, price, trade_date, reason=reason) if action == 'buy' else trade_simulator.sell(quantity, price, trade_date, reason=reason)
    if result.get('success'):
        kline_processor.add_trade_marker(action, price)
    return result


def _process_pending_orders(training):
    order_manager = training.get('order_manager')
    if not order_manager:
        return []

    kline_processor = training['kline_processor']
    current_bar = kline_processor.get_current_bar()
    current_date = kline_processor.get_current_date()
    prev_close = kline_processor.get_previous_close()
    stock_code = training.get('stock_code', '')

    return order_manager.process_bar(
        bar=current_bar,
        prev_close=prev_close,
        stock_code=stock_code,
        trade_date=current_date,
        execute_buy=lambda quantity, price, order: _execute_simulated_trade(training, 'buy', quantity, price, current_date, order.get('reason', '')),
        execute_sell=lambda quantity, price, order: _execute_simulated_trade(training, 'sell', quantity, price, current_date, order.get('reason', '')),
    )


def _pending_orders_payload(training):
    order_manager = training.get('order_manager')
    return order_manager.to_dict() if order_manager else {'buy_orders': [], 'exit_orders': []}


@app.route('/')
def index():
    """提供前端入口页面"""
    return app.send_static_file('index_enhanced.html')


@app.route('/api/users', methods=['GET'])
def get_users():
    """获取用户列表"""
    try:
        users = user_manager.get_users()
        return jsonify(users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['POST'])
def create_user():
    """创建新用户"""
    try:
        data = request.get_json()
        username = data.get('username')
        
        if not username:
            return jsonify({'error': '用户名不能为空'}), 400
        
        if user_manager.user_exists(username):
            return jsonify({'error': '用户名已存在'}), 400
        
        user_manager.create_user(username)
        return jsonify({'message': '用户创建成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/users/<username>', methods=['DELETE'])
def delete_user(username):
    """删除用户及其所有数据"""
    try:
        if not user_manager.user_exists(username):
            return jsonify({'error': '用户不存在'}), 404

        if user_manager.delete_user(username):
            return jsonify({'message': '用户删除成功'})
        else:
            return jsonify({'error': '删除用户失败'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<username>/settings', methods=['GET'])
def get_user_settings(username):
    """获取用户设置"""
    try:
        config = user_manager.get_user_config(username)
        if config:
            return jsonify(config.get('settings', {}))
        else:
            return jsonify({'error': '用户不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<username>/settings', methods=['POST'])
def update_user_settings(username):
    """更新用户设置"""
    try:
        data = request.get_json()
        config = user_manager.get_user_config(username)
        
        if not config:
            # 如果配置不存在，先创建默认配置，防止老用户数据丢失或缺失 config.json 导致无法保存
            user_manager.create_user(username)
            config = user_manager.get_user_config(username)
            if not config:
                return jsonify({'error': '用户不存在且创建配置失败'}), 404
        
        if 'settings' not in config:
            config['settings'] = {}
            
        # 更新设置
        config['settings'].update(data)
        
        if user_manager.update_user_config(username, config):
            return jsonify({'message': '设置更新成功'})
        else:
            return jsonify({'error': '设置更新失败'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<username>/statistics', methods=['GET'])
def get_user_statistics(username):
    """获取用户统计信息"""
    try:
        stats = user_manager.get_user_statistics(username)
        if stats:
            return jsonify(stats)
        else:
            return jsonify({'error': '用户不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<username>/history', methods=['GET'])
def get_user_training_history(username):
    try:
        limit = int(request.args.get('limit', 50))
        return jsonify(user_manager.get_training_history(username, limit))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<username>/history/<session_id>', methods=['GET'])
def get_user_history_report(username, session_id):
    try:
        report = user_manager.get_session_report(username, session_id)
        if not report:
            return jsonify({'error': '历史训练不存在'}), 404
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/users/<username>/history/<session_id>/chart', methods=['GET'])
def get_user_history_chart(username, session_id):
    try:
        report = user_manager.get_session_report(username, session_id)
        if not report:
            return jsonify({'error': '历史训练不存在'}), 404

        report = dict(report)
        training_start = report.get('training_start') or report.get('start_date')
        training_end = report.get('training_end') or report.get('end_date')
        if training_start:
            report['training_start'] = _format_datetime(training_start)
        if training_end:
            report['training_end'] = _format_datetime(training_end)

        required = ('stock_code', 'training_start', 'training_end')
        missing = [name for name in required if not report.get(name)]
        if missing:
            return jsonify({
                'error': f"缺少走势图重建元数据: {', '.join(missing)}",
            }), 400

        period = request.args.get('period', report.get('period', 'daily'))
        range_start = _parse_datetime_arg('range_start')
        range_end = _parse_datetime_arg('range_end')
        if range_start > range_end:
            return jsonify({'error': 'range_start 不能晚于 range_end'}), 400

        if report.get('data_mode', DATA_MODE_LEGACY_DAILY) != DATA_MODE_INTRADAY_30M:
            return jsonify(_legacy_history_chart_payload(
                report,
                period,
                range_start,
                range_end,
            ))

        result = _get_chart_window_service().load(
            stock_code=report['stock_code'],
            period=period,
            range_start=range_start,
            range_end=range_end,
            current_time=datetime.fromisoformat(report['training_end']),
            read_only=True,
        )
        payload = _chart_window_payload(result, report)
        payload['trade_markers'] = _trade_markers(report.get('trade_details'))
        return jsonify(payload)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<username>/history/<session_id>', methods=['DELETE'])
def delete_user_history_report(username, session_id):
    try:
        if user_manager.delete_training_session(username, session_id):
            return jsonify({'success': True})
        return jsonify({'error': '历史训练不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<username>/history/<session_id>/summary', methods=['POST'])
def save_user_history_summary(username, session_id):
    try:
        data = request.get_json() or {}
        summary = (data.get('summary') or '').strip()
        if user_manager.save_review_summary(username, session_id, summary):
            report = user_manager.get_session_report(username, session_id)
            return jsonify({'success': True, 'review_summary': summary, 'report': report})
        return jsonify({'error': '历史训练不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _update_api_info(user=None, enable=None):
    """更新或删除 api_info.json"""
    if getattr(sys, 'frozen', False):
        api_file_path = os.path.join(os.path.dirname(sys.executable), '..', 'data', 'ai_api_info.json')
    else:
        api_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'ai_api_info.json')
    
    if enable is None and user:
        user_config = user_manager.get_user_config(user)
        if user_config and 'settings' in user_config:
            enable = user_config['settings'].get('enable_ai_api', False)
        else:
            enable = False
            
    if not enable:
        if os.path.exists(api_file_path):
            try:
                os.remove(api_file_path)
            except Exception:
                pass
        return

    # 尝试获取base_url，如果不在请求上下文中可能为空
    try:
        base_url = request.host_url.rstrip('/') + "/api"
    except Exception:
        base_url = ""

    info = {
        "api_base_url": base_url,
        "active_trainings": list(active_trainings.keys()),
        "current_user": user,
        "endpoints": {
            "start_training": "POST /api/training/start",
            "next_bar": "POST /api/training/{training_id}/next",
            "execute_trade": "POST /api/training/{training_id}/trade",
            "adjustment": "POST /api/training/{training_id}/adjustment",
            "get_data": "GET /api/training/{training_id}/data",
            "get_account": "GET /api/training/{training_id}/account",
            "end_training": "POST /api/training/{training_id}/end"
        },
        "updated_at": datetime.now().isoformat()
    }
    
    try:
        with open(api_file_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"写入 ai_api_info.json 失败: {e}")

def get_ai_config():
    if getattr(sys, 'frozen', False):
        config_file = os.path.join(os.path.dirname(sys.executable), '..', 'data', '.ai_tester_config.enc')
    else:
        config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', '.ai_tester_config.enc')
        
    if not os.path.exists(config_file):
        return None
    try:
        with open(config_file, 'r') as f:
            obfs = f.read().strip()
        if not obfs: return None
        key = "kline_trainer_secret_key"
        json_str = "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(base64.b64decode(obfs).decode('utf-8')))
        return json.loads(json_str)
    except Exception as e:
        print(f"Failed to load AI config: {e}")
        return None

def analyze_report_with_ai(report):
    ai_config = get_ai_config()
    if not ai_config:
        return "AI 配置未找到，请在 AI 测试器中配置。"
    
    base_url = ai_config.get("base_url", "https://api.openai.com/v1").rstrip('/')
    api_key = ai_config.get("api_key", "")
    model = ai_config.get("model", "gpt-3.5-turbo")
    
    if not api_key:
        return "AI API Key 未配置，无法进行分析。"
    
    prompt = f"""
请作为一位资深的股票交易教练，对以下A股K线训练的回放复盘报告进行分析、点评和评分（百分制）。

【训练基本信息】
- 股票代码: {report.get('stock_code')}
- 训练期间: {report.get('start_date')} 至 {report.get('end_date')}
- 初始资金: {report.get('initial_capital')}
- 最终资金: {report.get('final_capital')}
- 总收益率: {report.get('total_return')}%
- 最大回撤: {report.get('max_drawdown', 0)}%
- 总交易次数: {report.get('total_trades')}
- 交易胜率: {report.get('trade_win_rate')}%

【交易明细】
"""
    for t in report.get('trade_details', [])[:150]:
        prompt += f"- {t.get('date')} {t.get('action')} {t.get('quantity')}手 @ {t.get('price')} (Bar: {t.get('bar_id')})\n"
        
    prompt += "\n请给出专业的点评（包括优点、不足和改进建议），并在最后给出一个综合评分（0-100分）。要求语言简练、直击要害。"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位专业的量化和主观交易教练，擅长通过交易记录分析交易者的心理和策略问题。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            return f"AI API请求失败: {response.status_code} {response.text}"
    except Exception as e:
        return f"AI 分析请求发生错误: {str(e)}"


@app.route('/api/system/api_info', methods=['POST', 'DELETE'])
def toggle_api_info():
    """手动切开/关 API暴露"""
    try:
        if request.method == 'POST':
            data = request.get_json() or {}
            user = data.get('user', None)
            _update_api_info(user=user, enable=True)
            return jsonify({'message': 'API info exposed'})
        else:
            _update_api_info(enable=False)
            return jsonify({'message': 'API info hidden'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _start_intraday_training(
    user,
    mode,
    data_source,
    period,
    initial_capital,
    training_id,
    payload,
    max_training_days,
):
    """启动 intraday_30m 训练会话。

    通过 IntradayDataService 加载 30 分钟底座数据，选择 start_date 当天或之后的
    第一根真实时间戳作为 initial_time，创建 IntradayReplaySession。

    返回包含完整 session snapshot 和 data_mode 的响应。
    """
    from backend.intraday.session import IntradayReplaySession
    from backend.intraday.trading_context import build_previous_close_index
    from backend.intraday.training_window import build_training_window

    try:
        if mode == 'random':
            selection = _get_intraday_random_selector().select(
                sector=payload.get('sector', 'all'),
                date_start=payload.get('date_start', '2024-01-01'),
                date_end=payload.get('date_end', '2026-01-01'),
                max_training_days=max_training_days,
            )
            stock_code = selection.stock_code
            initial_time = selection.start_time
            context_start = selection.context_start
            market_bars = selection.base_bars
            start_date = initial_time.strftime('%Y-%m-%d')
        else:
            stock_code = payload.get('stock_code')
            start_date = payload.get('start_date')
            if not stock_code or not start_date:
                return jsonify({'error': '股票代码和起始日期不能为空'}), 400
            try:
                start_dt = _parse_start_date(start_date)
            except ValueError:
                return jsonify({'error': f'起始日期格式错误: {start_date}'}), 400
            context_start = (pd.Timestamp(start_dt) - pd.DateOffset(years=2)).to_pydatetime()
            market_bars = _get_intraday_data_service().get_30m(
                stock_code,
                context_start,
                datetime.now(),
            )
            initial_time = _choose_initial_time(market_bars, start_dt)

        window = build_training_window(market_bars, initial_time, max_training_days)
    except Exception as e:
        return jsonify({'error': f'intraday 数据加载失败: {e}'}), 400

    trade_simulator = TradeSimulatorEnhanced(user, initial_capital, stock_code)
    trade_simulator.session_id = training_id
    order_manager = PendingOrderManager()

    # 应用用户佣金设置
    user_config = user_manager.get_user_config(user)
    if user_config and 'settings' in user_config:
        settings = user_config['settings']
        trade_simulator.set_commission_settings(
            settings.get('commission_rate', 0.0003),
            settings.get('min_commission', 5.0),
            settings.get('stamp_tax_rate', 0.001)
        )

    session = IntradayReplaySession(
        base_bars=window.replay_bars,
        initial_time=initial_time,
        stock_code=stock_code,
        simulator=trade_simulator,
        order_manager=order_manager,
        initial_period=period,
    )
    previous_close_index = build_previous_close_index(market_bars)
    initial_bar_id = int(
        market_bars.index[market_bars['datetime'] == pd.Timestamp(initial_time)][0]
    ) + 1

    # 初始化交易模拟器的当前价格 (用首根 base bar 的 close)
    snap = session.snapshot()
    current_base_bar = snap.get('current_base_bar')
    if current_base_bar:
        trade_simulator.update_current_price(current_base_bar['close'], initial_bar_id)

    active_trainings[training_id] = {
        'user': user,
        'stock_code': stock_code,
        'start_date': start_date,
        'trade_simulator': trade_simulator,
        'order_manager': order_manager,
        'mode': mode,
        'data_source': data_source,
        'period': period,
        'data_mode': DATA_MODE_INTRADAY_30M,
        'intraday_session': session,
        'previous_close_index': previous_close_index,
        'initial_bar_id': initial_bar_id,
        'initial_capital': initial_capital,
        'base_interval': '30m',
        'max_training_days': max_training_days,
        'training_start': _format_datetime(initial_time),
        'training_end': _format_datetime(window.cutoff_time),
        'created_at': datetime.now(),
    }

    user_manager.start_training_session(user, {
        'session_id': training_id,
        'stock_code': stock_code,
        'stock_name': data_manager.get_stock_name(stock_code),
        'start_date': start_date,
        'mode': mode,
        'initial_capital': initial_capital,
        'data_mode': DATA_MODE_INTRADAY_30M,
        'base_interval': '30m',
        'period': period,
        'training_start': _format_datetime(initial_time),
        'training_end': _format_datetime(window.cutoff_time),
        'max_training_days': max_training_days,
        'commission_settings': {
            'commission_rate': trade_simulator.commission_rate,
            'min_commission': trade_simulator.min_commission,
            'stamp_tax_rate': trade_simulator.stamp_tax_rate,
        }
    })

    _update_api_info(user=user)

    response = _intraday_snapshot_response(active_trainings[training_id])
    response['id'] = training_id
    response['training_start'] = _format_datetime(initial_time)
    response['training_end'] = _format_datetime(window.cutoff_time)
    response['max_training_days'] = max_training_days
    try:
        context_result = _get_chart_window_service().load(
            stock_code=stock_code,
            period=period,
            range_start=context_start,
            range_end=initial_time,
            current_time=initial_time,
            read_only=False,
        )
        response['context_kline_data'] = context_result.kline_data
        response['context_volume_data'] = context_result.volume_data
        response['window_start'] = _format_datetime(context_result.window_start)
        response['window_end'] = _format_datetime(context_result.window_end)
        response['has_earlier'] = context_result.has_earlier
    except TypeError:
        response['context_kline_data'] = response['kline_data']
        response['context_volume_data'] = []
        response['window_start'] = _format_datetime(context_start)
        response['window_end'] = _format_datetime(initial_time)
        response['has_earlier'] = False
    response['has_later'] = False
    return jsonify(response)


def _intraday_next(training, training_id):
    """intraday_30m 推进到下一个周期边界。

    调用 ``session.advance()``，返回 snapshot + order_events + completed_times。
    若回放已结束，生成报告并标记会话为 completed。
    """
    session = training['intraday_session']
    trade_simulator = training['trade_simulator']
    order_manager = training['order_manager']

    result = session.advance()
    finished = result.get('finished', False)
    order_events = result.get('order_events', [])
    completed_times = result.get('completed_times', [])

    # session.advance() 已按顺序更新每根隐藏 base bar 的价格与 bar_id。
    snap = session.snapshot()

    if finished:
        trade_simulator.session_id = training_id
        current_date = _intraday_current_trade_date(training)
        report = trade_simulator.generate_report(
            training['stock_code'],
            training['start_date'],
            current_date,
        )
        report['session_id'] = training_id
        report['data_mode'] = DATA_MODE_INTRADAY_30M
        _save_intraday_session_report(training, training_id, report, status='completed')
        return jsonify({
            'finished': True,
            'data_mode': DATA_MODE_INTRADAY_30M,
            'report': report,
        })

    pending_payload = order_manager.to_dict() if order_manager else {'buy_orders': [], 'exit_orders': []}
    return jsonify({
        'finished': False,
        'data_mode': DATA_MODE_INTRADAY_30M,
        'snapshot': snap,
        'order_events': order_events,
        'completed_times': completed_times,
        'pending_orders': pending_payload,
    })


def _intraday_get_data(training):
    """intraday_30m 获取当前数据快照，不推进回放状态。"""
    snap = _intraday_snapshot_response(training)
    return jsonify(snap)


def _intraday_set_period(training, period):
    """intraday_30m 切换显示周期，不推进时间，返回重新聚合后的快照。"""
    if period not in VALID_INTRADAY_PERIODS:
        return jsonify({'error': f'不支持的周期: {period}'}), 400
    session = training['intraday_session']
    try:
        session.set_period(period)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    # set_period 后 training['period'] 也同步更新，便于后续路由感知
    training['period'] = period
    response = _intraday_snapshot_response(training)
    return jsonify(response)


def _get_intraday_previous_close(training):
    """获取 intraday 会话用于涨跌停判断的上一交易日收盘价。

    手动交易与自动订单推进共用上一有效交易日收盘价规则。
    """
    session = training['intraday_session']
    snap = session.snapshot()
    current_time = snap.get('current_time')
    previous_closes = training.get('previous_close_index')
    if not current_time or previous_closes is None:
        return None
    return previous_closes.previous_close(datetime.fromisoformat(current_time))


def _intraday_trade(training, data):
    """intraday_30m 手动交易。

    成交价使用当前 base bar 的 close，保存完整的 trade_time 和 display_period，
    以支持分钟级回放的同日多次独立成交。
    """
    action = data.get('action')
    quantity = data.get('quantity')
    order_type = data.get('order_type', 'market')
    trigger_price = _parse_optional_price(data.get('trigger_price'))
    take_profit_price = _parse_optional_price(data.get('take_profit_price'))
    stop_loss_price = _parse_optional_price(data.get('stop_loss_price'))
    reason = (data.get('reason') or '').strip()
    quantity = int(quantity) if quantity else 0

    if not action or not quantity:
        return jsonify({'error': '交易参数不完整'}), 400

    session = training['intraday_session']
    trade_simulator = training['trade_simulator']
    order_manager = training['order_manager']

    snap = session.snapshot()
    current_base_bar = snap.get('current_base_bar')
    if not current_base_bar:
        return jsonify({'error': '当前无可用 base bar，无法交易'}), 400

    current_price = current_base_bar['close']
    trade_date = _intraday_current_trade_date(training)
    trade_time = _intraday_current_trade_time(training)
    display_period = snap.get('active_period', '')
    stock_code = training['stock_code']

    # 挂单逻辑 (与 legacy 类似，但使用 intraday 的当前价格)
    if action == 'buy' and order_type in {'limit', 'breakout'}:
        if trigger_price is None:
            return jsonify({'error': '请填写有效触发价'}), 400
        order = order_manager.add_buy_order(
            order_type=order_type,
            quantity=quantity,
            trigger_price=trigger_price,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            reason=reason,
        )
        return jsonify({
            'success': True,
            'pending': True,
            'order': order,
            'pending_orders': order_manager.to_dict(),
        })

    if order_type != 'market':
        return jsonify({'error': '卖出只支持市价单，止盈止损请在买入时设置'}), 400

    # 涨跌停检测 (后端兜底)
    prev_close = _get_intraday_previous_close(training)
    if prev_close and prev_close > 0:
        limit_pct = 0.10
        if stock_code.startswith(('30', '68')):
            limit_pct = 0.20
        elif stock_code.startswith(('43', '83', '87', '92')):
            limit_pct = 0.30
        threshold = prev_close * 0.001
        limit_up = prev_close * (1 + limit_pct)
        limit_down = prev_close * (1 - limit_pct)
        if action == 'buy' and current_price >= limit_up - threshold:
            return jsonify({'error': f'当前涨停（涨停价 {limit_up:.2f}），无法买入'}), 400
        if action == 'sell' and current_price <= limit_down + threshold:
            return jsonify({'error': f'当前跌停（跌停价 {limit_down:.2f}），无法卖出'}), 400

    if action == 'buy':
        result = trade_simulator.buy(
            quantity, current_price, trade_date,
            reason=reason, trade_time=trade_time, display_period=display_period,
        )
    elif action == 'sell':
        result = trade_simulator.sell(
            quantity, current_price, trade_date,
            reason=reason, trade_time=trade_time, display_period=display_period,
        )
    else:
        return jsonify({'error': '无效的交易操作'}), 400

    if result['success']:
        if action == 'buy' and (take_profit_price or stop_loss_price):
            order_manager.add_bracket_orders(quantity, take_profit_price, stop_loss_price, base_reason=reason)
        return jsonify({
            'success': True,
            'trade': result['trade'],
            'pending_orders': order_manager.to_dict(),
            'data_mode': DATA_MODE_INTRADAY_30M,
        })
    return jsonify({'error': result['message']}), 400


def _intraday_account(training):
    """intraday_30m 账户信息，附带当前 intraday 快照关键字段。"""
    trade_simulator = training['trade_simulator']
    order_manager = training['order_manager']
    current_date = _intraday_current_trade_date(training)
    account_info = trade_simulator.get_account_info(current_date)
    account_info['pending_orders'] = order_manager.to_dict() if order_manager else {'buy_orders': [], 'exit_orders': []}
    account_info['data_mode'] = DATA_MODE_INTRADAY_30M
    # 附带当前 intraday 快照关键字段，便于前端显示
    snap = training['intraday_session'].snapshot()
    account_info['current_time'] = snap.get('current_time')
    account_info['active_period'] = snap.get('active_period')
    account_info['next_boundary'] = snap.get('next_boundary')
    account_info['finished'] = snap.get('finished', False)
    return jsonify(account_info)


def _intraday_reset(training):
    """intraday_30m 重置: 恢复初始时间和周期，重置交易模拟器和挂单。

    注意: ``session.reset()`` 不替换 simulator/order_manager，仅恢复 replay clock；
    交易模拟器和挂单管理器需要单独调用 ``reset()``/``clear()``。
    """
    session = training['intraday_session']
    trade_simulator = training['trade_simulator']
    order_manager = training['order_manager']
    session.reset()
    trade_simulator.reset()
    if order_manager:
        order_manager.clear()
    # 重置后更新当前价格
    snap = session.snapshot()
    current_base_bar = snap.get('current_base_bar')
    if current_base_bar:
        trade_simulator.update_current_price(current_base_bar['close'], training['initial_bar_id'])
    return jsonify({
        'message': '训练已重置',
        'data_mode': DATA_MODE_INTRADAY_30M,
        'snapshot': snap,
    })


def _intraday_end(training, training_id):
    """intraday_30m 结束训练: 生成报告并标记会话为 ended。"""
    trade_simulator = training['trade_simulator']
    trade_simulator.session_id = training_id
    current_date = _intraday_current_trade_date(training)
    report = trade_simulator.generate_report(
        training['stock_code'],
        training['start_date'],
        current_date,
    )
    report['session_id'] = training_id
    report['data_mode'] = DATA_MODE_INTRADAY_30M
    _save_intraday_session_report(training, training_id, report, status='ended')
    active_trainings[training_id]['status'] = 'ended'
    _update_api_info(user=training['user'])
    return jsonify(report)


def _save_intraday_session_report(training, training_id, report, status):
    """保存 intraday 会话报告到用户历史。"""
    current_time = _intraday_current_trade_time(training)
    training['training_end'] = current_time
    report.update({
        'data_mode': DATA_MODE_INTRADAY_30M,
        'base_interval': '30m',
        'period': training.get('period', '30m'),
        'training_start': training['training_start'],
        'training_end': current_time,
        'max_training_days': training.get('max_training_days', 0),
        'stock_code': training['stock_code'],
        'data_source': training.get('data_source', 'akshare'),
    })
    session_data = {
        'session_id': training_id,
        'stock_code': training['stock_code'],
        'stock_name': data_manager.get_stock_name(training['stock_code']),
        'start_date': training['start_date'],
        'end_date': _intraday_current_trade_date(training),
        'mode': training.get('mode', ''),
        'data_mode': DATA_MODE_INTRADAY_30M,
        'base_interval': '30m',
        'period': training.get('period', ''),
        'training_start': training['training_start'],
        'training_end': current_time,
        'max_training_days': training.get('max_training_days', 0),
        'data_source': training.get('data_source', 'akshare'),
        'initial_capital': report['initial_capital'],
        'final_capital': report['final_capital'],
        'total_return': report['total_return'],
        'total_trades': report['total_trades'],
        'trade_win_rate': report['trade_win_rate'],
        'session_win_rate': report['session_win_rate'],
        'report_data': report,
        'review_summary': report.get('review_summary', ''),
        'status': status,
    }
    user_manager.save_training_session(training['user'], session_data)


@app.route('/api/training/start', methods=['POST'])
def start_training():
    """开始新的训练"""
    try:
        data = request.get_json()
        user = data.get('user')
        mode = data.get('mode')
        data_source = data.get('data_source', 'akshare')
        period = data.get('period', 'daily')
        initial_capital = data.get('initial_capital', 100000)
        max_bars = data.get('max_bars', 0) or 0
        max_training_days = int(data.get('max_training_days', max_bars) or 0)

        if max_training_days < 0:
            return jsonify({'error': '训练交易日限制不能为负数'}), 400

        if not user:
            return jsonify({'error': '用户名不能为空'}), 400

        # 新增: 可选 data_mode 参数 ('legacy_daily' | 'intraday_30m')
        # 未传时保持 legacy_daily；intraday 必须显式声明。
        data_mode = data.get('data_mode')
        resolved_data_mode = _resolve_data_mode(data_mode, period)

        # 仅 intraday_30m 模式强制校验 period；legacy_daily 保持原有宽容行为
        if resolved_data_mode == DATA_MODE_INTRADAY_30M and period not in VALID_INTRADAY_PERIODS:
            return jsonify({'error': f'不支持的 intraday 周期: {period}'}), 400

        # 创建训练会话
        training_id = f"{user}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # === intraday_30m 分支: 基于 30 分钟底座的多周期回放 ===
        if resolved_data_mode == DATA_MODE_INTRADAY_30M:
            return _start_intraday_training(
                user=user,
                mode=mode,
                data_source=data_source,
                period=period,
                initial_capital=initial_capital,
                training_id=training_id,
                payload=data,
                max_training_days=max_training_days,
            )

        # === legacy_daily 分支 (保持原有行为完全不变) ===
        if mode == 'random':
            # 随机模式
            sector = data.get('sector', 'all')
            date_start = data.get('date_start', '2024-01-01')
            date_end = data.get('date_end', '2026-01-01')
            try:
                stock_code, start_date = data_manager.get_random_stock(
                    sector,
                    date_start,
                    date_end,
                    source=data_source,
                    interval=period,
                )
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
        else:
            # 指定模式
            stock_code = data.get('stock_code')
            start_date = data.get('start_date')
            
            if not stock_code or not start_date:
                return jsonify({'error': '股票代码和起始日期不能为空'}), 400
        
        # 验证股票代码和日期
        validation_error = data_manager.get_training_validation_error(
            stock_code,
            start_date,
            source=data_source,
            interval=period,
        )
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # 创建增强版K线处理器和交易模拟器
        kline_processor = KLineProcessorEnhanced(data_manager, stock_code, start_date, source=data_source, interval=period, max_training_bars=max_bars)
        trade_simulator = TradeSimulatorEnhanced(user, initial_capital, stock_code)
        trade_simulator.session_id = training_id
        
        # 获取用户设置并应用到交易模拟器
        user_config = user_manager.get_user_config(user)
        if user_config and 'settings' in user_config:
            settings = user_config['settings']
            trade_simulator.set_commission_settings(
                settings.get('commission_rate', 0.0003),
                settings.get('min_commission', 5.0),
                settings.get('stamp_tax_rate', 0.001)
            )
        
        # 存储训练会话
        active_trainings[training_id] = {
            'user': user,
            'stock_code': stock_code,
            'start_date': start_date,
            'kline_processor': kline_processor,
            'trade_simulator': trade_simulator,
            'order_manager': PendingOrderManager(),
            'mode': mode,
            'data_source': data_source,
            'period': period,
            'data_mode': DATA_MODE_LEGACY_DAILY,
            'created_at': datetime.now()
        }
        user_manager.start_training_session(user, {
            'session_id': training_id,
            'stock_code': stock_code,
            'stock_name': data_manager.get_stock_name(stock_code),
            'start_date': start_date,
            'mode': mode,
            'initial_capital': initial_capital,
            'commission_settings': {
                'commission_rate': trade_simulator.commission_rate,
                'min_commission': trade_simulator.min_commission,
                'stamp_tax_rate': trade_simulator.stamp_tax_rate,
            }
        })
        
        _update_api_info(user=user)
        
        return jsonify({
            'id': training_id,
            'stock_code': stock_code,
            'start_date': start_date,
            'mode': mode,
            'data_source': data_source,
            'period': period
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/data', methods=['GET'])
def get_training_data(training_id):
    """获取训练数据"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404

        training = active_trainings[training_id]

        # === intraday_30m 分支: 返回当前快照，不推进回放状态 ===
        if _is_intraday_session(training):
            return _intraday_get_data(training)

        # === legacy_daily 分支 (原逻辑) ===
        kline_processor = training['kline_processor']
        view_period = request.args.get('view_period', 'daily')

        # 获取当前可见的K线数据
        kline_data = kline_processor.get_visible_data(view_period=view_period)
        volume_data = kline_processor.get_volume_data(view_period=view_period)
        
        # 获取均线周期参数
        ma_periods_str = request.args.get('ma_periods', '5,10,20')
        try:
            ma_periods = [int(p) for p in ma_periods_str.split(',') if p.strip()]
        except ValueError:
            ma_periods = [5, 10, 20]
            
        ma_data = kline_processor.get_ma_data(ma_periods, view_period=view_period)
        
        # 获取股票名称
        stock_name = data_manager.get_stock_name(training['stock_code'])
        
        # 获取进度信息
        progress = kline_processor.get_progress()
        
        return jsonify({
            'stock_name': stock_name,
            'kline_data': kline_data,
            'volume_data': volume_data,
            'ma_data': ma_data,
            'progress': progress,
            'trade_markers': kline_processor.get_trade_markers() if view_period == 'daily' else [],
            'period': training.get('period', 'daily'),
            'view_period': view_period,
            'data_source': training.get('data_source', 'akshare')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/next', methods=['POST'])
def next_bar(training_id):
    """获取下一根K线"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404

        training = active_trainings[training_id]

        # === intraday_30m 分支: 按活动周期边界推进，返回 ordered events ===
        if _is_intraday_session(training):
            return _intraday_next(training, training_id)

        # === legacy_daily 分支 (原逻辑) ===
        kline_processor = training['kline_processor']
        trade_simulator = training['trade_simulator']

        # 推进到下一根K线
        has_next = kline_processor.next_bar()
        
        if not has_next:
            # 训练结束，生成报告
            trade_simulator.session_id = training_id
            report = trade_simulator.generate_report(
                training['stock_code'],
                training['start_date'],
                kline_processor.get_current_date()
            )
            report["session_id"] = training_id
            
            # 保存训练记录
            session_data = {
                'session_id': training_id,
                'stock_code': training['stock_code'],
                'stock_name': data_manager.get_stock_name(training['stock_code']),
                'start_date': training['start_date'],
                'end_date': kline_processor.get_current_date(),
                'mode': training['mode'],
                'initial_capital': report['initial_capital'],
                'final_capital': report['final_capital'],
                'total_return': report['total_return'],
                'total_trades': report['total_trades'],
                'trade_win_rate': report['trade_win_rate'],
                'session_win_rate': report['session_win_rate'],
                'report_data': report,
                'review_summary': report.get('review_summary', ''),
                'status': 'completed'
            }
            user_manager.save_training_session(training['user'], session_data)
            
            return jsonify({
                'finished': True,
                'report': report
            })
        
        # 更新交易模拟器的当前价格和bar ID
        current_bar = kline_processor.get_current_bar()
        trade_simulator.update_current_price(current_bar['close'], current_bar['bar_id'])
        order_events = _process_pending_orders(training)

        current_bar['lastClose'] = kline_processor.get_previous_close()

        res = {
            'finished': False,
            'new_bar': current_bar,
            'new_volume': kline_processor.get_current_volume(),
            'progress': kline_processor.get_progress(),
            'order_events': order_events,
            'pending_orders': _pending_orders_payload(training),
            'trade_markers': kline_processor.get_trade_markers(),
            'requires_full_refresh': getattr(kline_processor, 'factor_changed', False)
        }

        color = '#000000'
        if res['new_bar']['close'] > res['new_bar']['open']:
            color = '#ff4d4f'
        elif res['new_bar']['close'] < res['new_bar']['open']:
            color = '#008000'  # 红涨绿跌

        res['new_volume']['color'] = color

        return jsonify(res)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/period', methods=['POST'])
def switch_period(training_id):
    """切换 intraday_30m 会话的显示周期，不推进时间，返回重新聚合后的快照。"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404

        training = active_trainings[training_id]
        if not _is_intraday_session(training):
            return jsonify({'error': '该会话不支持周期切换 (仅 intraday_30m 模式)'}), 400

        data = request.get_json() or {}
        period = data.get('period')
        if not period:
            return jsonify({'error': '缺少 period 参数'}), 400
        return _intraday_set_period(training, period)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/<training_id>/chart-window', methods=['GET'])
def get_training_chart_window(training_id):
    try:
        training = active_trainings.get(training_id)
        if not training:
            return jsonify({'error': '训练会话不存在'}), 404
        if not _is_intraday_session(training):
            return jsonify({'error': '该会话不支持分钟级上下文窗口'}), 400

        snapshot = training['intraday_session'].snapshot()
        result = _get_chart_window_service().load(
            stock_code=training['stock_code'],
            period=request.args.get('period', snapshot['active_period']),
            range_start=_parse_datetime_arg('range_start'),
            range_end=_parse_datetime_arg('range_end'),
            current_time=datetime.fromisoformat(snapshot['current_time']),
            read_only=False,
        )
        payload = _chart_window_payload(result, training)
        payload['trade_markers'] = _trade_markers(
            training['trade_simulator'].trade_history
        )
        return jsonify(payload)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/adjustment', methods=['POST'])
def update_adjustment(training_id):
    """更新复权设置"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        data = request.get_json()
        adjustment = data.get('adjustment', 'none')
        view_period = request.args.get('view_period', 'daily')
        
        training = active_trainings[training_id]
        kline_processor = training['kline_processor']
        
        # 更新复权设置
        kline_processor.set_adjustment(adjustment)
        
        # 获取均线周期参数
        ma_periods_str = request.args.get('ma_periods', '5,10,20')
        try:
            ma_periods = [int(p) for p in ma_periods_str.split(',') if p.strip()]
        except ValueError:
            ma_periods = [5, 10, 20]
            
        # 重新获取数据
        kline_data = kline_processor.get_visible_data(view_period=view_period)
        volume_data = kline_processor.get_volume_data(view_period=view_period)
        ma_data = kline_processor.get_ma_data(ma_periods, view_period=view_period)
        
        return jsonify({
            'kline_data': kline_data,
            'volume_data': volume_data,
            'ma_data': ma_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/full_data', methods=['GET'])
def get_full_data(training_id):
    """获取完整的K线数据和指标数据"""
    try:
        if training_id not in active_trainings:
            # 如果训练已结束且不在 active_trainings 中，尝试从历史记录重建所需的数据（这需要一些额外逻辑，目前先返回明确错误）
            # 或者我们可以考虑在 end_training 时不立即删除，而是标记为 ended，由客户端稍后清理
            return jsonify({'error': '训练会话已结束或不存在，无法获取完整走势'}), 404
        
        training = active_trainings[training_id]
        kline_processor = training['kline_processor']
        view_period = request.args.get('view_period', 'daily')
        
        kline_data = kline_processor.get_full_data(view_period=view_period)
        
        # 获取均线周期参数
        ma_periods_str = request.args.get('ma_periods', '5,10,20')
        try:
            ma_periods = [int(p) for p in ma_periods_str.split(',') if p.strip()]
        except ValueError:
            ma_periods = [5, 10, 20]
            
        # We also need volume data for the full range
        volume_data = []
        ma_data = {p: [] for p in ma_periods}
        
        # Save current state
        original_index = kline_processor.current_index
        
        # Set to max to calculate everything
        kline_processor.current_index = kline_processor.max_index
        
        try:
            volume_data = kline_processor.get_volume_data(view_period=view_period)
            ma_data = kline_processor.get_ma_data(ma_periods, view_period=view_period)
        finally:
            # Restore state
            kline_processor.current_index = original_index
            
        return jsonify({
            'kline_data': kline_data,
            'volume_data': volume_data,
            'ma_data': ma_data,
            'trade_markers': kline_processor.get_trade_markers() if view_period == 'daily' else [],
            'period': training.get('period', 'daily'),
            'view_period': view_period,
            'data_source': training.get('data_source', 'akshare')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/trade', methods=['POST'])
def execute_trade(training_id):
    """执行交易"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        data = request.get_json()
        training = active_trainings[training_id]

        # === intraday_30m 分支: 使用当前 base bar 的 close，保存完整 time/display period ===
        if _is_intraday_session(training):
            return _intraday_trade(training, data)

        # === legacy_daily 分支 (原逻辑) ===
        action = data.get('action')  # 'buy' or 'sell'
        quantity = data.get('quantity')
        price_type = data.get('price_type', 'close')
        order_type = data.get('order_type', 'market')
        trigger_price = _parse_optional_price(data.get('trigger_price'))
        take_profit_price = _parse_optional_price(data.get('take_profit_price'))
        stop_loss_price = _parse_optional_price(data.get('stop_loss_price'))
        reason = (data.get('reason') or '').strip()
        quantity = int(quantity) if quantity else 0

        if not action or not quantity:
            return jsonify({'error': '交易参数不完整'}), 400

        trade_simulator = training['trade_simulator']
        kline_processor = training['kline_processor']
        
        # 获取当前价格
        current_bar = kline_processor.get_current_bar()
        current_price = current_bar['open'] if price_type == 'open' else current_bar['close']
        current_date = kline_processor.get_current_date()
        prev_close = kline_processor.get_previous_close()
        stock_code = training.get('stock_code', '')
        order_manager = training.get('order_manager')

        if action == 'buy' and order_type in {'limit', 'breakout'}:
            if trigger_price is None:
                return jsonify({'error': '请填写有效触发价'}), 400
            order = order_manager.add_buy_order(
                order_type=order_type,
                quantity=quantity,
                trigger_price=trigger_price,
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price,
                reason=reason,
            )
            return jsonify({
                'success': True,
                'pending': True,
                'order': order,
                'pending_orders': _pending_orders_payload(training)
            })

        if order_type != 'market':
            return jsonify({'error': '卖出只支持市价单，止盈止损请在买入时设置'}), 400

        # 涨停/跌停检测（后端兜底）
        prev_close = kline_processor.get_previous_close()
        if prev_close and prev_close > 0:
            stock_code = training.get('stock_code', '')
            limit_pct = 0.10
            if stock_code.startswith(('30', '68')):
                limit_pct = 0.20
            elif stock_code.startswith(('43', '83', '87', '92')):
                limit_pct = 0.30

            threshold = prev_close * 0.001
            limit_up = prev_close * (1 + limit_pct)
            limit_down = prev_close * (1 - limit_pct)

            if action == 'buy' and current_price >= limit_up - threshold:
                return jsonify({'error': f'当前涨停（涨停价 {limit_up:.2f}），无法买入'}), 400
            if action == 'sell' and current_price <= limit_down + threshold:
                return jsonify({'error': f'当前跌停（跌停价 {limit_down:.2f}），无法卖出'}), 400

        # 执行交易
        if action == 'buy':
            result = _execute_simulated_trade(training, 'buy', quantity, current_price, current_date, reason)
        elif action == 'sell':
            result = _execute_simulated_trade(training, 'sell', quantity, current_price, current_date, reason)
        else:
            return jsonify({'error': '无效的交易操作'}), 400
        
        if result['success']:
            # 添加交易标记到K线图
            if action == 'buy' and (take_profit_price or stop_loss_price):
                order_manager.add_bracket_orders(quantity, take_profit_price, stop_loss_price, base_reason=reason)
            
            return jsonify({
                'success': True,
                'trade': result['trade'],
                'trade_markers': kline_processor.get_trade_markers(),
                'pending_orders': _pending_orders_payload(training)
            })
        else:
            return jsonify({'error': result['message']}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/account', methods=['GET'])
def get_account_info(training_id):
    """获取账户信息"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404

        training = active_trainings[training_id]

        # === intraday_30m 分支: 返回兼容账户信息 + intraday 快照字段 ===
        if _is_intraday_session(training):
            return _intraday_account(training)

        # === legacy_daily 分支 (原逻辑) ===
        trade_simulator = training['trade_simulator']

        current_date = training['kline_processor'].get_current_date()

        account_info = trade_simulator.get_account_info(current_date)
        account_info['pending_orders'] = _pending_orders_payload(training)
        return jsonify(account_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/<training_id>/orders', methods=['GET'])
def get_pending_orders(training_id):
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        return jsonify(_pending_orders_payload(active_trainings[training_id]))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/<training_id>/orders/<int:order_id>', methods=['DELETE'])
def cancel_pending_order(training_id, order_id):
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        order_manager = active_trainings[training_id].get('order_manager')
        if not order_manager or not order_manager.cancel_order(order_id):
            return jsonify({'error': '挂单不存在或已结束'}), 404
        return jsonify({
            'success': True,
            'pending_orders': _pending_orders_payload(active_trainings[training_id])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/trade_records', methods=['GET'])
def get_trade_records(training_id):
    """获取最新交易记录明细"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        trade_simulator = training['trade_simulator']
        
        records = trade_simulator.get_trade_history_with_bar_id()
        return jsonify(records)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/indicators/<indicator_type>', methods=['GET'])
def get_technical_indicators(training_id, indicator_type):
    """获取技术指标数据"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        kline_processor = training['kline_processor']
        view_period = request.args.get('view_period', 'daily')
        
        # 获取用户自定义的技术指标参数
        user = training['user']
        user_config = user_manager.get_user_config(user)
        kwargs = {}
        if user_config and 'settings' in user_config and 'indicators' in user_config['settings']:
            ind_settings = user_config['settings']['indicators']
            ind_type_lower = indicator_type.lower()
            if ind_type_lower in ind_settings:
                kwargs = ind_settings[ind_type_lower]
                
        indicators = kline_processor.get_technical_indicators(indicator_type.upper(), view_period=view_period, **kwargs)
        return jsonify(indicators)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/sync_status', methods=['GET'])
def get_sync_status(training_id):
    """获取精简同步状态"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        kline_processor = training['kline_processor']
        
        return jsonify({
            'current_bar_id': kline_processor.get_current_bar_id(),
            'trade_markers_count': len(kline_processor.get_trade_markers())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/end', methods=['POST'])
def end_training(training_id):
    """结束训练"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404

        training = active_trainings[training_id]

        # === intraday_30m 分支 ===
        if _is_intraday_session(training):
            return _intraday_end(training, training_id)

        # === legacy_daily 分支 (原逻辑) ===
        trade_simulator = training['trade_simulator']
        kline_processor = training['kline_processor']

        # Inject session_id into trade_simulator before generating report
        trade_simulator.session_id = training_id

        # 生成报告
        report = trade_simulator.generate_report(
            training['stock_code'],
            training['start_date'],
            kline_processor.get_current_date()
        )
        report["session_id"] = training_id
        
        # 保存训练记录
        session_data = {
            'session_id': training_id,
            'stock_code': training['stock_code'],
            'stock_name': data_manager.get_stock_name(training['stock_code']),
            'start_date': training['start_date'],
            'end_date': kline_processor.get_current_date(),
            'mode': training['mode'],
            'initial_capital': report['initial_capital'],
            'final_capital': report['final_capital'],
            'total_return': report['total_return'],
            'total_trades': report['total_trades'],
            'trade_win_rate': report['trade_win_rate'],
            'session_win_rate': report['session_win_rate'],
            'report_data': report,
            'review_summary': report.get('review_summary', ''),
            'status': 'ended'
        }
        user_manager.save_training_session(training['user'], session_data)
        
        # 清理训练会话
        # del active_trainings[training_id] # 不要立即删除，因为客户端可能还需要请求 full_data
        active_trainings[training_id]['status'] = 'ended'
        
        _update_api_info(user=training['user'])
        
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/cleanup', methods=['POST'])
def cleanup_training(training_id):
    """清理已结束的训练会话"""
    try:
        if training_id in active_trainings:
            del active_trainings[training_id]
        return jsonify({'message': '清理成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/reset', methods=['POST'])
def reset_training(training_id):
    """重置训练"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404

        training = active_trainings[training_id]

        # === intraday_30m 分支 ===
        if _is_intraday_session(training):
            return _intraday_reset(training)

        # === legacy_daily 分支 (原逻辑) ===
        # 重置K线处理器
        training['kline_processor'].reset()

        # 重置交易模拟器
        training['trade_simulator'].reset()
        if training.get('order_manager'):
            training['order_manager'].clear()

        return jsonify({'message': '训练已重置'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/history', methods=['GET'])
def get_training_history(training_id):
    """获取训练历史记录"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        trade_simulator = training['trade_simulator']
        kline_processor = training['kline_processor']
        
        # 获取交易历史（包含bar ID）
        trade_history = trade_simulator.get_trade_history_with_bar_id()
        
        # 获取每个bar的账户状态历史
        progress = kline_processor.get_progress()
        
        return jsonify({
            'trade_history': trade_history,
            'progress': progress,
            'trade_markers': kline_processor.get_trade_markers()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/chip_distribution', methods=['GET'])
def get_chip_distribution(training_id):
    """获取筹码分布（换手率衰减模型）"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
            
        kline_processor = active_trainings[training_id]['kline_processor']
        view_period = request.args.get('view_period', 'daily')
        
        # 可选增加 bins 参数，如果前端要求更精细的分布
        bins = int(request.args.get('bins', 80))
        chip_dist = kline_processor.get_volume_profile(bins=bins, view_period=view_period)
        
        return jsonify(chip_dist)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data/sources', methods=['GET'])
def get_data_sources():
    """返回可选数据源与可用性。"""
    try:
        return jsonify({'sources': data_manager.get_available_sources()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data/stock_universe', methods=['GET'])
def get_stock_universe():
    """按市场返回股票代码列表，供批量补数使用。"""
    try:
        market = request.args.get('market', 'all')
        stock_codes = data_manager.get_stock_universe(market=market)
        return jsonify({
            'market': market,
            'count': len(stock_codes),
            'stock_codes': stock_codes
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data/sync', methods=['POST'])
def sync_offline_data():
    """使用在线数据源增量补充离线数据。"""
    try:
        data = request.get_json() or {}
        stock_code = (data.get('stock_code') or '').strip()
        source = data.get('source', 'akshare')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        force_full = bool(data.get('force_full', False))

        if not stock_code:
            return jsonify({'error': '股票代码不能为空'}), 400
        if source == 'offline':
            return jsonify({'error': '请先选择在线数据源'}), 400

        result = data_manager.sync_offline_data(
            stock_code=stock_code,
            source=source,
            start_date=start_date,
            end_date=end_date,
            force_full=force_full,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/analyze_report', methods=['POST'])
def analyze_report():
    """使用AI分析复盘报告"""
    try:
        data = request.get_json()
        report = data.get('report')
        user = data.get('user')
        
        if not report or not user:
            return jsonify({'error': '缺少必要的参数'}), 400
            
        user_config = user_manager.get_user_config(user)
        if not user_config or not user_config.get('settings', {}).get('enable_ai_api', False):
            return jsonify({'error': '未开启AI分析功能'}), 403
            
        ai_commentary = analyze_report_with_ai(report)
        return jsonify({'ai_commentary': ai_commentary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'active_trainings': len(active_trainings)
    })

if __name__ == '__main__':
    # 确保数据目录存在
    os.makedirs('../data', exist_ok=True)
    os.makedirs('../users', exist_ok=True)
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=True)
