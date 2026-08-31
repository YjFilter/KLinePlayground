"""KLinePlayground - Crypto Perpetual Markets & Instruments Blueprint
(Migrated from app_enhanced.py by codemod; handlers access shared
state late-bound via `import backend.app_enhanced as ae`.)
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timezone

crypto_bp = Blueprint('crypto_routes', __name__)

_app_context = {}

def init_crypto_routes(crypto_service_getter=None):
    _app_context['get_crypto_service'] = crypto_service_getter

@crypto_bp.route('/api/crypto/universe', methods=['GET'])
def get_crypto_universe():
    try:
        from backend.crypto.universe import DEFAULT_CRYPTO_UNIVERSE
        return jsonify({
            'universe': [item.to_dict() if hasattr(item, 'to_dict') else dict(item) for item in DEFAULT_CRYPTO_UNIVERSE]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@crypto_bp.route('/api/crypto/instruments', methods=['GET'])
def get_crypto_instruments():
    import backend.app_enhanced as ae
    try:
        query = request.args.get('query', '')
        limit = min(max(int(request.args.get('limit', 20)), 1), 100)
        instruments = ae._get_crypto_universe().search(query=query, limit=limit)
        return jsonify({'instruments': [ae._serialize_crypto_instrument(item) for item in instruments]})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 503

@crypto_bp.route('/api/crypto/sources/status', methods=['GET'])
def get_crypto_source_status():
    import backend.app_enhanced as ae
    try:
        return jsonify({'sources': ae._crypto_source_status_payload()})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 503

@crypto_bp.route('/api/crypto/data/offline_status', methods=['GET'])
def get_crypto_offline_status():
    try:
        from backend.crypto.data_manager import scan_crypto_offline_status
        return jsonify(scan_crypto_offline_status())
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@crypto_bp.route('/api/crypto/data/download', methods=['POST'])
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

@crypto_bp.route('/api/crypto/history/prepare', methods=['POST'])
def prepare_crypto_history():
    import backend.app_enhanced as ae
    try:
        payload = request.get_json() or {}
        user = str(payload.get('user') or '').strip()
        if not user:
            return jsonify({'error': 'user is required'}), 400
        payload = dict(payload)
        payload['history_years'] = ae._parse_crypto_history_years(payload)
        # 临时诊断日志：打印完整 payload，便于排查"start must not be after end"
        try:
            with open('_history_prepare_debug.log', 'a', encoding='utf-8') as debug_handle:
                debug_handle.write(f"[{datetime.now(timezone.utc).isoformat()}] POST payload={payload}\n")
        except Exception:
            pass
        job = ae._get_crypto_history_prepare_manager().create(user, payload)
        ae._crypto_history_prepare_users[job['job_id']] = user
        return jsonify(_crypto_history_prepare_payload(job)), 202
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    except Exception as error:
        return jsonify({'error': str(error)}), 503

@crypto_bp.route('/api/crypto/history/prepare/<job_id>', methods=['GET'])
def get_crypto_history_prepare(job_id):
    import backend.app_enhanced as ae
    try:
        owner = _crypto_history_prepare_owner(job_id)
        job = ae._get_crypto_history_prepare_manager().get(job_id, owner)
        return jsonify(_crypto_history_prepare_payload(job))
    except Exception as error:
        return jsonify({'error': str(error)}), 404

@crypto_bp.route('/api/crypto/history/prepare/<job_id>', methods=['DELETE'])
def cancel_crypto_history_prepare(job_id):
    import backend.app_enhanced as ae
    try:
        owner = _crypto_history_prepare_owner(job_id)
        job = ae._get_crypto_history_prepare_manager().cancel(job_id, owner)
        return jsonify(_crypto_history_prepare_payload(job))
    except Exception as error:
        return jsonify({'error': str(error)}), 404

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
    import backend.app_enhanced as ae
    requested_user = request.args.get('user')
    owner = ae._crypto_history_prepare_users.get(str(job_id))
    if requested_user and owner and requested_user != owner:
        raise ValueError('history prepare job not found')
    if not owner:
        raise ValueError('history prepare job not found')
    return owner
