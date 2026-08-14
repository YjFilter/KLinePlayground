from flask import Flask, Response, request, jsonify
from flask_cors import CORS
import hmac
import os
import sys
import json
import base64
import random
import traceback
import requests
from threading import Lock, Timer
from datetime import datetime, timedelta, timezone
import sqlite3
import pandas as pd
import numpy as np

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.data_manager import DataManager
from backend.cloud_state import CloudStateError, CloudUserArchiveStore
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
is_vercel_runtime = bool(os.environ.get('VERCEL'))
users_dir_path = os.environ.get(
    'KLINE_USERS_DIR',
    os.path.join('/tmp', 'kline-playground', 'users') if is_vercel_runtime else os.path.join(project_root, 'users'),
)
data_dir_path = os.path.join(project_root, 'data')
os.environ.setdefault('KLINE_USERS_DIR', users_dir_path)
deployment_auth_user = os.environ.get('KLINE_DEPLOYMENT_USER', 'kline')
deployment_auth_password = os.environ.get('KLINE_DEPLOYMENT_PASSWORD', '')


@app.before_request
def require_deployment_auth():
    if request.endpoint == 'health_check':
        return None
    if not is_vercel_runtime or not deployment_auth_password:
        return None
    authorization = request.authorization
    valid_user = authorization is not None and hmac.compare_digest(
        authorization.username or '', deployment_auth_user,
    )
    valid_password = authorization is not None and hmac.compare_digest(
        authorization.password or '', deployment_auth_password,
    )
    if valid_user and valid_password:
        return None
    return Response(
        'Authentication required',
        401,
        {'WWW-Authenticate': 'Basic realm="KLine Playground", charset="UTF-8"'},
    )

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
MARKET_TYPE_A_SHARE = "a_share"
MARKET_TYPE_CRYPTO_PERPETUAL = "crypto_perpetual"
DATA_MODE_CRYPTO_5M = "crypto_5m"
VALID_CRYPTO_PERIODS = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "3h", "4h", "6h", "8h", "12h", "daily", "2d", "3d", "weekly")
CRYPTO_HISTORY_DEFAULT_YEARS = 2
CRYPTO_HISTORY_MIN_YEARS = 1
CRYPTO_HISTORY_MAX_YEARS = 5
CRYPTO_FINE_RENDER_LIMIT = 12000
CRYPTO_FINE_PERIOD_SECONDS = {"1m": 60, "3m": 180, "5m": 300, "15m": 900}
DEFAULT_CRYPTO_MAKER_FEE_RATE = "0"
DEFAULT_CRYPTO_TAKER_FEE_RATE = "0"
MAX_CRYPTO_FEE_RATE = "0.01"
CRYPTO_REPLAY_CHECKPOINT_DELAY_SECONDS = 0.0 if is_vercel_runtime else 0.75
# 懒加载的 IntradayDataService 单例；legacy_daily 路径不会触发其创建，
# 因此旧用户不会因缺少 baostock 等可选依赖而受影响。
_intraday_service_instance = None
_crypto_sources_instance = None
_crypto_instrument_cache_instance = None
_crypto_data_service_instance = None
_crypto_universe_instance = None
_crypto_history_prepare_manager_instance = None
_crypto_history_prepare_users = {}
_crypto_history_download_locks = {}
_crypto_history_download_locks_guard = Lock()

cloud_user_store = CloudUserArchiveStore(users_dir_path)
cloud_state_ready = not cloud_user_store.enabled
cloud_state_last_error = None


def _restore_cloud_users():
    global cloud_state_ready, cloud_state_last_error
    if not cloud_user_store.enabled:
        cloud_state_ready = True
        return []
    try:
        restored = cloud_user_store.restore_all()
    except CloudStateError as exc:
        cloud_state_ready = False
        cloud_state_last_error = str(exc)
        raise
    cloud_state_ready = True
    cloud_state_last_error = None
    return restored


def _request_cloud_username():
    view_args = request.view_args or {}
    username = view_args.get('username')
    if username:
        return str(username)
    payload = request.get_json(silent=True) if request.is_json else None
    if isinstance(payload, dict):
        username = payload.get('user') or payload.get('username')
        if username:
            return str(username)
    training_id = view_args.get('training_id')
    if training_id:
        training = active_trainings.get(training_id)
        if training and training.get('user'):
            return str(training['user'])
        for candidate in user_manager.get_users():
            if str(training_id).startswith(f"{candidate}_"):
                return str(candidate)
    return None


if cloud_user_store.enabled:
    try:
        _restore_cloud_users()
    except CloudStateError as exc:
        print(f"Cloud user restore deferred: {exc}")


@app.before_request
def restore_cloud_request_state():
    if not cloud_user_store.enabled:
        return None
    view_args = request.view_args or {}
    training_id = view_args.get('training_id')
    if training_id and training_id not in active_trainings:
        try:
            _restore_cloud_users()
            _restore_crypto_training(training_id)
        except (CloudStateError, ValueError):
            pass
    username = _request_cloud_username()
    request.environ['kline.cloud_username'] = username or ''
    if username and not os.path.isdir(os.path.join(users_dir_path, username)):
        try:
            cloud_user_store.restore_user(username)
        except CloudStateError as exc:
            return jsonify({'error': str(exc), 'code': 'cloud_state_unavailable'}), 503
    return None


@app.after_request
def persist_cloud_request_state(response):
    global cloud_state_ready, cloud_state_last_error
    if not cloud_user_store.enabled or request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return response
    if response.status_code >= 400:
        return response
    username = request.environ.get('kline.cloud_username') or _request_cloud_username()
    if not username:
        return response
    try:
        if request.method == 'DELETE' and request.endpoint == 'delete_user':
            cloud_user_store.delete_user(username)
        else:
            cloud_user_store.save_user(username)
    except (CloudStateError, FileNotFoundError) as exc:
        cloud_state_ready = False
        cloud_state_last_error = str(exc)
        error_response = jsonify({
            'error': 'cloud persistence failed',
            'detail': str(exc),
            'code': 'cloud_state_persist_failed',
        })
        error_response.status_code = 503
        return error_response
    cloud_state_ready = True
    cloud_state_last_error = None
    return response


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


def _get_crypto_sources():
    global _crypto_sources_instance
    if _crypto_sources_instance is None:
        from backend.crypto.binance_source import BinanceCryptoSource
        from backend.crypto.bybit_source import BybitCryptoSource

        _crypto_sources_instance = (BinanceCryptoSource(), BybitCryptoSource())
    return _crypto_sources_instance


def _get_crypto_instrument_cache():
    global _crypto_instrument_cache_instance
    if _crypto_instrument_cache_instance is None:
        from backend.crypto.cache import CryptoMonthlyCache

        cache_root = os.path.join(data_dir_path, 'crypto')
        _crypto_instrument_cache_instance = CryptoMonthlyCache(cache_root)
    return _crypto_instrument_cache_instance


def _get_crypto_data_service():
    global _crypto_data_service_instance
    if _crypto_data_service_instance is None:
        from backend.crypto.service import CryptoDataService

        _crypto_data_service_instance = CryptoDataService(
            sources=_get_crypto_sources(),
            cache=_get_crypto_instrument_cache(),
        )
    return _crypto_data_service_instance


def _get_crypto_history_prepare_manager():
    global _crypto_history_prepare_manager_instance
    if _crypto_history_prepare_manager_instance is None:
        from backend.crypto.history_prepare import CryptoHistoryPrepareManager

        _crypto_history_prepare_manager_instance = CryptoHistoryPrepareManager(
            _prepare_crypto_history_job,
        )
    return _crypto_history_prepare_manager_instance


def _get_crypto_history_download_lock(source, symbol):
    key = (str(source), str(symbol).upper())
    with _crypto_history_download_locks_guard:
        return _crypto_history_download_locks.setdefault(key, Lock())


def _get_crypto_universe():
    global _crypto_universe_instance
    if _crypto_universe_instance is None:
        from backend.crypto.universe import CryptoUniverse

        def availability_checker(instrument, start, end):
            try:
                _get_crypto_data_service().get_bundle(
                    instrument.symbol, start, end, source=None,
                )
                return True
            except Exception:
                return False

        class CachedCryptoSource:
            name = 'offline-cache'

            def list_instruments(self):
                instruments = _get_crypto_instrument_cache().list_instruments()
                if not instruments:
                    raise RuntimeError('no cached crypto instruments')
                return instruments

            def search_instruments(self, query):
                return _get_crypto_instrument_cache().search_instruments(query)

        class DeferredCryptoSource:
            def __init__(self, name, index):
                self.name = name
                self.index = index

            def list_instruments(self):
                sources = _get_crypto_sources()
                if self.index >= len(sources):
                    raise RuntimeError(f'{self.name} crypto source is unavailable')
                return sources[self.index].list_instruments()

        _crypto_universe_instance = CryptoUniverse(
            (
                CachedCryptoSource(),
                DeferredCryptoSource('binance', 0),
                DeferredCryptoSource('bybit', 1),
            ),
            availability_checker=availability_checker,
        )
    return _crypto_universe_instance


_get_crypto_instrument_cache()
_get_crypto_universe()


def _serialize_crypto_instrument(instrument):
    listed_at = getattr(instrument, 'listed_at', None)
    return {
        'symbol': instrument.symbol,
        'source': instrument.source,
        'base_asset': instrument.base_asset,
        'quote_asset': instrument.quote_asset,
        'contract_type': instrument.contract_type,
        'status': instrument.status,
        'listed_at': listed_at.isoformat() if listed_at else None,
        'tick_size': str(instrument.tick_size),
        'quantity_step': str(instrument.quantity_step),
        'min_quantity': str(instrument.min_quantity),
        'min_notional': str(instrument.min_notional),
        'quote_turnover_24h': str(instrument.quote_turnover_24h),
    }


