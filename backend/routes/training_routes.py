"""KLinePlayground - Training Lifecycle & Replay Routes Blueprint
(Migrated from app_enhanced.py by codemod; handlers access shared
state late-bound via `import backend.app_enhanced as ae`.)
"""
from flask import Blueprint, jsonify, request
from backend.kline_processor_enhanced import KLineProcessorEnhanced
from backend.order_manager import PendingOrderManager
from backend.crypto.futures_orders import FuturesOrderError
from backend.trade_simulator_enhanced import TradeSimulatorEnhanced
import base64
from datetime import datetime, timezone
import json
import os
import pandas
import requests
import sys
from threading import Lock
import traceback

training_bp = Blueprint('training_routes', __name__)

_app_context = {}

def init_training_routes(active_trainings_dict, user_manager_instance):
    _app_context['active_trainings'] = active_trainings_dict
    _app_context['user_manager'] = user_manager_instance

@training_bp.route('/api/training/active', methods=['GET'])
def get_active_trainings():
    trainings = _app_context.get('active_trainings', {})
    return jsonify({
        'count': len(trainings),
        'active_ids': list(trainings.keys())
    })

@training_bp.route('/api/training/start', methods=['POST'])
def start_training():
    """开始新的训练"""
    import backend.app_enhanced as ae
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

        market_type = data.get('market_type', ae.MARKET_TYPE_A_SHARE)
        data_mode = data.get('data_mode')
        if market_type == ae.MARKET_TYPE_CRYPTO_PERPETUAL or data_mode == ae.DATA_MODE_CRYPTO_5M:
            if period not in ae.VALID_CRYPTO_PERIODS:
                return jsonify({'error': f'unsupported crypto period: {period}'}), 400
            try:
                data['history_years'] = ae._parse_crypto_history_years(data)
            except ValueError as error:
                return jsonify({'error': str(error)}), 400
            training_id = f"{user}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                return ae._start_crypto_training(
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
        resolved_data_mode = ae._resolve_data_mode(data_mode, period)

        # 仅 intraday_30m 模式强制校验 period；legacy_daily 保持原有宽容行为
        if resolved_data_mode == ae.DATA_MODE_INTRADAY_30M and period not in ae.VALID_INTRADAY_PERIODS:
            return jsonify({'error': f'不支持的 intraday 周期: {period}'}), 400

        # 创建训练会话
        training_id = f"{user}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # === intraday_30m 分支: 基于 30 分钟底座的多周期回放 ===
        if resolved_data_mode == ae.DATA_MODE_INTRADAY_30M:
            return ae._start_intraday_training(
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
                stock_code, start_date = ae.data_manager.get_random_stock(
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
        validation_error = ae.data_manager.get_training_validation_error(
            stock_code,
            start_date,
            source=data_source,
            interval=period,
        )
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # 创建增强版K线处理器和交易模拟器
        kline_processor = KLineProcessorEnhanced(ae.data_manager, stock_code, start_date, source=data_source, interval=period, max_training_bars=max_bars)
        trade_simulator = TradeSimulatorEnhanced(user, initial_capital, stock_code)
        trade_simulator.session_id = training_id
        
        # 获取用户设置并应用到交易模拟器
        user_config = ae.user_manager.get_user_config(user)
        if user_config and 'settings' in user_config:
            settings = user_config['settings']
            trade_simulator.set_commission_settings(
                settings.get('commission_rate', 0.0003),
                settings.get('min_commission', 5.0),
                settings.get('stamp_tax_rate', 0.001)
            )
        
        # 存储训练会话
        ae.active_trainings[training_id] = {
            'user': user,
            'stock_code': stock_code,
            'start_date': start_date,
            'kline_processor': kline_processor,
            'trade_simulator': trade_simulator,
            'order_manager': PendingOrderManager(),
            'mode': mode,
            'data_source': data_source,
            'period': period,
            'data_mode': ae.DATA_MODE_LEGACY_DAILY,
            'created_at': datetime.now()
        }
        ae.user_manager.start_training_session(user, {
            'session_id': training_id,
            'stock_code': stock_code,
            'stock_name': ae.data_manager.get_stock_name(stock_code),
            'start_date': start_date,
            'mode': mode,
            'initial_capital': initial_capital,
            'commission_settings': {
                'commission_rate': trade_simulator.commission_rate,
                'min_commission': trade_simulator.min_commission,
                'stamp_tax_rate': trade_simulator.stamp_tax_rate,
            }
        })
        
        ae._update_api_info(user=user)
        
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

@training_bp.route('/api/training/<training_id>/data', methods=['GET'])
def get_training_data(training_id):
    """获取训练数据"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404

        training = ae.active_trainings[training_id]

        if ae._is_crypto_session(training):
            return ae._crypto_get_data(training)

        # === intraday_30m 分支: 返回当前快照，不推进回放状态 ===
        if ae._is_intraday_session(training):
            return ae._intraday_get_data(training)

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
        stock_name = ae.data_manager.get_stock_name(training['stock_code'])
        
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

@training_bp.route('/api/training/<training_id>/next', methods=['POST'])
def next_bar(training_id):
    """获取下一根K线"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404

        training = ae.active_trainings[training_id]

        if ae._is_crypto_session(training):
            return ae._crypto_next(training)

        # === intraday_30m 分支: 按活动周期边界推进，返回 ordered events ===
        if ae._is_intraday_session(training):
            return ae._intraday_next(training, training_id)

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
                'stock_name': ae.data_manager.get_stock_name(training['stock_code']),
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
            ae.user_manager.save_training_session(training['user'], session_data)
            
            return jsonify({
                'finished': True,
                'report': report
            })
        
        # 更新交易模拟器的当前价格和bar ID
        current_bar = kline_processor.get_current_bar()
        trade_simulator.update_current_price(current_bar['close'], current_bar['bar_id'])
        order_events = ae._process_pending_orders(training)

        current_bar['lastClose'] = kline_processor.get_previous_close()

        res = {
            'finished': False,
            'new_bar': current_bar,
            'new_volume': kline_processor.get_current_volume(),
            'progress': kline_processor.get_progress(),
            'order_events': order_events,
            'pending_orders': ae._pending_orders_payload(training),
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

@training_bp.route('/api/training/<training_id>/period', methods=['POST'])
def switch_period(training_id):
    """切换 intraday_30m 会话的显示周期，不推进时间，返回重新聚合后的快照。"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404

        training = ae.active_trainings[training_id]
        data = request.get_json() or {}
        period = data.get('period')
        if not period:
            return jsonify({'error': '缺少 period 参数'}), 400
        if ae._is_crypto_session(training):
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
            return ae._crypto_set_period(
                training, period, request_id=request_id,
                range_start=range_start, range_end=range_end,
                visible_start=visible_start, visible_end=visible_end,
                compact_chart=bool(data.get('compact_chart')),
            )
        if not ae._is_intraday_session(training):
            return jsonify({'error': '该会话不支持周期切换 (仅 intraday_30m 模式)'}), 400

        return ae._intraday_set_period(training, period)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@training_bp.route('/api/training/<training_id>/chart-window', methods=['GET'])
def get_training_chart_window(training_id):
    import backend.app_enhanced as ae
    try:
        training = ae.active_trainings.get(training_id)
        if not training:
            return jsonify({'error': '训练会话不存在'}), 404
        if ae._is_crypto_session(training):
            from backend.crypto.chart_window import CryptoChartWindowService

            snapshot = training['crypto_session'].snapshot()
            current_time = datetime.fromisoformat(snapshot['current_time']).replace(tzinfo=timezone.utc)
            requested_period = request.args.get('period', snapshot['active_period'])
            requested_start = ae._parse_datetime_arg('range_start').replace(tzinfo=timezone.utc)
            requested_end = ae._parse_datetime_arg('range_end').replace(tzinfo=timezone.utc)
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
                payload = ae._crypto_extended_period_snapshot(
                    training,
                    requested_period,
                    snapshot,
                    requested_start,
                    requested_end,
                )
                payload.update({
                    'market_type': ae.MARKET_TYPE_CRYPTO_PERPETUAL,
                    'data_mode': ae.DATA_MODE_CRYPTO_5M,
                    'training_start': training['training_start'],
                    'training_end': training['training_end'],
                    'trade_markers': training.get('trade_markers', []),
                })
                return jsonify(payload)
            result = CryptoChartWindowService(ae._get_crypto_data_service()).load(
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
                'market_type': ae.MARKET_TYPE_CRYPTO_PERPETUAL,
                'data_mode': ae.DATA_MODE_CRYPTO_5M,
                'training_start': training['training_start'],
                'training_end': training['training_end'],
                'current_time': snapshot['current_time'],
                'trade_markers': training.get('trade_markers', []),
            })
            return jsonify(payload)
        if not ae._is_intraday_session(training):
            return jsonify({'error': '该会话不支持分钟级上下文窗口'}), 400

        snapshot = training['intraday_session'].snapshot()
        result = ae._get_chart_window_service().load(
            stock_code=training['stock_code'],
            period=request.args.get('period', snapshot['active_period']),
            range_start=ae._parse_datetime_arg('range_start'),
            range_end=ae._parse_datetime_arg('range_end'),
            current_time=datetime.fromisoformat(snapshot['current_time']),
            read_only=False,
        )
        payload = ae._chart_window_payload(result, training)
        payload['trade_markers'] = ae._trade_markers(
            training['trade_simulator'].trade_history
        )
        return jsonify(payload)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@training_bp.route('/api/training/<training_id>/adjustment', methods=['POST'])
def update_adjustment(training_id):
    """更新复权设置"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        data = request.get_json()
        adjustment = data.get('adjustment', 'none')
        view_period = request.args.get('view_period', 'daily')
        
        training = ae.active_trainings[training_id]
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

@training_bp.route('/api/training/<training_id>/full_data', methods=['GET'])
def get_full_data(training_id):
    """获取完整的K线数据和指标数据"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            # 如果训练已结束且不在 active_trainings 中，尝试从历史记录重建所需的数据（这需要一些额外逻辑，目前先返回明确错误）
            # 或者我们可以考虑在 end_training 时不立即删除，而是标记为 ended，由客户端稍后清理
            return jsonify({'error': '训练会话已结束或不存在，无法获取完整走势'}), 404
        
        training = ae.active_trainings[training_id]
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

@training_bp.route('/api/training/<training_id>/fee-rates', methods=['POST'])
def update_crypto_fee_rates(training_id):
    import backend.app_enhanced as ae
    if training_id not in ae.active_trainings:
        return jsonify({'error': '训练会话不存在'}), 404
    training = ae.active_trainings[training_id]
    if not ae._is_crypto_session(training):
        return jsonify({'error': '手续费率设置仅适用于币圈合约训练。'}), 400
    return ae._crypto_update_fee_rates(training, request.get_json(silent=True) or {})

@training_bp.route('/api/training/<training_id>/trade', methods=['POST'])
def execute_trade(training_id):
    """执行交易"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        data = request.get_json()
        training = ae.active_trainings[training_id]

        if ae._is_crypto_session(training):
            lock = training.setdefault('_crypto_next_lock', Lock())
            with lock:
                return ae._crypto_trade(training, data or {})

        # === intraday_30m 分支: 使用当前 base bar 的 close，保存完整 time/display period ===
        if ae._is_intraday_session(training):
            return ae._intraday_trade(training, data)

        # === legacy_daily 分支 (原逻辑) ===
        action = data.get('action')  # 'buy' or 'sell'
        quantity = data.get('quantity')
        price_type = data.get('price_type', 'close')
        order_type = data.get('order_type', 'market')
        trigger_price = ae._parse_optional_price(data.get('trigger_price'))
        take_profit_price = ae._parse_optional_price(data.get('take_profit_price'))
        stop_loss_price = ae._parse_optional_price(data.get('stop_loss_price'))
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
                'pending_orders': ae._pending_orders_payload(training)
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
            result = ae._execute_simulated_trade(training, 'buy', quantity, current_price, current_date, reason)
        elif action == 'sell':
            result = ae._execute_simulated_trade(training, 'sell', quantity, current_price, current_date, reason)
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
                'pending_orders': ae._pending_orders_payload(training)
            })
        else:
            return jsonify({'error': result['message']}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@training_bp.route('/api/training/<training_id>/account', methods=['GET'])
def get_account_info(training_id):
    """获取账户信息"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404

        training = ae.active_trainings[training_id]

        if ae._is_crypto_session(training):
            return jsonify(ae._crypto_futures_payload(training))

        # === intraday_30m 分支: 返回兼容账户信息 + intraday 快照字段 ===
        if ae._is_intraday_session(training):
            return ae._intraday_account(training)

        # === legacy_daily 分支 (原逻辑) ===
        trade_simulator = training['trade_simulator']

        current_date = training['kline_processor'].get_current_date()

        account_info = trade_simulator.get_account_info(current_date)
        account_info['pending_orders'] = ae._pending_orders_payload(training)
        return jsonify(account_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@training_bp.route('/api/training/<training_id>/orders', methods=['GET'])
def get_pending_orders(training_id):
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        training = ae.active_trainings[training_id]
        if ae._is_crypto_session(training):
            return jsonify(ae._crypto_futures_payload(training)['pending_orders'])
        return jsonify(ae._pending_orders_payload(training))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@training_bp.route('/api/training/<training_id>/orders/<order_id>', methods=['DELETE'])
def cancel_pending_order(training_id, order_id):
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        training = ae.active_trainings[training_id]
        if ae._is_crypto_session(training):
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
                    ae._checkpoint_crypto_futures(training)
                pending_orders = ae._crypto_futures_payload(training)['pending_orders']
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
            'pending_orders': ae._pending_orders_payload(ae.active_trainings[training_id])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@training_bp.route('/api/training/<training_id>/orders/<order_id>', methods=['PUT'])
@training_bp.route('/api/training/<training_id>/orders/<order_id>/modify', methods=['POST', 'PUT'])
def modify_pending_order(training_id, order_id):
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        training = ae.active_trainings[training_id]
        payload = request.get_json() or {}
        new_price = payload.get('price')
        if new_price is None:
            return jsonify({'error': 'price is required'}), 400

        if ae._is_crypto_session(training):
            lock = training.setdefault('_crypto_next_lock', Lock())
            with lock:
                engine = training['futures_executor'].engine
                order_book = engine.order_book
                normalized_order_id = str(order_id)
                simulator = engine.simulator
                mark_price = simulator.last_mark_price or simulator.position.entry_price
                updated_order = order_book.modify_order_price(
                    normalized_order_id,
                    new_price,
                    training['crypto_session'].clock.current_time,
                    current_price=mark_price if mark_price and mark_price > 0 else None,
                )
                if updated_order:
                    ae._checkpoint_crypto_futures(training)
                futures_payload = ae._crypto_futures_payload(training)
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
    except FuturesOrderError as error:
        return jsonify({'error': error.message, 'message': error.message, 'code': error.code}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@training_bp.route('/api/training/<training_id>/trade_records', methods=['GET'])
def get_trade_records(training_id):
    """获取最新交易记录明细"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = ae.active_trainings[training_id]
        if ae._is_crypto_session(training):
            return jsonify(ae._crypto_futures_payload(training)['fills'])
        trade_simulator = training['trade_simulator']
        
        records = trade_simulator.get_trade_history_with_bar_id()
        return jsonify(records)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@training_bp.route('/api/training/<training_id>/indicators/<indicator_type>', methods=['GET'])
def get_technical_indicators(training_id, indicator_type):
    """获取技术指标数据"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = ae.active_trainings[training_id]
        kline_processor = training['kline_processor']
        view_period = request.args.get('view_period', 'daily')
        
        # 获取用户自定义的技术指标参数
        user = training['user']
        user_config = ae.user_manager.get_user_config(user)
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

@training_bp.route('/api/training/<training_id>/sync_status', methods=['GET'])
def get_sync_status(training_id):
    """获取精简同步状态"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = ae.active_trainings[training_id]
        kline_processor = training['kline_processor']
        
        return jsonify({
            'current_bar_id': kline_processor.get_current_bar_id(),
            'trade_markers_count': len(kline_processor.get_trade_markers())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@training_bp.route('/api/training/<training_id>/end', methods=['POST'])
def end_training(training_id):
    """结束训练"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404

        training = ae.active_trainings[training_id]

        if ae._is_crypto_session(training):
            return ae._crypto_end(training, training_id)

        # === intraday_30m 分支 ===
        if ae._is_intraday_session(training):
            return ae._intraday_end(training, training_id)

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
            'stock_name': ae.data_manager.get_stock_name(training['stock_code']),
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
        ae.user_manager.save_training_session(training['user'], session_data)
        
        # 清理训练会话
        # del active_trainings[training_id] # 不要立即删除，因为客户端可能还需要请求 full_data
        ae.active_trainings[training_id]['status'] = 'ended'
        
        ae._update_api_info(user=training['user'])
        
        return jsonify(report)
    except Exception as e:
        print(f"[end_training] 结束训练失败 training_id={training_id}", file=sys.stderr)
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@training_bp.route('/api/training/<training_id>/cleanup', methods=['POST'])
def cleanup_training(training_id):
    """清理已结束的训练会话"""
    import backend.app_enhanced as ae
    try:
        if training_id in ae.active_trainings:
            del ae.active_trainings[training_id]
        return jsonify({'message': '清理成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@training_bp.route('/api/training/<training_id>/reset', methods=['POST'])
def reset_training(training_id):
    """重置训练"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404

        training = ae.active_trainings[training_id]

        if ae._is_crypto_session(training):
            return ae._crypto_reset(training)

        # === intraday_30m 分支 ===
        if ae._is_intraday_session(training):
            return ae._intraday_reset(training)

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

@training_bp.route('/api/training/<training_id>/history', methods=['GET'])
def get_training_history(training_id):
    """获取训练历史记录"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = ae.active_trainings[training_id]
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

@training_bp.route('/api/training/<training_id>/chip_distribution', methods=['GET'])
def get_chip_distribution(training_id):
    """获取筹码分布（换手率衰减模型）"""
    import backend.app_enhanced as ae
    try:
        if training_id not in ae.active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
            
        kline_processor = ae.active_trainings[training_id]['kline_processor']
        view_period = request.args.get('view_period', 'daily')
        
        # 可选增加 bins 参数，如果前端要求更精细的分布
        bins = int(request.args.get('bins', 80))
        chip_dist = kline_processor.get_volume_profile(bins=bins, view_period=view_period)
        
        return jsonify(chip_dist)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@training_bp.route('/api/training/analyze_report', methods=['POST'])
def analyze_report():
    """使用AI分析复盘报告"""
    import backend.app_enhanced as ae
    try:
        data = request.get_json()
        report = data.get('report')
        user = data.get('user')
        
        if not report or not user:
            return jsonify({'error': '缺少必要的参数'}), 400
            
        user_config = ae.user_manager.get_user_config(user)
        if not user_config or not user_config.get('settings', {}).get('enable_ai_api', False):
            return jsonify({'error': '未开启AI分析功能'}), 403
            
        ai_commentary = analyze_report_with_ai(report)
        return jsonify({'ai_commentary': ai_commentary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
