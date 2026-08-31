"""KLinePlayground - User Management & Cloud State Routes Blueprint
(Migrated from app_enhanced.py by codemod; handlers access shared
state late-bound via `import backend.app_enhanced as ae`.)
"""
from flask import Blueprint, jsonify, request
from datetime import datetime

user_bp = Blueprint('user_routes', __name__)

_app_context = {}

def init_user_routes(user_manager_instance, cloud_state_instance=None):
    _app_context['user_manager'] = user_manager_instance
    _app_context['cloud_state'] = cloud_state_instance

@user_bp.route('/api/users', methods=['GET'])
def get_users():
    """获取用户列表"""
    import backend.app_enhanced as ae
    try:
        users = ae.user_manager.get_users()
        return jsonify(users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/api/users', methods=['POST'])
def create_user():
    """创建新用户"""
    import backend.app_enhanced as ae
    try:
        data = request.get_json()
        username = data.get('username')
        
        if not username:
            return jsonify({'error': '用户名不能为空'}), 400
        
        if ae.user_manager.user_exists(username):
            return jsonify({'error': '用户名已存在'}), 400
        
        ae.user_manager.create_user(username)
        return jsonify({'message': '用户创建成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/api/users/<username>', methods=['DELETE'])
def delete_user(username):
    """删除用户及其所有数据"""
    import backend.app_enhanced as ae
    try:
        if not ae.user_manager.user_exists(username):
            return jsonify({'error': '用户不存在'}), 404

        if ae.user_manager.delete_user(username):
            return jsonify({'message': '用户删除成功'})
        else:
            return jsonify({'error': '删除用户失败'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/api/users/<username>/settings', methods=['GET'])
def get_user_settings(username):
    """获取用户设置"""
    import backend.app_enhanced as ae
    try:
        config = ae.user_manager.get_user_config(username)
        if config:
            return jsonify(config.get('settings', {}))
        else:
            return jsonify({'error': '用户不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/api/users/<username>/settings', methods=['POST'])
def update_user_settings(username):
    """更新用户设置"""
    import backend.app_enhanced as ae
    try:
        data = request.get_json()
        config = ae.user_manager.get_user_config(username)
        
        if not config:
            # 如果配置不存在，先创建默认配置，防止老用户数据丢失或缺失 config.json 导致无法保存
            ae.user_manager.create_user(username)
            config = ae.user_manager.get_user_config(username)
            if not config:
                return jsonify({'error': '用户不存在且创建配置失败'}), 404
        
        if 'settings' not in config:
            config['settings'] = {}
            
        # 更新设置
        config['settings'].update(data)
        
        if ae.user_manager.update_user_config(username, config):
            return jsonify({'message': '设置更新成功'})
        else:
            return jsonify({'error': '设置更新失败'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/api/users/<username>/statistics', methods=['GET'])
def get_user_statistics(username):
    """获取用户统计信息"""
    import backend.app_enhanced as ae
    try:
        stats = ae.user_manager.get_user_statistics(username)
        if stats:
            return jsonify(stats)
        else:
            return jsonify({'error': '用户不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/api/users/<username>/history', methods=['GET'])
def get_user_training_history(username):
    import backend.app_enhanced as ae
    try:
        limit = int(request.args.get('limit', 50))
        return jsonify(ae.user_manager.get_training_history(username, limit))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/api/users/<username>/history/<session_id>', methods=['GET'])
def get_user_history_report(username, session_id):
    import backend.app_enhanced as ae
    try:
        report = ae.user_manager.get_session_report(username, session_id)
        if not report:
            return jsonify({'error': '历史训练不存在'}), 404
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/api/users/<username>/history/<session_id>/chart', methods=['GET'])
def get_user_history_chart(username, session_id):
    import backend.app_enhanced as ae
    try:
        report = ae.user_manager.get_session_report(username, session_id)
        if not report:
            return jsonify({'error': '历史训练不存在'}), 404

        report = dict(report)
        training_start = report.get('training_start') or report.get('start_date')
        training_end = report.get('training_end') or report.get('end_date')
        if training_start:
            report['training_start'] = ae._format_datetime(training_start)
        if training_end:
            report['training_end'] = ae._format_datetime(training_end)

        is_crypto = (
            report.get('market_type') == ae.MARKET_TYPE_CRYPTO_PERPETUAL
            or report.get('data_mode') == ae.DATA_MODE_CRYPTO_5M
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
        range_start = ae._parse_datetime_arg('range_start')
        range_end = ae._parse_datetime_arg('range_end')
        if range_start > range_end:
            return jsonify({'error': 'range_start 不能晚于 range_end'}), 400

        if is_crypto:
            from backend.crypto.chart_window import CryptoChartWindowService

            result = CryptoChartWindowService(ae._get_crypto_data_service()).load(
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
                'market_type': ae.MARKET_TYPE_CRYPTO_PERPETUAL,
                'data_mode': ae.DATA_MODE_CRYPTO_5M,
                'training_start': report['training_start'],
                'training_end': report['training_end'],
                'trade_markers': report.get('trade_markers') or ae._trade_markers(
                    report.get('trade_details')
                ),
            })
            return jsonify(payload)

        if report.get('data_mode', ae.DATA_MODE_LEGACY_DAILY) != ae.DATA_MODE_INTRADAY_30M:
            return jsonify(ae._legacy_history_chart_payload(
                report,
                period,
                range_start,
                range_end,
            ))

        result = ae._get_chart_window_service().load(
            stock_code=report['stock_code'],
            period=period,
            range_start=range_start,
            range_end=range_end,
            current_time=datetime.fromisoformat(report['training_end']),
            read_only=True,
        )
        payload = ae._chart_window_payload(result, report)
        payload['trade_markers'] = ae._trade_markers(report.get('trade_details'))
        return jsonify(payload)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/api/users/<username>/history/<session_id>', methods=['DELETE'])
def delete_user_history_report(username, session_id):
    import backend.app_enhanced as ae
    try:
        if ae.user_manager.delete_training_session(username, session_id):
            return jsonify({'success': True})
        return jsonify({'error': '历史训练不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/api/users/<username>/history/<session_id>/summary', methods=['POST'])
def save_user_history_summary(username, session_id):
    import backend.app_enhanced as ae
    try:
        data = request.get_json() or {}
        summary = (data.get('summary') or '').strip()
        if ae.user_manager.save_review_summary(username, session_id, summary):
            report = ae.user_manager.get_session_report(username, session_id)
            return jsonify({'success': True, 'review_summary': summary, 'report': report})
        return jsonify({'error': '历史训练不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