def _crypto_source_status_payload():
    payload = []
    for source in _get_crypto_sources():
        status = source.status()
        payload.append({
            'source': status.source,
            'available': status.available,
            'message': status.message,
            'checked_at': status.checked_at.isoformat() if status.checked_at else None,
            'latency_ms': status.latency_ms,
        })
    return payload


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


def _is_crypto_session(training):
    return training.get('market_type') == MARKET_TYPE_CRYPTO_PERPETUAL or training.get('data_mode') == DATA_MODE_CRYPTO_5M


def _crypto_snapshot(training):
    snapshot = training['crypto_session'].snapshot()
    futures_executor = training.get('futures_executor')
    if futures_executor is not None:
        snapshot.update(_crypto_futures_payload(training))
    snapshot.update({
        'market_type': MARKET_TYPE_CRYPTO_PERPETUAL,
        'data_mode': DATA_MODE_CRYPTO_5M,
        'symbol': training['symbol'],
        'stock_code': training['symbol'],
        'stock_name': training['symbol'],
        'data_source': training['source'],
        'period': snapshot.get('active_period', training.get('period', '5m')),
        'training_start': training['training_start'],
        'training_end': training['training_end'],
        'trade_markers': snapshot.get('trade_markers', training.get('trade_markers', [])),
    })
    return snapshot


def _crypto_get_data(training):
    return jsonify(_crypto_snapshot(training))


def _append_crypto_chart_base_range(training, start_exclusive, end_inclusive):
    frame = training.get('_crypto_chart_base_frame')
    session = training.get('crypto_session')
    if frame is None or frame.empty or session is None or end_inclusive is None:
        return
    start_timestamp = pd.Timestamp(start_exclusive) if start_exclusive is not None else None
    end_timestamp = pd.Timestamp(end_inclusive)
    if start_timestamp is not None and start_timestamp.tzinfo is None:
        start_timestamp = start_timestamp.tz_localize('UTC')
    if end_timestamp.tzinfo is None:
        end_timestamp = end_timestamp.tz_localize('UTC')
    source_bars = session.base_bars
    mask = source_bars['timestamp'] <= end_timestamp
    if start_timestamp is not None:
        mask &= source_bars['timestamp'] > start_timestamp
    incoming = source_bars.loc[mask].copy()
    if incoming.empty:
        return
    if 'source' in frame.columns:
        incoming['source'] = training.get('source', '')
    if 'symbol' in frame.columns:
        incoming['symbol'] = training.get('symbol', '')
    if 'kind' in frame.columns:
        incoming['kind'] = 'trade'
    incoming['timestamp'] = pd.to_datetime(incoming['timestamp'], utc=True)
    frame_last = pd.Timestamp(frame.iloc[-1]['timestamp'])
    if frame_last.tzinfo is None:
        frame_last = frame_last.tz_localize('UTC')
    if (
        incoming['timestamp'].is_monotonic_increasing
        and bool((incoming['timestamp'] > frame_last).all())
    ):
        training['_crypto_chart_base_frame'] = pd.concat(
            [frame, incoming.reindex(columns=frame.columns)],
            ignore_index=True,
        )
        return
    from backend.crypto.aggregator import normalize_base_bars

    combined = pd.concat([frame, incoming], ignore_index=True)
    training['_crypto_chart_base_frame'] = normalize_base_bars(combined)


def _repair_crypto_chart_session_tail(training, current_time):
    frame = training.get('_crypto_chart_base_frame')
    session = training.get('crypto_session')
    if frame is None or frame.empty or session is None or current_time is None:
        return False
    from backend.crypto.aggregator import normalize_base_bars

    cached = normalize_base_bars(frame)
    session_bars = session.base_bars
    current_timestamp = pd.Timestamp(current_time)
    if current_timestamp.tzinfo is None:
        current_timestamp = current_timestamp.tz_localize('UTC')
    revealed = session_bars.loc[session_bars['timestamp'] <= current_timestamp].copy()
    if revealed.empty:
        return False
    session_start = revealed.iloc[0]['timestamp']
    cached_tail = cached.loc[
        (cached['timestamp'] >= session_start)
        & (cached['timestamp'] <= current_timestamp)
    ]
    if pd.DatetimeIndex(cached_tail['timestamp']).equals(pd.DatetimeIndex(revealed['timestamp'])):
        return False
    historical = cached.loc[cached['timestamp'] < session_start]
    if 'source' in cached.columns:
        revealed['source'] = training.get('source', '')
    if 'symbol' in cached.columns:
        revealed['symbol'] = training.get('symbol', '')
    if 'kind' in cached.columns:
        revealed['kind'] = 'trade'
    training['_crypto_chart_base_frame'] = normalize_base_bars(
        pd.concat([historical, revealed], ignore_index=True)
    )
    return True


def _crypto_next(training):
    lock = training.setdefault('_crypto_next_lock', Lock())
    if not lock.acquire(blocking=False):
        return jsonify({'error': '下一根 K 线正在推进，请稍候。', 'code': 'advance_in_progress'}), 409
    try:
        delta = training['crypto_session'].advance_delta(max_bars=CRYPTO_PERIOD_SNAPSHOT_BAR_LIMIT)
        # 训练自然结束时，生成报告（复用 _crypto_end 逻辑）
        if delta.get('finished'):
            return _crypto_end(training, training['id'])
        if training.get('_crypto_chart_window_start') is not None and delta.get('current_time'):
            previous_window_end = training.get('_crypto_chart_window_end')
            current_window_end = datetime.fromisoformat(delta['current_time']).replace(tzinfo=timezone.utc)
            _append_crypto_chart_base_range(training, previous_window_end, current_window_end)
            training['_crypto_chart_window_end'] = datetime.fromisoformat(
                delta['current_time']
            ).replace(tzinfo=timezone.utc)
            training['_crypto_history_end'] = training['_crypto_chart_window_end']
            # 完全失效窗口缓存：next 推进后 current_time/visible 范围变化，多数 cache_key 失配。
            # 未来优化：把缓存结构改为 {period: {cache_key: payload}} 后可按周期失效，
            # 保留其他周期的窗口缓存（提升回放中切换便利性）。
            training.pop('_crypto_period_window_cache', None)
        _schedule_crypto_checkpoint(training)
        payload = _crypto_futures_payload(training, compact=True)
        position = payload['position']
        delta.update({
            'bars': [] if delta.get('new_bar') is None else [delta['new_bar']],
            'progress': {
                'current_time': delta.get('current_time'),
                'next_boundary': delta.get('next_boundary'),
                'finished': delta.get('finished', False),
                'current_bar_complete': delta.get('current_bar_complete', False),
            },
            'account': payload['account'],
            'position': position,
            'positions': [] if position.get('side') == 'flat' else [position],
            'pending_orders': payload['pending_orders'],
            'fills': payload['fills'],
            'trade_markers': payload['trade_markers'],
            'order_constraints': payload['order_constraints'],
        })
        payload.update({
            'data_mode': DATA_MODE_CRYPTO_5M,
            'market_type': MARKET_TYPE_CRYPTO_PERPETUAL,
            'delta': delta,
            'finished': delta.get('finished', False),
            'completed_times': delta.get('completed_times', []),
            'order_events': delta.get('order_events', []),
        })
        return jsonify(payload)
    finally:
        lock.release()


CRYPTO_PERIOD_SNAPSHOT_BAR_LIMIT = 300


def _clear_crypto_chart_window(training):
    for key in (
        '_crypto_chart_window_start',
        '_crypto_chart_window_end',
        '_crypto_chart_window_has_earlier',
        '_crypto_period_window_cache',
        '_crypto_chart_base_frame',
    ):
        training.pop(key, None)

def _crypto_render_bounds(training, period, current_time, visible_start=None, visible_end=None):
    history_start = training.get('_crypto_history_start') or training.get('_crypto_chart_window_start')
    history_end = training.get('_crypto_history_end') or training.get('_crypto_chart_window_end') or current_time
    if history_start is None:
        return None, None, None, None
    history_start = pd.Timestamp(history_start).to_pydatetime()
    history_end = min(pd.Timestamp(history_end).to_pydatetime(), current_time)
    if period not in CRYPTO_FINE_PERIOD_SECONDS:
        return history_start, history_end, history_start, history_end
    requested_end = min(
        pd.Timestamp(visible_end).to_pydatetime() if visible_end is not None else history_end,
        history_end,
    )
    interval_seconds = CRYPTO_FINE_PERIOD_SECONDS[period]
    requested_end = pd.Timestamp(requested_end).floor(
        f'{interval_seconds}s'
    ).to_pydatetime()
    render_start = requested_end - timedelta(
        seconds=interval_seconds * (CRYPTO_FINE_RENDER_LIMIT - 1)
    )
    render_start = max(history_start, render_start)
    if visible_start is not None:
        requested_start = pd.Timestamp(visible_start).to_pydatetime()
        if requested_start > requested_end:
            requested_start = requested_end
        if requested_start < render_start:
            render_start = max(
                history_start,
                requested_end - timedelta(
                    seconds=interval_seconds * (CRYPTO_FINE_RENDER_LIMIT - 1)
                ),
            )
    return history_start, history_end, render_start, requested_end


