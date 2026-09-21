"""
A股实时行情路由模块 (A-Share Live Blueprint)
提供股票搜索、分时K线数据拉取、实时快照轮询 API
"""
from flask import Blueprint, jsonify, request
from backend.services.ashare_live_service import (
    search_stocks,
    get_minute_klines,
    get_realtime_snapshot,
    get_batch_snapshots
)

ashare_live_bp = Blueprint('ashare_live', __name__, url_prefix='/api/ashare/live')


@ashare_live_bp.route('/search', methods=['GET'])
def search():
    """
    根据关键词搜索股票：/api/ashare/live/search?q=600519
    """
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 10)), 20)
    if not query:
        return jsonify([])
    results = search_stocks(query, limit=limit)
    return jsonify(results)


@ashare_live_bp.route('/kline', methods=['GET'])
def kline():
    """
    获取分时 K 线：/api/ashare/live/kline?symbol=600519&period=1m&limit=240
    """
    symbol = request.args.get('symbol', '').strip()
    if not symbol:
        return jsonify({"error": "缺少 symbol 参数"}), 400
    period = request.args.get('period', '1m').strip()
    limit = min(int(request.args.get('limit', 240)), 1000)
    data = get_minute_klines(symbol, period=period, limit=limit)
    return jsonify(data)


@ashare_live_bp.route('/snapshot', methods=['GET'])
def snapshot():
    """
    获取单只股票实时行情快照：/api/ashare/live/snapshot?symbol=600519
    """
    symbol = request.args.get('symbol', '').strip()
    if not symbol:
        return jsonify({"error": "缺少 symbol 参数"}), 400
    data = get_realtime_snapshot(symbol)
    return jsonify(data)


@ashare_live_bp.route('/batch', methods=['GET'])
def batch():
    """
    获取多只自选股票的实时批量行情：/api/ashare/live/batch?symbols=600519,300750,002594
    """
    raw_symbols = request.args.get('symbols', '').strip()
    if not raw_symbols:
        return jsonify([])
    symbols_list = [s.strip() for s in raw_symbols.split(',') if s.strip()]
    data = get_batch_snapshots(symbols_list)
    return jsonify(data)

