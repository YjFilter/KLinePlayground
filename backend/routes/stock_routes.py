"""KLinePlayground - A-Share Stock Markets Blueprint
(Migrated from app_enhanced.py by codemod; handlers access shared
state late-bound via `import backend.app_enhanced as ae`.)
"""
from flask import Blueprint, jsonify, request

stock_bp = Blueprint('stock_routes', __name__)

_app_context = {}

def init_stock_routes(data_manager_instance=None):
    _app_context['data_manager'] = data_manager_instance

@stock_bp.route('/api/stock/intraday-dates', methods=['GET'])
def get_intraday_dates():
    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'error': 'Stock code required'}), 400
    dm = _app_context.get('data_manager')
    if dm and hasattr(dm, 'get_intraday_dates'):
        dates = dm.get_intraday_dates(code)
        return jsonify({'code': code, 'dates': dates})
    return jsonify({'code': code, 'dates': []})

@stock_bp.route('/api/data/sources', methods=['GET'])
def get_data_sources():
    """返回可选数据源与可用性。"""
    import backend.app_enhanced as ae
    try:
        return jsonify({'sources': ae.data_manager.get_available_sources()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@stock_bp.route('/api/data/stock_universe', methods=['GET'])
def get_stock_universe():
    """按市场返回股票代码列表，供批量补数使用。"""
    import backend.app_enhanced as ae
    try:
        market = request.args.get('market', 'all')
        stock_codes = ae.data_manager.get_stock_universe(market=market)
        return jsonify({
            'market': market,
            'count': len(stock_codes),
            'stock_codes': stock_codes
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@stock_bp.route('/api/data/sync', methods=['POST'])
def sync_offline_data():
    """使用在线数据源增量补充离线数据。"""
    import backend.app_enhanced as ae
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

        result = ae.data_manager.sync_offline_data(
            stock_code=stock_code,
            source=source,
            start_date=start_date,
            end_date=end_date,
            force_full=force_full,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