def _crypto_extended_period_snapshot(
    training, period, snapshot, visible_start=None, visible_end=None,
):
    if not training.get('symbol') or not training.get('source'):
        return snapshot
    from backend.crypto.chart_window import CryptoChartWindowService

    current_time = datetime.fromisoformat(snapshot['current_time']).replace(tzinfo=timezone.utc)
    if _repair_crypto_chart_session_tail(training, current_time):
        training.pop('_crypto_period_window_cache', None)
    history_start, history_end, render_start, render_end = _crypto_render_bounds(
        training, period, current_time, visible_start, visible_end,
    )
    if history_start is None:
        return snapshot
    cache_key = (
        period,
        current_time.isoformat(),
        history_start.isoformat(),
        history_end.isoformat(),
        render_start.isoformat(),
        render_end.isoformat(),
    )
    cache = training.setdefault('_crypto_period_window_cache', {})
    window_payload = cache.get(cache_key)
    if window_payload is None:
        result = CryptoChartWindowService(_get_crypto_data_service()).load(
            symbol=training['symbol'],
            source=training['source'],
            period=period,
            range_start=render_start,
            range_end=render_end,
            current_time=current_time,
            read_only=False,
            trade_bars=training.get('_crypto_chart_base_frame'),
        )
        window_payload = result.to_dict()
        window_payload.update({
            'history_start': history_start.strftime('%Y-%m-%d %H:%M:%S'),
            'history_end': history_end.strftime('%Y-%m-%d %H:%M:%S'),
            'render_start': render_start.strftime('%Y-%m-%d %H:%M:%S'),
            'render_end': render_end.strftime('%Y-%m-%d %H:%M:%S'),
            'window_start': history_start.strftime('%Y-%m-%d %H:%M:%S'),
            'window_end': history_end.strftime('%Y-%m-%d %H:%M:%S'),
            'has_earlier_render': render_start > history_start,
            'has_earlier': False,
            'has_later': False,
            'extended_history': True,
        })
        cache[cache_key] = window_payload

    merged = dict(snapshot)
    merged.update(window_payload)
    merged.update({
        'active_period': period,
        'period': period,
        'current_time': snapshot['current_time'],
        'current_bar_complete': snapshot.get('current_bar_complete', False),
        'next_boundary': snapshot.get('next_boundary'),
        'current_base_bar': snapshot.get('current_base_bar'),
        'finished': snapshot.get('finished', False),
        'available_periods': snapshot.get('available_periods', list(VALID_CRYPTO_PERIODS)),
        'base_interval': snapshot.get('base_interval', '1m'),
        'market_type': MARKET_TYPE_CRYPTO_PERPETUAL,
        'data_mode': DATA_MODE_CRYPTO_5M,
    })
    return merged


def _compact_crypto_period_snapshot(snapshot):
    compact = dict(snapshot)
    compact['kline_data'] = [
        {
            'time': bar.get('time') or bar.get('end_time') or bar.get('datetime'),
            'open': bar.get('open'), 'high': bar.get('high'),
            'low': bar.get('low'), 'close': bar.get('close'),
            'volume': bar.get('volume', 0),
        }
        for bar in snapshot.get('kline_data', [])
    ]
    compact['volume_data'] = []
    return compact


def _crypto_set_period(
    training, period, request_id=None, range_start=None, range_end=None,
    visible_start=None, visible_end=None, compact_chart=False,
):
    if period not in VALID_CRYPTO_PERIODS:
        return jsonify({'error': f'unsupported crypto period: {period}'}), 400
    effective_range_start = training.get('_crypto_history_start') or range_start or training.get('_crypto_chart_window_start')
    effective_range_end = training.get('_crypto_history_end') or range_end or training.get('_crypto_chart_window_end')
    use_window_service = bool(
        effective_range_start is not None
        and training.get('symbol')
        and training.get('source')
    )
    lock = training.setdefault('_period_switch_lock', Lock())
    with lock:
        latest_request_id = training.get('_period_request_id', -1)
        if request_id is not None and request_id < latest_request_id:
            active_period = training.get('period', period)
            snapshot = training['crypto_session'].snapshot(
                max_bars=CRYPTO_PERIOD_SNAPSHOT_BAR_LIMIT if use_window_service else (
                    None if effective_range_start is not None or effective_range_end is not None
                    else CRYPTO_PERIOD_SNAPSHOT_BAR_LIMIT
                ),
                range_start=None if use_window_service else effective_range_start,
                range_end=None if use_window_service else effective_range_end,
            )
            stale_snapshot = _crypto_extended_period_snapshot(
                training, active_period, snapshot,
                visible_start, visible_end,
            ) if use_window_service else snapshot
            return jsonify(_compact_crypto_period_snapshot(stale_snapshot) if compact_chart else stale_snapshot)
        if request_id is not None:
            training['_period_request_id'] = request_id
        training['period'] = period
        snapshot = training['crypto_session'].set_period(
            period,
            max_bars=CRYPTO_PERIOD_SNAPSHOT_BAR_LIMIT if use_window_service else (
                None if effective_range_start is not None or effective_range_end is not None
                else CRYPTO_PERIOD_SNAPSHOT_BAR_LIMIT
            ),
            range_start=None if use_window_service else effective_range_start,
            range_end=None if use_window_service else effective_range_end,
        )
        if use_window_service:
            snapshot = _crypto_extended_period_snapshot(
                training, period, snapshot,
                visible_start, visible_end,
            )
        _persist_crypto_period(training, period)
        return jsonify(_compact_crypto_period_snapshot(snapshot) if compact_chart else snapshot)

def _persist_crypto_period(training, period):
    from backend.crypto.persistence import CryptoFuturesRepository

    training_id = training.get('id')
    user = training.get('user')
    if not training_id or not user:
        return
    db_path = user_manager.history_manager._get_user_db_path(user)
    repository = CryptoFuturesRepository(db_path, migrate=False)
    repository.update_runtime_period(training_id, period)


def _crypto_reset(training):
    _clear_crypto_chart_window(training)
    training['crypto_session'].reset()
    _initialize_crypto_futures(training)
    _checkpoint_crypto_futures(training)
    return jsonify({
        'message': '训练已重置',
        'data_mode': DATA_MODE_CRYPTO_5M,
        'market_type': MARKET_TYPE_CRYPTO_PERPETUAL,
        'snapshot': _crypto_snapshot(training),
    })


def _initialize_crypto_futures(training):
    from backend.crypto.futures_engine import FuturesEngine
    from backend.crypto.futures_orders import FuturesOrderBook
    from backend.crypto.futures_simulator import FuturesSimulator
    from backend.crypto.trading import FuturesReplayExecutor

    instrument = training['instrument']
    bundle = training['crypto_bundle']
    simulator = FuturesSimulator(
        training['initial_capital'],
        quantity_step=instrument.quantity_step,
        min_quantity=instrument.min_quantity,
        min_notional=instrument.min_notional,
        leverage=training.get('leverage', 5),
    )
    order_book = FuturesOrderBook(
        simulator,
        maker_fee_rate=training.get('maker_fee_rate', DEFAULT_CRYPTO_MAKER_FEE_RATE),
        taker_fee_rate=training.get('taker_fee_rate', DEFAULT_CRYPTO_TAKER_FEE_RATE),
    )
    engine = FuturesEngine(simulator, order_book)
    executor = FuturesReplayExecutor(
        clock=training['crypto_session'].clock,
        trade_bars=bundle.trade_bars,
        mark_bars=bundle.mark_bars,
        engine=engine,
        funding_events=bundle.funding,
        symbol=training['symbol'],
        source=training['source'],
    )
    training['crypto_session']._on_bar = executor.on_bar
    training['futures_executor'] = executor
    return executor


def _crypto_futures_payload(training, *, compact=False):
    executor = training['futures_executor']
    simulator = executor.engine.simulator
    mark_price = simulator.last_mark_price or simulator.position.entry_price
    if compact:
        simulator_snapshot = simulator.snapshot(mark_price)
        payload = {
            'market_type': MARKET_TYPE_CRYPTO_PERPETUAL,
            'data_mode': DATA_MODE_CRYPTO_5M,
            'symbol': executor.symbol,
            'source': executor.source,
            'current_time': executor.clock.current_time.isoformat(),
            'active_period': executor.clock.active_period.value,
            'finished': not executor.clock.has_next(),
            'account': simulator_snapshot['account'],
            'position': simulator_snapshot['position'],
            'fills': [fill.to_dict() for fill in simulator.fills[-20:]],
            'trade_markers': executor._trade_markers(),
        }
    else:
        payload = executor.snapshot()
    liquidation_price = executor.engine.liquidation_price()
    position = payload['position']
    position.update({
        'notional': float(simulator.position.notional(mark_price)),
        'liquidation_price': None if liquidation_price is None else float(liquidation_price),
    })
    account = payload['account']
    account.update({
        'mark_price': float(mark_price),
        'margin_ratio': float(simulator.margin_ratio(mark_price) / 100),
        'funding_net': float(simulator.account.funding_received - simulator.account.funding_paid),
    })
    order_book = executor.engine.order_book
    leverage = int(training.get('leverage', simulator.leverage))
    trade_price = executor._trade_bars[executor.clock.current_time]['close']
    payload['order_constraints'] = {
        'maker_fee_rate': float(order_book.maker_fee_rate),
        'taker_fee_rate': float(order_book.taker_fee_rate),
        'reserved_margin': float(order_book.reserved_margin),
        'leverage': leverage,
        'current_price': float(trade_price),
        'quantity_step': float(simulator.quantity_step),
        'min_quantity': float(simulator.min_quantity),
        'min_notional': float(simulator.min_notional),
        'max_market_margin': float(order_book.max_open_margin(order_type='market', leverage=leverage)),
        'max_limit_margin': float(order_book.max_open_margin(order_type='limit', leverage=leverage)),
        'max_breakout_margin': float(order_book.max_open_margin(order_type='breakout', leverage=leverage)),
    }
    payload['pending_orders'] = [
        order.to_dict() for order in executor.engine.order_book.active_orders
    ]
    return payload


