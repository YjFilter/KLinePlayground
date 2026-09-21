from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from typing import Any

from .futures_models import FuturesFill, ZERO, decimal_value, timestamp_value
from .futures_simulator import FuturesSimulator


VALID_ACTIONS = {"open_long", "open_short", "close"}
VALID_ORDER_TYPES = {"market", "limit", "breakout"}


class FuturesOrderError(ValueError):
    """A user-facing futures order validation error with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class FuturesOrder:
    order_id: str
    action: str
    order_type: str
    side: str
    quantity: Decimal
    margin: Decimal
    leverage: int
    submitted_at: datetime
    limit_price: Decimal | None = None
    trigger_price: Decimal | None = None
    reduce_only: bool = False
    status: str = "active"
    filled_at: datetime | None = None
    cancelled_at: datetime | None = None
    fill_id: str | None = None
    cancel_reason: str | None = None
    reserved_margin: Decimal = ZERO
    tp_price: Decimal | None = None
    sl_price: Decimal | None = None
    parent_order_id: str | None = None
    protection_type: str | None = None
    trigger_source: str = "last_price"

    def __post_init__(self) -> None:
        self.quantity = decimal_value(self.quantity)
        self.margin = decimal_value(self.margin)
        self.limit_price = None if self.limit_price is None else decimal_value(self.limit_price)
        self.trigger_price = None if self.trigger_price is None else decimal_value(self.trigger_price)
        self.tp_price = None if self.tp_price is None else decimal_value(self.tp_price)
        self.sl_price = None if self.sl_price is None else decimal_value(self.sl_price)
        self.reserved_margin = decimal_value(self.reserved_margin)
        self.submitted_at = timestamp_value(self.submitted_at)
        if self.filled_at is not None:
            self.filled_at = timestamp_value(self.filled_at)
        if self.cancelled_at is not None:
            self.cancelled_at = timestamp_value(self.cancelled_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "action": self.action,
            "order_type": self.order_type,
            "side": self.side,
            "quantity": float(self.quantity),
            "margin": float(self.margin),
            "leverage": self.leverage,
            "submitted_at": self.submitted_at.isoformat(),
            "limit_price": None if self.limit_price is None else float(self.limit_price),
            "trigger_price": None if self.trigger_price is None else float(self.trigger_price),
            "reduce_only": self.reduce_only,
            "status": self.status,
            "filled_at": None if self.filled_at is None else self.filled_at.isoformat(),
            "cancelled_at": None if self.cancelled_at is None else self.cancelled_at.isoformat(),
            "fill_id": self.fill_id,
            "cancel_reason": self.cancel_reason,
            "reserved_margin": float(self.reserved_margin),
            "tp_price": None if self.tp_price is None else float(self.tp_price),
            "sl_price": None if self.sl_price is None else float(self.sl_price),
            "parent_order_id": self.parent_order_id,
            "protection_type": self.protection_type,
            "trigger_source": self.trigger_source,
            "role": "protective" if self.parent_order_id else "entry",
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "action": self.action,
            "order_type": self.order_type,
            "side": self.side,
            "quantity": format(self.quantity, "f"),
            "margin": format(self.margin, "f"),
            "leverage": self.leverage,
            "submitted_at": self.submitted_at.isoformat(),
            "limit_price": None if self.limit_price is None else format(self.limit_price, "f"),
            "trigger_price": None if self.trigger_price is None else format(self.trigger_price, "f"),
            "reduce_only": self.reduce_only,
            "status": self.status,
            "filled_at": None if self.filled_at is None else self.filled_at.isoformat(),
            "cancelled_at": None if self.cancelled_at is None else self.cancelled_at.isoformat(),
            "fill_id": self.fill_id,
            "cancel_reason": self.cancel_reason,
            "reserved_margin": format(self.reserved_margin, "f"),
            "tp_price": None if self.tp_price is None else format(self.tp_price, "f"),
            "sl_price": None if self.sl_price is None else format(self.sl_price, "f"),
            "parent_order_id": self.parent_order_id,
            "protection_type": self.protection_type,
            "trigger_source": self.trigger_source,
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "FuturesOrder":
        return cls(
            order_id=state["order_id"], action=state["action"], order_type=state["order_type"],
            side=state["side"], quantity=state["quantity"], margin=state["margin"],
            leverage=int(state["leverage"]), submitted_at=datetime.fromisoformat(state["submitted_at"]),
            limit_price=state.get("limit_price"), trigger_price=state.get("trigger_price"),
            reduce_only=bool(state.get("reduce_only", False)),
            status=state.get("status", "active"),
            filled_at=None if state.get("filled_at") is None else datetime.fromisoformat(state["filled_at"]),
            cancelled_at=None if state.get("cancelled_at") is None else datetime.fromisoformat(state["cancelled_at"]),
            fill_id=state.get("fill_id"), cancel_reason=state.get("cancel_reason"),
            reserved_margin=state.get("reserved_margin", ZERO),
            tp_price=state.get("tp_price"), sl_price=state.get("sl_price"),
            parent_order_id=state.get("parent_order_id"),
            protection_type=state.get("protection_type"),
            trigger_source=state.get("trigger_source", "last_price"),
        )


def _protective_priority(order: FuturesOrder) -> int:
    """同一根 K 线内的撮合顺序：止损优先于止盈（保守撮合，不美化回测）。

    引擎自建的止盈止损子单带 protection_type；用户在图上手工拖出的平仓单没有该字段，
    按订单类型推断——平仓突破单 = 止损（价格穿越触发），平仓限价单 = 止盈。
    """
    if order.protection_type == "sl":
        return 0
    if order.protection_type == "tp":
        return 1
    if order.reduce_only:
        return 0 if order.order_type == "breakout" else 1
    return 2


class FuturesOrderBook:
    def __init__(
        self,
        simulator: FuturesSimulator,
        *,
        maker_fee_rate: Decimal | int | float | str = "0",
        taker_fee_rate: Decimal | int | float | str = "0",
    ) -> None:
        self.simulator = simulator
        self.maker_fee_rate = decimal_value(maker_fee_rate)
        self.taker_fee_rate = decimal_value(taker_fee_rate)
        if min(self.maker_fee_rate, self.taker_fee_rate) < ZERO:
            raise ValueError("fee rates cannot be negative")
        self.orders: list[FuturesOrder] = []
        self.fills: list[FuturesFill] = []
        self._next_order_id = 1

    def set_fee_rates(self, *, maker_fee_rate, taker_fee_rate) -> None:
        maker = decimal_value(maker_fee_rate)
        taker = decimal_value(taker_fee_rate)
        if min(maker, taker) < ZERO:
            raise ValueError("fee rates cannot be negative")
        self.maker_fee_rate = maker
        self.taker_fee_rate = taker

    @property
    def active_orders(self) -> list[FuturesOrder]:
        return [order for order in self.orders if order.status == "active"]

    @property
    def reserved_margin(self) -> Decimal:
        return sum((order.reserved_margin for order in self.active_orders), ZERO)

    def fee_rate(self, order_type: str) -> Decimal:
        if order_type not in VALID_ORDER_TYPES:
            raise FuturesOrderError("invalid_order_type", "订单类型必须是市价、限价或突破。")
        return self.maker_fee_rate if order_type == "limit" else self.taker_fee_rate

    def _validate_pending_direction(
        self,
        *,
        action: str,
        order_type: str,
        price: Decimal,
        current_price: Decimal,
        reduce_only: bool,
    ) -> None:
        if order_type == "limit":
            if action == "open_long" and price >= current_price:
                raise FuturesOrderError("invalid_limit_direction", "开多限价必须低于当前价格。")
            if action == "open_short" and price <= current_price:
                raise FuturesOrderError("invalid_limit_direction", "开空限价必须高于当前价格。")
            # 平仓限价只能挂在"不会立刻成交"的那一侧（= 止盈侧），这是交易所的真实语义：
            # "卖出限价"的撮合条件是 high >= 限价，所以低于标记价的卖出限价属于
            # "可立即成交"的单子，下一根 K 线就会当场成交 —— 它不是止损。
            # 止损必须用突破单（价格穿越触发价才成交）。
            #   多头：限价在上 = 止盈；在下必须用 breakout 当止损
            #   空头：限价在下 = 止盈；在上必须用 breakout 当止损
            position_quantity = self.simulator.position.quantity
            if reduce_only and position_quantity > ZERO and price <= current_price:
                raise FuturesOrderError(
                    "invalid_limit_direction",
                    "平多限价必须高于当前标记价，否则会立即成交。低于标记价的止损请改用突破单。",
                )
            if reduce_only and position_quantity < ZERO and price >= current_price:
                raise FuturesOrderError(
                    "invalid_limit_direction",
                    "平空限价必须低于当前标记价，否则会立即成交。高于标记价的止损请改用突破单。",
                )
            return
        if order_type != "breakout":
            return
        if action == "open_long" and price <= current_price:
            raise FuturesOrderError("invalid_trigger_direction", "开多突破价必须高于当前价格。")
        if action == "open_short" and price >= current_price:
            raise FuturesOrderError("invalid_trigger_direction", "开空突破价必须低于当前价格。")
        if reduce_only and self.simulator.position.quantity > ZERO and price >= current_price:
            raise FuturesOrderError("invalid_trigger_direction", "平多止损触发价必须低于当前价格。")
        if reduce_only and self.simulator.position.quantity < ZERO and price <= current_price:
            raise FuturesOrderError("invalid_trigger_direction", "平空止损触发价必须高于当前价格。")

    def _validate_single_pending_entry(self, action: str) -> None:
        if any(
            order.status == "active"
            and not order.reduce_only
            and order.action == action
            and order.order_type in {"limit", "breakout"}
            for order in self.orders
        ):
            direction = "开多" if action == "open_long" else "开空"
            raise FuturesOrderError("duplicate_pending_order", f"{direction}方向已有一笔挂单，请先撤单或等待成交。")

    def max_open_margin(self, *, order_type: str, leverage: int | None = None) -> Decimal:
        selected_leverage = self.simulator.leverage if leverage is None else leverage
        self.simulator._validate_leverage(selected_leverage)
        fee_rate = self.fee_rate(order_type)
        available = max(ZERO, self.simulator.account.available_balance - self.reserved_margin)
        denominator = Decimal("1") + (Decimal(selected_leverage) * fee_rate)
        return (available / denominator).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    def submit_order(
        self,
        *,
        action: str,
        order_type: str,
        timestamp: datetime,
        current_price,
        margin=None,
        quantity=None,
        leverage: int | None = None,
        limit_price=None,
        trigger_price=None,
        tp_price=None,
        sl_price=None,
    ) -> FuturesOrder:
        if action not in VALID_ACTIONS:
            raise FuturesOrderError("invalid_action", "不支持的合约操作。")
        if order_type not in VALID_ORDER_TYPES:
            raise FuturesOrderError("invalid_order_type", "订单类型必须是市价、限价或突破。")
        submitted_at = timestamp_value(timestamp)
        current_price_value = decimal_value(current_price)
        selected_leverage = self.simulator.leverage if leverage is None else leverage
        self.simulator._validate_leverage(selected_leverage)
        if selected_leverage != self.simulator.leverage:
            if not self.simulator.position.is_flat or self.active_orders:
                raise ValueError("leverage can change only while flat without active orders")
            self.simulator.set_leverage(selected_leverage)
        reduce_only = action == "close"
        selected_limit = None
        selected_trigger = None
        if order_type == "limit":
            if limit_price is None:
                raise FuturesOrderError("missing_limit_price", "限价单必须填写限价。")
            selected_limit = decimal_value(limit_price)
            if selected_limit <= ZERO:
                raise FuturesOrderError("invalid_limit_price", "限价必须大于 0。")
        elif order_type == "breakout":
            if trigger_price is None:
                raise FuturesOrderError("missing_trigger_price", "突破单必须填写触发价。")
            selected_trigger = decimal_value(trigger_price)
            if selected_trigger <= ZERO:
                raise FuturesOrderError("invalid_trigger_price", "触发价必须大于 0。")
        pending_price = selected_limit if order_type == "limit" else selected_trigger
        if reduce_only:
            if self.simulator.position.is_flat:
                raise FuturesOrderError("no_position", "当前没有可平仓的持仓。")
            position_qty = self.simulator.position.absolute_quantity
            step = getattr(self.simulator, "quantity_step", Decimal("0.0001"))
            if quantity is not None and decimal_value(quantity) > ZERO:
                selected_qty = decimal_value(quantity)
                quantity = min(selected_qty, position_qty)
            elif margin is not None and decimal_value(margin) > ZERO and self.simulator.position.isolated_margin > ZERO:
                margin_val = decimal_value(margin)
                closing_ratio = min(Decimal("1"), margin_val / self.simulator.position.isolated_margin)
                if closing_ratio >= Decimal("0.999"):
                    quantity = position_qty
                else:
                    quantity = (position_qty * closing_ratio).quantize(step, rounding=ROUND_DOWN)
                    if quantity <= ZERO:
                        quantity = min(step, position_qty)
            else:
                quantity = position_qty

            if quantity <= ZERO:
                raise FuturesOrderError("invalid_quantity", "平仓数量必须大于 0。")

            margin_value = ZERO
            side = "sell" if self.simulator.position.quantity > ZERO else "buy"
            if order_type in {"limit", "breakout"}:
                self._validate_pending_direction(
                    action=action,
                    order_type=order_type,
                    price=pending_price,
                    current_price=current_price_value,
                    reduce_only=True,
                )
        else:
            if margin is None:
                raise FuturesOrderError("missing_margin", "开仓单必须填写保证金。")
            margin_value = decimal_value(margin)
            if margin_value <= ZERO:
                raise FuturesOrderError("invalid_margin", "保证金必须大于 0。")
            sizing_price = current_price_value if order_type == "market" else pending_price
            if order_type in {"limit", "breakout"}:
                self._validate_single_pending_entry(action)
                self._validate_pending_direction(
                    action=action,
                    order_type=order_type,
                    price=sizing_price,
                    current_price=current_price_value,
                    reduce_only=False,
                )
            try:
                quantity = self.simulator.margin_to_quantity(margin_value, selected_leverage, sizing_price)
            except ValueError as error:
                message = str(error)
                if message == "order is below minimum quantity":
                    minimum_notional = self.simulator.min_quantity * sizing_price
                    minimum_margin = (
                        minimum_notional / Decimal(selected_leverage)
                        + minimum_notional * self.fee_rate(order_type)
                    )
                    raise FuturesOrderError(
                        "min_quantity",
                        f"下单数量低于最小数量 {self.simulator.min_quantity}，当前价格和杠杆至少需要 {minimum_margin.quantize(Decimal('0.01'), rounding=ROUND_UP)} USDT 保证金（含预估手续费）。",
                    ) from error
                if message == "order is below minimum notional":
                    raise FuturesOrderError(
                        "min_notional",
                        f"订单名义价值低于最低要求 {self.simulator.min_notional} USDT，请提高保证金或调整价格。",
                    ) from error
                raise
            side = "buy" if action == "open_long" else "sell"
            fee_rate = self.fee_rate(order_type)
            current_quantity = self.simulator.position.quantity
            signed_quantity = quantity if side == "buy" else -quantity
            if current_quantity == ZERO or current_quantity * signed_quantity > ZERO:
                required_reservation = quantity * sizing_price / Decimal(selected_leverage) + quantity * sizing_price * fee_rate
                if required_reservation + self.reserved_margin > self.simulator.account.available_balance:
                    raise ValueError("insufficient available margin including fee")
            else:
                closing_quantity = min(quantity, abs(current_quantity))
                opening_quantity = max(ZERO, quantity - abs(current_quantity))
                required_reservation = ZERO
                if opening_quantity > ZERO:
                    released_margin = self.simulator.position.isolated_margin * closing_quantity / abs(current_quantity)
                    direction = Decimal("1") if current_quantity > ZERO else Decimal("-1")
                    realized_pnl = closing_quantity * (sizing_price - self.simulator.position.entry_price) * direction
                    closing_fee = closing_quantity * sizing_price * fee_rate
                    projected_balance = max(ZERO, self.simulator.account.balance + realized_pnl - closing_fee)
                    projected_used_margin = max(ZERO, self.simulator.account.used_margin - released_margin)
                    projected_available = max(ZERO, projected_balance - projected_used_margin - self.reserved_margin)
                    opening_requirement = opening_quantity * sizing_price / Decimal(selected_leverage) + opening_quantity * sizing_price * fee_rate
                    if opening_requirement <= projected_available:
                        required_reservation = opening_requirement
        # --- 止盈止损验证 ---
        selected_tp = None
        selected_sl = None
        if tp_price is not None or sl_price is not None:
            if reduce_only:
                raise FuturesOrderError("invalid_tp_sl", "止盈止损只能设置在开仓单上。")
            if tp_price is not None:
                selected_tp = decimal_value(tp_price)
                if selected_tp <= ZERO:
                    raise FuturesOrderError("invalid_tp_sl", "止盈价必须大于 0。")
            if sl_price is not None:
                selected_sl = decimal_value(sl_price)
                if selected_sl <= ZERO:
                    raise FuturesOrderError("invalid_tp_sl", "止损价必须大于 0。")
            if side == "buy":  # open_long
                if selected_tp is not None and selected_tp <= sizing_price:
                    raise ValueError("tp_price must be above entry price for long")
                if selected_sl is not None and selected_sl >= sizing_price:
                    raise ValueError("sl_price must be below entry price for long")
            else:  # open_short
                if selected_tp is not None and selected_tp >= sizing_price:
                    raise ValueError("tp_price must be below entry price for short")
                if selected_sl is not None and selected_sl <= sizing_price:
                    raise ValueError("sl_price must be above entry price for short")
        order = FuturesOrder(
            order_id=f"order-{self._next_order_id}",
            action=action,
            order_type=order_type,
            side=side,
            quantity=quantity,
            margin=margin_value,
            leverage=selected_leverage,
            submitted_at=submitted_at,
            limit_price=selected_limit,
            trigger_price=selected_trigger,
            reduce_only=reduce_only,
            reserved_margin=ZERO if reduce_only else required_reservation,
            tp_price=selected_tp,
            sl_price=selected_sl,
        )
        self._next_order_id += 1
        self.orders.append(order)
        if order_type == "market":
            self._fill_order(order, current_price_value, submitted_at, "taker")
        return order

    def cancel_order(self, order_id: str, timestamp: datetime, reason: str = "user_cancelled") -> bool:
        for order in self.orders:
            if order.order_id == order_id and order.status == "active":
                order.status = "cancelled"
                order.cancelled_at = timestamp_value(timestamp)
                order.cancel_reason = reason
                return True
        return False

    def cancel_all(self, timestamp: datetime) -> list[FuturesOrder]:
        cancelled = []
        for order in self.active_orders:
            if self.cancel_order(order.order_id, timestamp, "cancel_all"):
                cancelled.append(order)
        return cancelled

    def _retarget_reduce_only_order(self, order: FuturesOrder, price: Decimal, current_price: Decimal) -> None:
        """按新价位重定平仓单的类型：止盈（限价，等价格到达）↔ 止损（突破，价格穿越才成交）。

        图上把一条保护线拖到"会立即成交"的一侧时必须改判类型，否则下一根 K 线就会当场成交
        （用户反馈：止损线还没到就被平仓）。多头价在上=止盈、在下=止损；空头相反。
        """
        position_quantity = self.simulator.position.quantity
        if position_quantity == ZERO:
            raise FuturesOrderError("no_position", "当前没有可平仓的持仓。")
        if price == current_price:
            raise FuturesOrderError(
                "invalid_limit_direction",
                "保护价不能等于当前标记价，请拖到其他价位（高于标记价为止盈、低于为止损）。",
            )
        is_take_profit = price > current_price if position_quantity > ZERO else price < current_price
        order.order_type = "limit" if is_take_profit else "breakout"
        order.protection_type = "tp" if is_take_profit else "sl"
        order.limit_price = price if is_take_profit else None
        order.trigger_price = None if is_take_profit else price
        order.tp_price = price if is_take_profit else None
        order.sl_price = None if is_take_profit else price

    def _validate_amend_direction(self, order: FuturesOrder, price: Decimal, current_price: Decimal) -> None:
        """开仓挂单改价时，不允许改到"会立即成交"的一侧（避免静默变成市价单）。"""
        if order.reduce_only or order.protection_type:
            return
        if order.order_type == "limit":
            if order.side == "buy" and price >= current_price:
                raise FuturesOrderError("invalid_limit_direction", "买入限价必须低于当前标记价，否则会立即成交。")
            if order.side == "sell" and price <= current_price:
                raise FuturesOrderError("invalid_limit_direction", "卖出限价必须高于当前标记价，否则会立即成交。")
        elif order.order_type == "breakout":
            if order.side == "buy" and price <= current_price:
                raise FuturesOrderError("invalid_trigger_direction", "买入突破价必须高于当前标记价。")
            if order.side == "sell" and price >= current_price:
                raise FuturesOrderError("invalid_trigger_direction", "卖出突破价必须低于当前标记价。")

    def modify_order_price(
        self,
        order_id: str,
        new_price,
        timestamp: datetime | None = None,
        current_price=None,
    ) -> FuturesOrder | None:
        target = None
        for order in self.orders:
            if order.order_id == str(order_id) and order.status == "active":
                target = order
                break
        if not target:
            return None
        price_val = decimal_value(new_price)
        if price_val <= 0:
            raise ValueError("order price must be positive")

        if current_price is not None:
            mark = decimal_value(current_price)
            if target.reduce_only:
                # 保护单按新价位改判 止盈(限价) / 止损(突破)，避免拖过界后立刻成交
                self._retarget_reduce_only_order(target, price_val, mark)
                return target
            self._validate_amend_direction(target, price_val, mark)

        if target.order_type == "limit":
            target.limit_price = price_val
            if target.protection_type == "tp":
                target.tp_price = price_val
        elif target.order_type == "breakout":
            target.trigger_price = price_val
            if target.protection_type == "sl":
                target.sl_price = price_val
        else:
            target.limit_price = price_val

        return target

    def process_bar(
        self,
        *,
        timestamp: datetime,
        high,
        low,
        close,
        open=None,
        reduce_only: bool | None = None,
        trigger_high=None,
        trigger_low=None,
    ) -> list[FuturesFill]:
        bar_time = timestamp_value(timestamp)
        high_value = decimal_value(high)
        low_value = decimal_value(low)
        open_value = decimal_value(close if open is None else open)
        trigger_high_value = high_value if trigger_high is None else decimal_value(trigger_high)
        trigger_low_value = low_value if trigger_low is None else decimal_value(trigger_low)
        if low_value > high_value:
            raise ValueError("bar low cannot exceed high")
        fills: list[FuturesFill] = []
        # 排序：SL 子单（breakout+parent）优先于 TP 子单（limit+parent），同根K线内保守触发止损
        candidates = sorted(list(self.active_orders), key=_protective_priority)
        for order in candidates:
            if order.order_type not in {"limit", "breakout"} or order.submitted_at >= bar_time:
                continue
            if reduce_only is not None and order.reduce_only != reduce_only:
                continue
            if order.reduce_only and not self._is_reducing(order):
                self.cancel_order(order.order_id, bar_time, "position_flat" if self.simulator.position.is_flat else "not_reducing")
                continue
            trigger = order.limit_price if order.order_type == "limit" else order.trigger_price
            if trigger is None:
                continue
            if order.protection_type == "tp":
                crossed = trigger_high_value >= trigger if order.side == "sell" else trigger_low_value <= trigger
                fill_price = trigger
                fee_type = "taker"
            elif order.protection_type == "sl":
                crossed = trigger_low_value <= trigger if order.side == "sell" else trigger_high_value >= trigger
                fill_price = trigger
                fee_type = "taker"
            elif order.order_type == "limit" and order.side == "buy":
                crossed = low_value <= trigger
                fill_price = trigger
                fee_type = "maker"
            elif order.order_type == "limit":
                crossed = high_value >= trigger
                fill_price = trigger
                fee_type = "maker"
            elif order.side == "buy":
                crossed = high_value >= trigger
                fill_price = trigger
                fee_type = "taker"
            else:
                crossed = low_value <= trigger
                fill_price = trigger
                fee_type = "taker"
            if crossed:
                fills.extend(self._fill_order(order, fill_price, bar_time, fee_type))
        return fills

    def _is_reducing(self, order: FuturesOrder) -> bool:
        quantity = self.simulator.position.quantity
        return quantity != ZERO and ((quantity > ZERO and order.side == "sell") or (quantity < ZERO and order.side == "buy"))

    def _fill_order(self, order: FuturesOrder, price: Decimal, timestamp: datetime, fee_type: str) -> list[FuturesFill]:
        fill_quantity = order.quantity
        if order.reduce_only:
            if not self._is_reducing(order):
                self.cancel_order(order.order_id, timestamp, "position_flat" if self.simulator.position.is_flat else "not_reducing")
                return []
            fill_quantity = min(fill_quantity, self.simulator.position.absolute_quantity)
        before = len(self.simulator.fills)
        try:
            self.simulator.apply_quantity(
                order.side,
                fill_quantity,
                price,
                timestamp=timestamp,
                leverage=order.leverage,
                fee_rate=self.maker_fee_rate if fee_type == "maker" else self.taker_fee_rate,
                fee_type=fee_type,
                action=order.action,
                order_id=order.order_id,
                reduce_only=order.reduce_only,
            )
        except ValueError as error:
            if "insufficient available margin" not in str(error):
                raise
            self.cancel_order(order.order_id, timestamp, "insufficient_margin")
            return []
        fills = self.simulator.fills[before:]
        filled_quantity = sum((fill.quantity for fill in fills), ZERO)
        order.status = "filled" if filled_quantity == order.quantity else "partially_filled"
        order.filled_at = timestamp
        order.fill_id = fills[-1].fill_id if fills else None
        if order.status == "partially_filled":
            order.cancelled_at = timestamp
            order.cancel_reason = fills[-1].metadata.get("cancel_reason", "partially_filled")
        self.fills.extend(fills)
        # --- 止盈止损：开仓单成交后创建条件平仓单 ---
        if fills and not order.reduce_only and (order.tp_price is not None or order.sl_price is not None):
            self._create_tp_sl_orders(order, filled_quantity, timestamp)
        # --- OCO：TP/SL 子单成交后取消兄弟单 ---
        if fills and order.parent_order_id is not None:
            self._cancel_sibling_tp_sl(order, timestamp)
        # --- 仓位归零后清理孤立的 TP/SL 单 ---
        if fills and self.simulator.position.is_flat:
            self._cancel_orphaned_tp_sl(timestamp)
        return fills

    def _create_tp_sl_orders(self, parent: FuturesOrder, quantity: Decimal, timestamp: datetime) -> None:
        """开仓单成交后，根据 tp_price / sl_price 创建 reduce_only 条件平仓单。"""
        close_side = "sell" if parent.side == "buy" else "buy"
        if parent.tp_price is not None:
            # TP 用 limit 单：long→sell limit（high>=tp 成交）；short→buy limit（low<=tp 成交）
            tp_order = FuturesOrder(
                order_id=f"order-{self._next_order_id}",
                action="close", order_type="limit", side=close_side,
                quantity=quantity, margin=ZERO, leverage=parent.leverage,
                submitted_at=timestamp, limit_price=parent.tp_price,
                reduce_only=True, parent_order_id=parent.order_id,
                protection_type="tp", trigger_source="mark_price",
            )
            self._next_order_id += 1
            self.orders.append(tp_order)
        if parent.sl_price is not None:
            # SL 用 breakout 单：long→sell breakout（low<=sl 成交）；short→buy breakout（high>=sl 成交）
            sl_order = FuturesOrder(
                order_id=f"order-{self._next_order_id}",
                action="close", order_type="breakout", side=close_side,
                quantity=quantity, margin=ZERO, leverage=parent.leverage,
                submitted_at=timestamp, trigger_price=parent.sl_price,
                reduce_only=True, parent_order_id=parent.order_id,
                protection_type="sl", trigger_source="mark_price",
            )
            self._next_order_id += 1
            self.orders.append(sl_order)

    def _cancel_sibling_tp_sl(self, filled_order: FuturesOrder, timestamp: datetime) -> None:
        """OCO：一个 TP/SL 子单成交后，取消同 parent 的兄弟单。"""
        for order in self.active_orders:
            if order.parent_order_id == filled_order.parent_order_id and order.order_id != filled_order.order_id:
                self.cancel_order(order.order_id, timestamp, "oco_sibling_filled")

    def _cancel_orphaned_tp_sl(self, timestamp: datetime) -> None:
        """仓位归零后，取消所有仍活跃的 TP/SL 子单。"""
        for order in list(self.active_orders):
            if order.parent_order_id is not None and order.reduce_only:
                self.cancel_order(order.order_id, timestamp, "position_flat")

    def to_dict(self) -> list[dict[str, Any]]:
        return [order.to_dict() for order in self.orders]

    def to_state(self) -> dict[str, Any]:
        return {
            "maker_fee_rate": format(self.maker_fee_rate, "f"),
            "taker_fee_rate": format(self.taker_fee_rate, "f"),
            "orders": [order.to_state() for order in self.orders],
            "fill_ids": [fill.fill_id for fill in self.fills],
            "next_order_id": self._next_order_id,
        }

    @classmethod
    def from_state(cls, simulator: FuturesSimulator, state: dict[str, Any]) -> "FuturesOrderBook":
        order_book = cls(
            simulator,
            maker_fee_rate=state["maker_fee_rate"],
            taker_fee_rate=state["taker_fee_rate"],
        )
        order_book.orders = [FuturesOrder.from_state(order) for order in state.get("orders", [])]
        fills_by_id = {fill.fill_id: fill for fill in simulator.fills}
        order_book.fills = [fills_by_id[fill_id] for fill_id in state.get("fill_ids", []) if fill_id in fills_by_id]
        order_book._next_order_id = int(state.get("next_order_id", len(order_book.orders) + 1))
        return order_book


__all__ = ["FuturesOrder", "FuturesOrderBook", "FuturesOrderError"]