def _crypto_update_fee_rates(training, data):
    from backend.crypto.futures_models import decimal_value

    executor = training['futures_executor']
    order_book = executor.engine.order_book
    simulator = executor.engine.simulator
    if not simulator.position.is_flat or order_book.active_orders:
        return jsonify({'error': '请在空仓且无挂单时修改手续费率。'}), 400
    try:
        maker = decimal_value(data.get('maker_fee_rate'))
        taker = decimal_value(data.get('taker_fee_rate'))
        maximum = decimal_value(MAX_CRYPTO_FEE_RATE)
        if maker < 0 or taker < 0 or maker > maximum or taker > maximum:
            raise ValueError('fee rate out of range')
        order_book.set_fee_rates(maker_fee_rate=maker, taker_fee_rate=taker)
    except (TypeError, ValueError, ArithmeticError):
        return jsonify({'error': '手续费率必须是 0% 到 1% 之间的有效数字。'}), 400
    training['maker_fee_rate'] = format(maker, 'f')
    training['taker_fee_rate'] = format(taker, 'f')
    _checkpoint_crypto_futures(training)
    payload = _crypto_futures_payload(training)
    payload.update({'success': True, 'message': '手续费率已更新，仅影响后续成交。'})
    return jsonify(payload)


def _crypto_trade(training, data):
    executor = training['futures_executor']
    try:
        order = executor.submit_order(
            action=data.get('action'),
            order_type=data.get('order_type', 'market'),
            margin=data.get('margin'),
            quantity=data.get('quantity'),
            leverage=int(data.get('leverage', training.get('leverage', 5))),
            limit_price=data.get('limit_price'),
            trigger_price=data.get('trigger_price'),
            tp_price=data.get('tp_price'),
            sl_price=data.get('sl_price'),
        )
    except ValueError as error:
        message = str(error)
        structured_code = getattr(error, 'code', None)
        structured_message = getattr(error, 'message', None)
        if structured_code and structured_message:
            return jsonify({
                'error': structured_message,
                'message': structured_message,
                'code': structured_code,
            }), 400
        error_map = {
            'insufficient available margin including fee': (
                'insufficient_margin', '可用保证金不足，请降低保证金并预留手续费。'
            ),
            'margin must be positive': ('invalid_margin', '保证金必须大于 0。'),
            'margin is required for open orders': ('invalid_margin', '请输入开仓保证金。'),
            'cannot close a flat position': ('no_position', '当前没有可平仓的持仓。'),
            'limit_price is required for limit orders': ('invalid_limit_price', '限价单必须填写限价。'),
            'limit_price must be positive': ('invalid_limit_price', '限价必须大于 0。'),
            'trigger_price is required for breakout orders': ('invalid_trigger_price', '突破单必须填写触发价。'),
            'trigger_price must be positive': ('invalid_trigger_price', '触发价必须大于 0。'),
            'leverage can change only while flat without active orders': (
                'leverage_locked', '存在持仓或挂单时不能修改杠杆。'
            ),
            'tp/sl can only be set on opening orders': ('invalid_tp_sl', '止盈止损只能设置在开仓单上。'),
            'tp_price must be positive': ('invalid_tp_sl', '止盈价必须大于 0。'),
            'sl_price must be positive': ('invalid_tp_sl', '止损价必须大于 0。'),
            'tp_price must be above entry price for long': ('invalid_tp_sl', '做多止盈价必须高于开仓价。'),
            'sl_price must be below entry price for long': ('invalid_tp_sl', '做多止损价必须低于开仓价。'),
            'tp_price must be below entry price for short': ('invalid_tp_sl', '做空止盈价必须低于开仓价。'),
            'sl_price must be above entry price for short': ('invalid_tp_sl', '做空止损价必须高于开仓价。'),
        }
        code, localized = error_map.get(message, ('invalid_order', '合约订单参数无效，请检查后重试。'))
        return jsonify({'error': localized, 'message': localized, 'code': code}), 400
    training['leverage'] = order.leverage
    _checkpoint_crypto_futures(training)
    payload = _crypto_futures_payload(training)
    payload.update({'success': True, 'order': order.to_dict()})
    return jsonify(payload)


def _crypto_end(training, training_id):
    from backend.crypto.persistence import build_crypto_futures_report

    payload = _crypto_futures_payload(training)
    account = payload['account']
    report = build_crypto_futures_report(
        initial_equity=training['initial_capital'],
        final_equity=account['equity'],
        unrealized_pnl=payload['position']['unrealized_pnl'],
        fills=payload['fills'],
        orders=payload['orders'],
        funding_events=payload['funding_events'],
        liquidation_events=payload['liquidation_events'],
        equity_snapshots=payload['equity_snapshots'],
        max_drawdown_percent=training['futures_executor'].engine.max_drawdown_percent(),
        leverage=training.get('leverage', 5),
        source=training['source'],
        symbol=training['symbol'],
        display_period=training.get('period', '5m'),
    )
    current_time = training['crypto_session'].snapshot()['current_time']
    report.update({
        'session_id': training_id,
        'market_type': MARKET_TYPE_CRYPTO_PERPETUAL,
        'data_mode': DATA_MODE_CRYPTO_5M,
        'simulator_type': 'isolated_futures',
        'symbol': training['symbol'],
        'stock_code': training['symbol'],
        'quote_currency': 'USDT',
        'base_interval': '5m',
        'timezone': 'UTC',
        'period': training.get('period', '5m'),
        'training_start': training['training_start'],
        'training_end': current_time,
        'start_date': training['start_date'],
        'end_date': current_time[:10],
        'initial_capital': report['initial_equity'],
        'final_capital': report['final_equity'],
        'total_trades': report['fill_count'],
        'trade_win_rate': report['win_rate'],
        'session_win_rate': 100.0 if report['total_return'] > 0 else 0.0,
        'trade_details': payload['fills'],
        'trade_markers': payload['trade_markers'],
        'account': account,
        'position': payload['position'],
        'maker_fee_rate': payload['order_constraints']['maker_fee_rate'],
        'taker_fee_rate': payload['order_constraints']['taker_fee_rate'],
    })
    session_data = {
        'session_id': training_id,
        'stock_code': training['symbol'],
        'stock_name': training['symbol'],
        'start_date': training['start_date'],
        'end_date': current_time[:10],
        'mode': training['mode'],
        'initial_capital': report['initial_capital'],
        'final_capital': report['final_capital'],
        'total_return': report['total_return'],
        'max_drawdown': report['max_drawdown'],
        'total_trades': report['total_trades'],
        'trade_win_rate': report['trade_win_rate'],
        'session_win_rate': report['session_win_rate'],
        'total_commission': report['total_fees'],
        'report_data': report,
        'review_summary': '',
        'status': 'ended',
    }
    _persist_crypto_futures_state(training, training_id, payload)
    user_manager.save_training_session(training['user'], session_data)
    _clear_crypto_chart_window(training)
    training['status'] = 'ended'
    _update_api_info(user=training['user'])
    report['finished'] = True
    return jsonify(report)


def _persist_crypto_futures_state(training, training_id, payload):
    from backend.crypto.persistence import CryptoFuturesRepository

    db_path = user_manager.history_manager._get_user_db_path(training['user'])
    repository = CryptoFuturesRepository(db_path)
    repository.save_runtime_state(
        training_id,
        _crypto_runtime_state(training, status='ended'),
    )
    repository.save_session_metadata(
        training_id,
        market_type=MARKET_TYPE_CRYPTO_PERPETUAL,
        symbol=training['symbol'],
        quote_currency='USDT',
        base_interval='5m',
        timezone='UTC',
        source=training['source'],
        simulator_type='isolated_futures',
    )
    orders = list(payload.get('orders', []))
    fills = list(payload.get('fills', []))
    funding = list(payload.get('funding_events', []))
    liquidations = list(payload.get('liquidation_events', []))
    snapshots = list(payload.get('equity_snapshots', []))
    if orders:
        repository.record_orders(training_id, orders)
    if fills:
        repository.record_fills(training_id, fills)
    if funding:
        repository.record_funding_events(training_id, funding)
    if liquidations:
        repository.record_liquidations(training_id, liquidations)
    if snapshots:
        repository.record_equities(training_id, snapshots)


def _crypto_runtime_state(training, *, status=None):
    state = training['futures_executor'].export_state()
    state['training'] = {
        'id': training.get('id'),
        'user': training['user'],
        'symbol': training['symbol'],
        'source': training['source'],
        'period': training.get('period', '5m'),
        'initial_period': training.get('initial_period', training.get('period', '5m')),
        'mode': training.get('mode', 'specified'),
        'start_date': training['start_date'],
        'training_start': training['training_start'],
        'training_end': training['training_end'],
        'max_training_days': training.get('max_training_days'),
        'history_years': training.get('history_years'),
        'history_start': (
            training.get('_crypto_history_start').isoformat()
            if training.get('_crypto_history_start') is not None else None
        ),
        'initial_capital': training['initial_capital'],
        'leverage': training.get('leverage', 5),
        'maker_fee_rate': format(training['futures_executor'].engine.order_book.maker_fee_rate, 'f'),
        'taker_fee_rate': format(training['futures_executor'].engine.order_book.taker_fee_rate, 'f'),
        'status': status or training.get('status', 'active'),
    }
    return state


def _checkpoint_crypto_futures(training):
    from backend.crypto.persistence import CryptoFuturesRepository

    training_id = training.get('id')
    if not training_id or not training.get('futures_executor'):
        return
    write_lock = training.setdefault('_crypto_checkpoint_write_lock', Lock())
    with write_lock:
        db_path = user_manager.history_manager._get_user_db_path(training['user'])
        repository = CryptoFuturesRepository(db_path)
        repository.save_session_metadata(
            training_id,
            market_type=MARKET_TYPE_CRYPTO_PERPETUAL,
            symbol=training['symbol'],
            quote_currency='USDT',
            base_interval='5m',
            timezone='UTC',
            source=training['source'],
            simulator_type='isolated_futures',
        )
        repository.save_runtime_state(training_id, _crypto_runtime_state(training))


def _schedule_crypto_checkpoint(training):
    if app.config.get('TESTING'):
        return
    if CRYPTO_REPLAY_CHECKPOINT_DELAY_SECONDS <= 0:
        _checkpoint_crypto_futures(training)
        return
    schedule_lock = training.setdefault('_crypto_checkpoint_schedule_lock', Lock())
    with schedule_lock:
        previous = training.get('_crypto_checkpoint_timer')
        if previous is not None:
            previous.cancel()
        generation = int(training.get('_crypto_checkpoint_generation', 0)) + 1
        training['_crypto_checkpoint_generation'] = generation
        timer = Timer(
            CRYPTO_REPLAY_CHECKPOINT_DELAY_SECONDS,
            _run_scheduled_crypto_checkpoint,
            args=(training, generation),
        )
        timer.daemon = True
        training['_crypto_checkpoint_timer'] = timer
        timer.start()


def _run_scheduled_crypto_checkpoint(training, generation):
    if generation != training.get('_crypto_checkpoint_generation'):
        return
    next_lock = training.setdefault('_crypto_next_lock', Lock())
    with next_lock:
        if generation == training.get('_crypto_checkpoint_generation') and training.get('status') == 'active':
            _checkpoint_crypto_futures(training)
    schedule_lock = training.setdefault('_crypto_checkpoint_schedule_lock', Lock())
    with schedule_lock:
        if generation == training.get('_crypto_checkpoint_generation'):
            training['_crypto_checkpoint_timer'] = None


def _parse_crypto_runtime_time(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _restore_crypto_training(training_id):
    from backend.crypto.persistence import CryptoFuturesRepository
    from backend.crypto.session import CryptoReplaySession

    if training_id in active_trainings:
        return active_trainings[training_id]
    for user in user_manager.get_users():
        db_path = user_manager.history_manager._get_user_db_path(user)
        if not os.path.exists(db_path):
            continue
        try:
            repository = CryptoFuturesRepository(db_path)
            state = repository.load_runtime_state(training_id)
        except Exception:
            continue
        metadata = state.get('training') if isinstance(state, dict) else None
        if not metadata or metadata.get('status') != 'active':
            continue
        symbol = str(metadata.get('symbol') or state.get('symbol') or '').upper()
        source = metadata.get('source') or state.get('source')
        training_start = _parse_crypto_runtime_time(metadata.get('training_start'))
        training_end = _parse_crypto_runtime_time(metadata.get('training_end'))
        if not symbol or training_start is None or training_end is None:
            continue
        bundle = _get_crypto_data_service().get_bundle(
            symbol,
            training_start - timedelta(days=30),
            training_end,
            source=source,
        )
        initial_period = metadata.get('initial_period') or metadata.get('period') or '5m'
        session = CryptoReplaySession(
            bundle.trade_bars,
            initial_time=training_start,
            symbol=symbol,
            source=bundle.source,
            active_period=initial_period,
            max_training_days=int(metadata.get('max_training_days') or 1),
        )
        runtime_time = _parse_crypto_runtime_time(state.get('clock', {}).get('current_time'))
        if runtime_time and runtime_time > session.clock.current_time:
            session.clock.advance(runtime_time)
        session.clock.set_period(state.get('clock', {}).get('active_period') or metadata.get('period') or initial_period)
        history_years = int(metadata.get('history_years') or 0)
        history_start = _parse_crypto_runtime_time(metadata.get('history_start'))
        history_end = runtime_time or training_start
        history_frame = None
        if history_years >= CRYPTO_HISTORY_MIN_YEARS and history_start is not None:
            _, history_frame = _get_crypto_data_service().get_chart_bars(
                symbol,
                history_start,
                history_end,
                source=bundle.source,
            )
        executor = repository.rehydrate_executor(
            training_id,
            trade_bars=bundle.trade_bars,
            mark_bars=bundle.mark_bars,
            funding_events=bundle.funding,
        )
        executor.clock = session.clock
        session._on_bar = executor.on_bar
        training = {
            'id': training_id,
            'user': metadata.get('user') or user,
            'market_type': MARKET_TYPE_CRYPTO_PERPETUAL,
            'data_mode': DATA_MODE_CRYPTO_5M,
            'symbol': symbol,
            'stock_code': symbol,
            'source': bundle.source,
            'data_source': bundle.source,
            'period': session.clock.active_period.value,
            'initial_period': initial_period,
            'mode': metadata.get('mode', 'specified'),
            'start_date': metadata.get('start_date') or training_start.date().isoformat(),
            'training_start': training_start.strftime('%Y-%m-%d %H:%M:%S'),
            'training_end': training_end.strftime('%Y-%m-%d %H:%M:%S'),
            'max_training_days': int(metadata.get('max_training_days') or 1),
            'history_years': history_years or None,
            'initial_capital': float(metadata.get('initial_capital') or 0),
            'leverage': int(metadata.get('leverage') or 5),
            'maker_fee_rate': format(executor.engine.order_book.maker_fee_rate, 'f'),
            'taker_fee_rate': format(executor.engine.order_book.taker_fee_rate, 'f'),
            'crypto_session': session,
            'crypto_bundle': bundle,
            'instrument': bundle.instrument,
            'futures_executor': executor,
            'status': 'active',
            'created_at': datetime.now(timezone.utc),
        }
        if history_frame is not None:
            training.update({
                '_crypto_history_start': history_start,
                '_crypto_history_end': history_end,
                '_crypto_chart_window_start': history_start,
                '_crypto_chart_window_end': history_end,
                '_crypto_chart_window_has_earlier': False,
                '_crypto_chart_base_frame': history_frame,
            })
        active_trainings[training_id] = training
        return training
    return None


@app.before_request
def _restore_crypto_training_for_request():
    training_id = (request.view_args or {}).get('training_id')
    if training_id and training_id not in active_trainings:
        _restore_crypto_training(training_id)


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

        is_crypto = (
            report.get('market_type') == MARKET_TYPE_CRYPTO_PERPETUAL
            or report.get('data_mode') == DATA_MODE_CRYPTO_5M
        )
        required = (
            ('symbol', 'training_start', 'training_end')
            if is_crypto else
            ('stock_code', 'training_start', 'training_end')
        )
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

        if is_crypto:
            from backend.crypto.chart_window import CryptoChartWindowService

            result = CryptoChartWindowService(_get_crypto_data_service()).load(
                symbol=report['symbol'],
                source=report.get('source') or report.get('data_source'),
                period=period,
                range_start=range_start,
                range_end=range_end,
                current_time=datetime.fromisoformat(report['training_end']),
                read_only=True,
            )
            payload = result.to_dict()
            payload.update({
                'market_type': MARKET_TYPE_CRYPTO_PERPETUAL,
                'data_mode': DATA_MODE_CRYPTO_5M,
                'training_start': report['training_start'],
                'training_end': report['training_end'],
                'trade_markers': report.get('trade_markers') or _trade_markers(
                    report.get('trade_details')
                ),
            })
            return jsonify(payload)

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


@app.route('/api/crypto/instruments', methods=['GET'])
def get_crypto_instruments():
    try:
        query = request.args.get('query', '')
        limit = min(max(int(request.args.get('limit', 20)), 1), 100)
        instruments = _get_crypto_universe().search(query=query, limit=limit)
        return jsonify({'instruments': [_serialize_crypto_instrument(item) for item in instruments]})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 503


@app.route('/api/crypto/sources/status', methods=['GET'])
def get_crypto_source_status():
    try:
        return jsonify({'sources': _crypto_source_status_payload()})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 503


@app.route('/api/crypto/data/offline_status', methods=['GET'])
def get_crypto_offline_status():
    try:
        from backend.crypto.data_manager import scan_crypto_offline_status
        return jsonify(scan_crypto_offline_status())
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/api/crypto/data/download', methods=['POST'])
def download_crypto_data():
    try:
        from backend.crypto.data_manager import sync_crypto_offline_data
        payload = request.get_json() or {}
        symbol = str(payload.get('symbol') or '').strip().upper()
        if not symbol:
            return jsonify({'error': 'symbol is required'}), 400
        year = payload.get('year') or 'all'
        source = str(payload.get('source') or 'binance').lower()
        kinds = payload.get('kinds') or ('trade', 'mark', 'funding')
        result = sync_crypto_offline_data(symbol=symbol, year=year, source=source, kinds=tuple(kinds))
        return jsonify(result)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


def _crypto_history_prepare_payload(payload):
    normalized = dict(payload or {})
    current_start = normalized.get('current_start')
    current_end = normalized.get('current_end')
    if isinstance(current_start, datetime):
        normalized['current_start'] = current_start.strftime('%Y-%m-%d %H:%M:%S')
        normalized['current_month'] = current_start.strftime('%Y-%m')
    if isinstance(current_end, datetime):
        normalized['current_end'] = current_end.strftime('%Y-%m-%d %H:%M:%S')
    normalized['completed_months'] = normalized.get('completed_chunks', 0)
    normalized['total_months'] = normalized.get('total_chunks', 0)
    return normalized


def _crypto_history_prepare_owner(job_id):
    requested_user = request.args.get('user')
    owner = _crypto_history_prepare_users.get(str(job_id))
    if requested_user and owner and requested_user != owner:
        raise ValueError('history prepare job not found')
    if not owner:
        raise ValueError('history prepare job not found')
    return owner


@app.route('/api/crypto/history/prepare', methods=['POST'])
def prepare_crypto_history():
    try:
        payload = request.get_json() or {}
        user = str(payload.get('user') or '').strip()
        if not user:
            return jsonify({'error': 'user is required'}), 400
        payload = dict(payload)
        payload['history_years'] = _parse_crypto_history_years(payload)
        # 临时诊断日志：打印完整 payload，便于排查"start must not be after end"
        try:
            with open('_history_prepare_debug.log', 'a', encoding='utf-8') as debug_handle:
                debug_handle.write(f"[{datetime.now(timezone.utc).isoformat()}] POST payload={payload}\n")
        except Exception:
            pass
        job = _get_crypto_history_prepare_manager().create(user, payload)
        _crypto_history_prepare_users[job['job_id']] = user
        return jsonify(_crypto_history_prepare_payload(job)), 202
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    except Exception as error:
        return jsonify({'error': str(error)}), 503


@app.route('/api/crypto/history/prepare/<job_id>', methods=['GET'])
def get_crypto_history_prepare(job_id):
    try:
        owner = _crypto_history_prepare_owner(job_id)
        job = _get_crypto_history_prepare_manager().get(job_id, owner)
        return jsonify(_crypto_history_prepare_payload(job))
    except Exception as error:
        return jsonify({'error': str(error)}), 404


@app.route('/api/crypto/history/prepare/<job_id>', methods=['DELETE'])
def cancel_crypto_history_prepare(job_id):
    try:
        owner = _crypto_history_prepare_owner(job_id)
        job = _get_crypto_history_prepare_manager().cancel(job_id, owner)
        return jsonify(_crypto_history_prepare_payload(job))
    except Exception as error:
        return jsonify({'error': str(error)}), 404


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
        'id': training_id,
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
            'trade_markers': _trade_markers(trade_simulator.trade_history),
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


def _parse_crypto_timestamp(value):
    if not value:
        raise ValueError('crypto start_time is required')
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone(timedelta(hours=8)))
    parsed = parsed.astimezone(timezone.utc)
    # 新底座 1m 对齐：保持原分钟（向后兼容 5m 倍数边界）
    return parsed.replace(second=0, microsecond=0)


def _normalize_crypto_symbol(value):
    symbol = str(value or '').strip().upper()
    for separator in ('/', '-', '_', ' '):
        symbol = symbol.replace(separator, '')
    if symbol and not symbol.endswith(('USDT', 'USDC')):
        symbol += 'USDT'
    return symbol


def _parse_crypto_history_years(payload):
    raw_value = (payload or {}).get('history_years', CRYPTO_HISTORY_DEFAULT_YEARS)
    if isinstance(raw_value, bool):
        raise ValueError(
            f'history_years must be an integer from {CRYPTO_HISTORY_MIN_YEARS} to '
            f'{CRYPTO_HISTORY_MAX_YEARS}'
        )
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = None
    if value is None or str(raw_value).strip() not in {str(value), f'+{value}'}:
        raise ValueError(
            f'history_years must be an integer from {CRYPTO_HISTORY_MIN_YEARS} to '
            f'{CRYPTO_HISTORY_MAX_YEARS}'
        )
    if not CRYPTO_HISTORY_MIN_YEARS <= value <= CRYPTO_HISTORY_MAX_YEARS:
        raise ValueError(
            f'history_years must be between {CRYPTO_HISTORY_MIN_YEARS} and '
            f'{CRYPTO_HISTORY_MAX_YEARS}'
        )
    return value


def _subtract_calendar_years(value, years):
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, month=2, day=28)


def _crypto_training_days(payload, explicit_days=None):
    if explicit_days is None:
        max_bars = (payload or {}).get('max_bars', 0) or 0
        explicit_days = (payload or {}).get('max_training_days', max_bars) or 0
    training_days = int(explicit_days)
    if training_days == 0:
        return None  # 不限制，由可用数据决定训练长度
    if training_days < 0:
        training_days = 30
    if training_days > 365:
        raise ValueError('crypto training is limited to 365 calendar days per session')
    return training_days


def _crypto_prepare_candidate(
    *, symbol, training_start, training_days, history_years,
    preferred_source=None, progress_callback=None, cancel_check=None,
    history_months=None, history_start=None,
):
    service = _get_crypto_data_service()
    prepare_days = training_days if training_days is not None else 365
    context_start = training_start - timedelta(days=30)
    range_end = training_start + timedelta(days=prepare_days, minutes=-1)
    # 临时诊断日志：打印边界，排查"start must not be after end"
    try:
        with open('_history_prepare_debug.log', 'a', encoding='utf-8') as debug_handle:
            debug_handle.write(
                f"[{datetime.now(timezone.utc).isoformat()}] candidate symbol={symbol} "
                f"training_start={training_start} training_days={training_days} "
                f"prepare_days={prepare_days} context_start={context_start} "
                f"range_end={range_end} start_after_end={context_start > range_end}\n"
            )
    except Exception:
        pass
    # 不限制天数时，检查离线缓存覆盖范围，避免尝试下载不存在的数据
    if training_days is None:
        try:
            cache = service.cache
            for kind in ('trade',):
                for src in ('binance', 'bybit'):
                    cov = cache.coverage(src, symbol, kind)
                    # 仅当缓存覆盖到训练窗口内才裁剪 range_end，
                    # 否则（缓存早于训练开始日）保留原 range_end，避免 start > end。
                    if cov and training_start <= cov.end < range_end:
                        range_end = cov.end
                        break
        except Exception:
            pass
    # 防护：训练窗口结束时间不得晚于当前时间，否则实时数据源无法提供未来行情，
    # 只会报出误导性的 "lacks complete aligned trade/mark coverage"。
    now_utc = datetime.now(timezone.utc)
    if range_end > now_utc:
        available_days = max((now_utc - training_start).days, 0)
        raise ValueError(
            f'crypto 训练窗口结束于 {range_end.strftime("%Y-%m-%d %H:%M")}（UTC），'
            f'晚于当前时间 {now_utc.strftime("%Y-%m-%d %H:%M")}（UTC），数据源无法提供未来行情。'
            f'起始时间 {training_start.strftime("%Y-%m-%d %H:%M")} 距今不足 {prepare_days} 天，'
            f'请将起始时间提前，或将"训练交易日限制"设为不超过 {available_days} 天。'
        )
    if history_months is not None:
        history_start = training_start - timedelta(days=int(history_months) * 30)
    elif history_start:
        if isinstance(history_start, str):
            history_start = _parse_crypto_timestamp(history_start)
    else:
        history_start = _subtract_calendar_years(training_start, history_years)
    candidate_sources = []
    if preferred_source:
        candidate_sources.append(str(preferred_source))
    else:
        candidate_sources.append(None)
        candidate_sources.extend(
            source.name for source in _get_crypto_sources()
            if source.name not in candidate_sources
        )
    failures = []
    attempted_sources = set()
    for requested_source in candidate_sources:
        if cancel_check is not None and cancel_check():
            raise ValueError('crypto history preparation cancelled')
        try:
            bundle = service.get_bundle(
                symbol, context_start, range_end, source=requested_source,
            )
            resolved_source = bundle.source
            if resolved_source in attempted_sources:
                continue
            attempted_sources.add(resolved_source)
            with _get_crypto_history_download_lock(resolved_source, symbol):
                prepared_source, history_frame = service.prepare_chart_bars(
                    symbol,
                    history_start,
                    training_start,
                    source=resolved_source,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                )
            if prepared_source != resolved_source:
                raise ValueError(
                    f'crypto history source mismatch: {resolved_source} != {prepared_source}'
                )
            history_frame = history_frame.loc[
                pd.to_datetime(history_frame['timestamp'], utc=True)
                <= pd.Timestamp(training_start)
            ].reset_index(drop=True)
            return {
                'symbol': symbol,
                'source': resolved_source,
                'instrument': bundle.instrument,
                'bundle': bundle,
                'training_start': training_start,
                'context_start': context_start,
                'range_end': range_end,
                'history_start': history_start,
                'history_end': training_start,
                'history_years': history_years,
                'history_frame': history_frame,
                'training_days': training_days,
                'summary': {
                    'symbol': symbol,
                    'source': resolved_source,
                    'start_time': training_start.strftime('%Y-%m-%d %H:%M:%S'),
                    'history_start': history_start.strftime('%Y-%m-%d %H:%M:%S'),
                    'history_end': training_start.strftime('%Y-%m-%d %H:%M:%S'),
                    'history_years': history_years,
                },
            }
        except Exception as error:
            failures.append(f'{requested_source or "auto"}: {error}')
    raise ValueError(
        f'no single crypto source has complete history and training data for {symbol}: '
        + '; '.join(failures)
    )


def _prepare_crypto_history_job(user, payload, progress_callback, cancel_check):
    del user
    history_years = _parse_crypto_history_years(payload)
    training_days = _crypto_training_days(payload)
    mode = (payload or {}).get('mode') or 'specified'
    if mode != 'random':
        symbol = _normalize_crypto_symbol((payload or {}).get('symbol'))
        if not symbol:
            raise ValueError('crypto symbol is required')
        training_start = _parse_crypto_timestamp((payload or {}).get('start_time'))
        return _crypto_prepare_candidate(
            symbol=symbol,
            training_start=training_start,
            training_days=training_days,
            history_years=history_years,
            preferred_source=(payload or {}).get('source'),
            progress_callback=progress_callback,
            cancel_check=cancel_check,
            history_months=(payload or {}).get('history_months'),
            history_start=(payload or {}).get('history_start'),
        )

    last_error = None
    for _ in range(10):
        if cancel_check is not None and cancel_check():
            raise ValueError('crypto history preparation cancelled')
        prepare_days = training_days if training_days is not None else 365
        training_start = _random_crypto_timestamp(
            (payload or {}).get('date_start', '2024-01-01'),
            (payload or {}).get('date_end', datetime.now(timezone.utc).date().isoformat()),
            prepare_days,
        )
        context_start = training_start - timedelta(days=30)
        range_end = training_start + timedelta(days=prepare_days, minutes=-1)
        try:
            instrument = _get_crypto_universe().select_random(
                start=context_start,
                end=range_end,
                max_retries=10,
            )
            return _crypto_prepare_candidate(
                symbol=instrument.symbol,
                training_start=training_start,
                training_days=training_days,
                history_years=history_years,
                preferred_source=getattr(instrument, 'source', None),
                progress_callback=progress_callback,
                cancel_check=cancel_check,
            )
        except Exception as error:
            last_error = error
    raise ValueError(
        f'no crypto instrument has complete data for the requested range: {last_error}'
    )


def _random_crypto_timestamp(date_start, date_end, training_days):
    start = datetime.fromisoformat(str(date_start)).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(str(date_end)).replace(tzinfo=timezone.utc, hour=23, minute=59)
    effective_days = training_days if training_days is not None else 365
    latest = end - timedelta(days=max(effective_days, 1) - 1)
    if latest < start:
        raise ValueError('crypto random date range is shorter than the requested training days')
    slots = int((latest - start).total_seconds() // 60)
    return start + timedelta(minutes=1 * random.randint(0, max(slots, 0)))


def _start_crypto_training(*, user, mode, period, initial_capital, training_id, payload, max_training_days):
    from backend.crypto.session import CryptoReplaySession

    history_years = _parse_crypto_history_years(payload)
    training_days = _crypto_training_days(payload, max_training_days)
    prepare_id = str(payload.get('history_prepare_id') or '').strip()
    if prepare_id:
        prepared = _get_crypto_history_prepare_manager().consume(prepare_id, user)
        _crypto_history_prepare_users.pop(prepare_id, None)
    else:
        synchronous_payload = dict(payload)
        synchronous_payload['mode'] = mode
        synchronous_payload['history_years'] = history_years
        synchronous_payload['max_training_days'] = training_days
        prepared = _prepare_crypto_history_job(
            user,
            synchronous_payload,
            progress_callback=lambda progress: None,
            cancel_check=lambda: False,
        )

    symbol = prepared['symbol']
    bundle = prepared['bundle']
    instrument = prepared['instrument']
    training_start = prepared['training_start']
    context_start = prepared['context_start']
    range_end = prepared['range_end']
    history_start = prepared['history_start']
    history_end = min(prepared['history_end'], training_start)
    history_frame = prepared['history_frame'].copy()
    history_frame['timestamp'] = pd.to_datetime(history_frame['timestamp'], utc=True)
    history_frame = history_frame.loc[
        history_frame['timestamp'] <= pd.Timestamp(training_start)
    ].drop_duplicates('timestamp', keep='last').sort_values('timestamp').reset_index(drop=True)
    session = CryptoReplaySession(
        bundle.trade_bars,
        initial_time=training_start,
        symbol=symbol,
        source=bundle.source,
        active_period=period,
        max_training_days=training_days,
    )
    snapshot = session.snapshot(max_bars=CRYPTO_PERIOD_SNAPSHOT_BAR_LIMIT)
    training = {
        'id': training_id,
        'user': user,
        'market_type': MARKET_TYPE_CRYPTO_PERPETUAL,
        'data_mode': DATA_MODE_CRYPTO_5M,
        'symbol': symbol,
        'stock_code': symbol,
        'source': bundle.source,
        'data_source': bundle.source,
        'period': period,
        'initial_period': period,
        'mode': mode,
        'start_date': training_start.date().isoformat(),
        'training_start': training_start.strftime('%Y-%m-%d %H:%M:%S'),
        'training_end': range_end.strftime('%Y-%m-%d %H:%M:%S'),
        'max_training_days': training_days,
        'history_years': history_years,
        'initial_capital': float(initial_capital),
        'leverage': int(payload.get('leverage', 5) or 5),
        'crypto_session': session,
        'crypto_bundle': bundle,
        'instrument': instrument,
        'status': 'active',
        'created_at': datetime.now(timezone.utc),
        '_crypto_history_start': history_start,
        '_crypto_history_end': history_end,
        '_crypto_chart_window_start': history_start,
        '_crypto_chart_window_end': history_end,
        '_crypto_chart_window_has_earlier': False,
        '_crypto_chart_base_frame': history_frame,
    }
    active_trainings[training_id] = training
    _initialize_crypto_futures(training)
    user_manager.start_training_session(user, {
        'session_id': training_id,
        'stock_code': symbol,
        'stock_name': symbol,
        'start_date': training_start.date().isoformat(),
        'mode': mode,
        'initial_capital': float(initial_capital),
        'commission_settings': {
            'simulator_type': 'isolated_futures',
            'leverage': int(payload.get('leverage', 5) or 5),
            'quote_currency': 'USDT',
        },
    })
    _checkpoint_crypto_futures(training)
    chart_snapshot = _crypto_extended_period_snapshot(
        training,
        period,
        snapshot,
        history_start,
        history_end,
    )
    return jsonify({
        'id': training_id,
        'training_id': training_id,
        'market_type': MARKET_TYPE_CRYPTO_PERPETUAL,
        'data_mode': DATA_MODE_CRYPTO_5M,
        'symbol': symbol,
        'source': bundle.source,
        'leverage': training['leverage'],
        'period': period,
        'training_start': training['training_start'],
        'training_end': training['training_end'],
        'history_years': history_years,
        'history_start': history_start.strftime('%Y-%m-%d %H:%M:%S'),
        'history_end': history_end.strftime('%Y-%m-%d %H:%M:%S'),
        'window_start': history_start.strftime('%Y-%m-%d %H:%M:%S'),
        'window_end': history_end.strftime('%Y-%m-%d %H:%M:%S'),
        'has_earlier': False,
        'has_later': False,
        'context_kline_data': chart_snapshot['kline_data'],
        'context_volume_data': chart_snapshot['volume_data'],
        'trade_markers': [],
        **chart_snapshot,
    })


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

        market_type = data.get('market_type', MARKET_TYPE_A_SHARE)
        data_mode = data.get('data_mode')
        if market_type == MARKET_TYPE_CRYPTO_PERPETUAL or data_mode == DATA_MODE_CRYPTO_5M:
            if period not in VALID_CRYPTO_PERIODS:
                return jsonify({'error': f'unsupported crypto period: {period}'}), 400
            try:
                data['history_years'] = _parse_crypto_history_years(data)
            except ValueError as error:
                return jsonify({'error': str(error)}), 400
            training_id = f"{user}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                return _start_crypto_training(
                    user=user,
                    mode=mode,
                    period=period,
                    initial_capital=initial_capital,
                    training_id=training_id,
                    payload=data,
                    max_training_days=max_training_days,
                )
            except ValueError as error:
                return jsonify({'error': str(error)}), 400

        # 新增: 可选 data_mode 参数 ('legacy_daily' | 'intraday_30m')
        # 未传时保持 legacy_daily；intraday 必须显式声明。
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

        if _is_crypto_session(training):
            return _crypto_get_data(training)

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
        ma_periods_str = request.args.get('ma_periods', '10,20,40,80,160')
        try:
            ma_periods = [int(p) for p in ma_periods_str.split(',') if p.strip()]
        except ValueError:
            ma_periods = [10, 20, 40, 80, 160]
            
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

        if _is_crypto_session(training):
            return _crypto_next(training)

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
        data = request.get_json() or {}
        period = data.get('period')
        if not period:
            return jsonify({'error': '缺少 period 参数'}), 400
        if _is_crypto_session(training):
            request_id = data.get('request_id')
            if request_id is not None:
                # 容错：前端预取会用 'prefetch-<n>' 字符串 ID，视为预取请求不参与主计数器
                try:
                    request_id = int(request_id)
                except (TypeError, ValueError):
                    request_id = None
            range_start = data.get('range_start')
            range_end = data.get('range_end')
            visible_start = data.get('visible_start')
            visible_end = data.get('visible_end')
            if range_start is not None:
                range_start = datetime.fromtimestamp(float(range_start), tz=timezone.utc)
            if range_end is not None:
                range_end = datetime.fromtimestamp(float(range_end), tz=timezone.utc)
            if visible_start is not None:
                visible_start = datetime.fromtimestamp(float(visible_start), tz=timezone.utc)
            if visible_end is not None:
                visible_end = datetime.fromtimestamp(float(visible_end), tz=timezone.utc)
            return _crypto_set_period(
                training, period, request_id=request_id,
                range_start=range_start, range_end=range_end,
                visible_start=visible_start, visible_end=visible_end,
                compact_chart=bool(data.get('compact_chart')),
            )
        if not _is_intraday_session(training):
            return jsonify({'error': '该会话不支持周期切换 (仅 intraday_30m 模式)'}), 400

        return _intraday_set_period(training, period)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/<training_id>/chart-window', methods=['GET'])
def get_training_chart_window(training_id):
    try:
        training = active_trainings.get(training_id)
        if not training:
            return jsonify({'error': '训练会话不存在'}), 404
        if _is_crypto_session(training):
            from backend.crypto.chart_window import CryptoChartWindowService

            snapshot = training['crypto_session'].snapshot()
            current_time = datetime.fromisoformat(snapshot['current_time']).replace(tzinfo=timezone.utc)
            requested_period = request.args.get('period', snapshot['active_period'])
            requested_start = _parse_datetime_arg('range_start').replace(tzinfo=timezone.utc)
            requested_end = _parse_datetime_arg('range_end').replace(tzinfo=timezone.utc)
            runtime_start = training.get('_crypto_history_start')
            runtime_end = training.get('_crypto_history_end') or current_time
            runtime_frame = training.get('_crypto_chart_base_frame')
            if (
                runtime_frame is not None
                and not runtime_frame.empty
                and runtime_start is not None
                and requested_start >= runtime_start
                and requested_end <= runtime_end
            ):
                payload = _crypto_extended_period_snapshot(
                    training,
                    requested_period,
                    snapshot,
                    requested_start,
                    requested_end,
                )
                payload.update({
                    'market_type': MARKET_TYPE_CRYPTO_PERPETUAL,
                    'data_mode': DATA_MODE_CRYPTO_5M,
                    'training_start': training['training_start'],
                    'training_end': training['training_end'],
                    'trade_markers': training.get('trade_markers', []),
                })
                return jsonify(payload)
            result = CryptoChartWindowService(_get_crypto_data_service()).load(
                symbol=training['symbol'],
                source=training['source'],
                period=requested_period,
                range_start=requested_start,
                range_end=requested_end,
                current_time=current_time,
                read_only=False,
            )
            previous_start = training.get('_crypto_chart_window_start')
            previous_end = training.get('_crypto_chart_window_end')
            training['_crypto_chart_window_start'] = (
                result.window_start if previous_start is None
                else min(previous_start, result.window_start)
            )
            training['_crypto_chart_window_end'] = max(
                value for value in (previous_end, result.window_end, current_time)
                if value is not None
            )
            training['_crypto_chart_window_has_earlier'] = result.has_earlier
            training.pop('_crypto_period_window_cache', None)
            existing_base = training.get('_crypto_chart_base_frame')
            result_base = getattr(result, 'base_bars', None)
            if result_base is not None:
                if existing_base is None or existing_base.empty:
                    training['_crypto_chart_base_frame'] = result_base
                else:
                    combined = pd.concat([existing_base, result_base], ignore_index=True)
                    combined['timestamp'] = pd.to_datetime(combined['timestamp'], utc=True)
                    training['_crypto_chart_base_frame'] = (
                        combined.drop_duplicates('timestamp', keep='last')
                        .sort_values('timestamp')
                        .reset_index(drop=True)
                    )
            payload = result.to_dict()
            payload.update({
                'market_type': MARKET_TYPE_CRYPTO_PERPETUAL,
                'data_mode': DATA_MODE_CRYPTO_5M,
                'training_start': training['training_start'],
                'training_end': training['training_end'],
                'current_time': snapshot['current_time'],
                'trade_markers': training.get('trade_markers', []),
            })
            return jsonify(payload)
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
        ma_periods_str = request.args.get('ma_periods', '10,20,40,80,160')
        try:
            ma_periods = [int(p) for p in ma_periods_str.split(',') if p.strip()]
        except ValueError:
            ma_periods = [10, 20, 40, 80, 160]
            
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
        ma_periods_str = request.args.get('ma_periods', '10,20,40,80,160')
        try:
            ma_periods = [int(p) for p in ma_periods_str.split(',') if p.strip()]
        except ValueError:
            ma_periods = [10, 20, 40, 80, 160]
            
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

@app.route('/api/training/<training_id>/fee-rates', methods=['POST'])
def update_crypto_fee_rates(training_id):
    if training_id not in active_trainings:
        return jsonify({'error': '训练会话不存在'}), 404
    training = active_trainings[training_id]
    if not _is_crypto_session(training):
        return jsonify({'error': '手续费率设置仅适用于币圈合约训练。'}), 400
    return _crypto_update_fee_rates(training, request.get_json(silent=True) or {})


@app.route('/api/training/<training_id>/trade', methods=['POST'])
def execute_trade(training_id):
    """执行交易"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        data = request.get_json()
        training = active_trainings[training_id]

        if _is_crypto_session(training):
            lock = training.setdefault('_crypto_next_lock', Lock())
            with lock:
                return _crypto_trade(training, data or {})

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

        if _is_crypto_session(training):
            return jsonify(_crypto_futures_payload(training))

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
        training = active_trainings[training_id]
        if _is_crypto_session(training):
            return jsonify(_crypto_futures_payload(training)['pending_orders'])
        return jsonify(_pending_orders_payload(training))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/<training_id>/orders/<order_id>', methods=['DELETE'])
def cancel_pending_order(training_id, order_id):
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        training = active_trainings[training_id]
        if _is_crypto_session(training):
            lock = training.setdefault('_crypto_next_lock', Lock())
            with lock:
                order_book = training['futures_executor'].engine.order_book
                normalized_order_id = str(order_id)
                order = next(
                    (candidate for candidate in order_book.orders if candidate.order_id == normalized_order_id),
                    None,
                )
                cancelled = order_book.cancel_order(
                    normalized_order_id, training['crypto_session'].clock.current_time,
                )
                if cancelled:
                    _checkpoint_crypto_futures(training)
                pending_orders = _crypto_futures_payload(training)['pending_orders']
            if not cancelled:
                if order is None:
                    return jsonify({
                        'error': '订单不存在，挂单列表已刷新。',
                        'code': 'order_not_found',
                        'pending_orders': pending_orders,
                    }), 404
                return jsonify({
                    'error': '订单已成交或已撤销，挂单列表已刷新。',
                    'code': 'order_inactive',
                    'order_status': order.status,
                    'pending_orders': pending_orders,
                }), 409
            return jsonify({
                'success': True,
                'order_id': normalized_order_id,
                'order_status': 'cancelled',
                'pending_orders': pending_orders,
            })
        order_manager = training.get('order_manager')
        if not order_manager or not order_manager.cancel_order(order_id):
            return jsonify({'error': '挂单不存在或已结束'}), 404
        return jsonify({
            'success': True,
            'pending_orders': _pending_orders_payload(active_trainings[training_id])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/<training_id>/orders/<order_id>', methods=['PUT'])
@app.route('/api/training/<training_id>/orders/<order_id>/modify', methods=['POST', 'PUT'])
def modify_pending_order(training_id, order_id):
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        training = active_trainings[training_id]
        payload = request.get_json() or {}
        new_price = payload.get('price')
        if new_price is None:
            return jsonify({'error': 'price is required'}), 400

        if _is_crypto_session(training):
            lock = training.setdefault('_crypto_next_lock', Lock())
            with lock:
                order_book = training['futures_executor'].engine.order_book
                normalized_order_id = str(order_id)
                updated_order = order_book.modify_order_price(
                    normalized_order_id,
                    new_price,
                    training['crypto_session'].clock.current_time,
                )
                if updated_order:
                    _checkpoint_crypto_futures(training)
                futures_payload = _crypto_futures_payload(training)
                pending_orders = futures_payload['pending_orders']
            if not updated_order:
                return jsonify({
                    'error': '订单不存在或已不可修改',
                    'code': 'order_not_modifiable',
                    'pending_orders': pending_orders,
                }), 404
            return jsonify({
                'success': True,
                'order_id': normalized_order_id,
                'order': updated_order.to_dict(),
                'pending_orders': pending_orders,
            })

        return jsonify({'error': 'A股暂不支持拖拽改单'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/<training_id>/trade_records', methods=['GET'])
def get_trade_records(training_id):
    """获取最新交易记录明细"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        if _is_crypto_session(training):
            return jsonify(_crypto_futures_payload(training)['fills'])
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

        if _is_crypto_session(training):
            return _crypto_end(training, training_id)

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
        print(f"[end_training] 结束训练失败 training_id={training_id}", file=sys.stderr)
        traceback.print_exc()
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

        if _is_crypto_session(training):
            return _crypto_reset(training)

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
        'active_trainings': len(active_trainings),
        'cloud_state_enabled': cloud_user_store.enabled,
        'cloud_state_ready': cloud_state_ready,
        'cloud_state_error': cloud_state_last_error,
        'cloud_user_count': len(user_manager.get_users()),
    })

if __name__ == '__main__':
    # 确保数据目录存在
    os.makedirs('../data', exist_ok=True)
    os.makedirs('../users', exist_ok=True)
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=True)
