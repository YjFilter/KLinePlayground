from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from .futures_models import FuturesFill, ZERO, decimal_value, timestamp_value
from .futures_simulator import FuturesSimulator


VALID_ACTIONS = {"open_long", "open_short", "close"}
VALID_ORDER_TYPES = {"market", "limit"}


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
    reduce_only: bool = False
    status: str = "active"
    filled_at: datetime | None = None
    cancelled_at: datetime | None = None
    fill_id: str | None = None
    cancel_reason: str | None = None
    reserved_margin: Decimal = ZERO

    def __post_init__(self) -> None:
        self.quantity = decimal_value(self.quantity)
        self.margin = decimal_value(self.margin)
        self.limit_price = None if self.limit_price is None else decimal_value(self.limit_price)
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
            "reduce_only": self.reduce_only,
            "status": self.status,
            "filled_at": None if self.filled_at is None else self.filled_at.isoformat(),
            "cancelled_at": None if self.cancelled_at is None else self.cancelled_at.isoformat(),
            "fill_id": self.fill_id,
            "cancel_reason": self.cancel_reason,
            "reserved_margin": float(self.reserved_margin),
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
            "reduce_only": self.reduce_only,
            "status": self.status,
            "filled_at": None if self.filled_at is None else self.filled_at.isoformat(),
            "cancelled_at": None if self.cancelled_at is None else self.cancelled_at.isoformat(),
            "fill_id": self.fill_id,
            "cancel_reason": self.cancel_reason,
            "reserved_margin": format(self.reserved_margin, "f"),
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "FuturesOrder":
        return cls(
            order_id=state["order_id"], action=state["action"], order_type=state["order_type"],
            side=state["side"], quantity=state["quantity"], margin=state["margin"],
            leverage=int(state["leverage"]), submitted_at=datetime.fromisoformat(state["submitted_at"]),
            limit_price=state.get("limit_price"), reduce_only=bool(state.get("reduce_only", False)),
            status=state.get("status", "active"),
            filled_at=None if state.get("filled_at") is None else datetime.fromisoformat(state["filled_at"]),
            cancelled_at=None if state.get("cancelled_at") is None else datetime.fromisoformat(state["cancelled_at"]),
            fill_id=state.get("fill_id"), cancel_reason=state.get("cancel_reason"),
            reserved_margin=state.get("reserved_margin", ZERO),
        )


class FuturesOrderBook:
    def __init__(
        self,
        simulator: FuturesSimulator,
        *,
        maker_fee_rate: Decimal | int | float | str = "0.0002",
        taker_fee_rate: Decimal | int | float | str = "0.0005",
    ) -> None:
        self.simulator = simulator
        self.maker_fee_rate = decimal_value(maker_fee_rate)
        self.taker_fee_rate = decimal_value(taker_fee_rate)
        if min(self.maker_fee_rate, self.taker_fee_rate) < ZERO:
            raise ValueError("fee rates cannot be negative")
        self.orders: list[FuturesOrder] = []
        self.fills: list[FuturesFill] = []
        self._next_order_id = 1

    @property
    def active_orders(self) -> list[FuturesOrder]:
        return [order for order in self.orders if order.status == "active"]

    @property
    def reserved_margin(self) -> Decimal:
        return sum((order.reserved_margin for order in self.active_orders), ZERO)

    def submit_order(
        self,
        *,
        action: str,
        order_type: str,
        timestamp: datetime,
        current_price,
        margin=None,
        leverage: int | None = None,
        limit_price=None,
    ) -> FuturesOrder:
        if action not in VALID_ACTIONS:
            raise ValueError("unsupported futures action")
        if order_type not in VALID_ORDER_TYPES:
            raise ValueError("order_type must be market or limit")
        submitted_at = timestamp_value(timestamp)
        current_price_value = decimal_value(current_price)
        selected_leverage = self.simulator.leverage if leverage is None else leverage
        self.simulator._validate_leverage(selected_leverage)
        if selected_leverage != self.simulator.leverage:
            if not self.simulator.position.is_flat or self.active_orders:
                raise ValueError("leverage can change only while flat without active orders")
            self.simulator.set_leverage(selected_leverage)
        reduce_only = action == "close"
        if reduce_only:
            if self.simulator.position.is_flat:
                raise ValueError("cannot close a flat position")
            quantity = self.simulator.position.absolute_quantity
            margin_value = ZERO
            side = "sell" if self.simulator.position.quantity > ZERO else "buy"
        else:
            if margin is None:
                raise ValueError("margin is required for open orders")
            margin_value = decimal_value(margin)
            if margin_value <= ZERO:
                raise ValueError("margin must be positive")
            sizing_price = current_price_value if order_type == "market" else decimal_value(limit_price)
            quantity = self.simulator.margin_to_quantity(margin_value, selected_leverage, sizing_price)
            side = "buy" if action == "open_long" else "sell"
            fee_rate = self.taker_fee_rate if order_type == "market" else self.maker_fee_rate
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
        selected_limit = None
        if order_type == "limit":
            if limit_price is None:
                raise ValueError("limit_price is required for limit orders")
            selected_limit = decimal_value(limit_price)
            if selected_limit <= ZERO:
                raise ValueError("limit_price must be positive")
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
            reduce_only=reduce_only,
            reserved_margin=ZERO if reduce_only else required_reservation,
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

    def process_bar(self, *, timestamp: datetime, high, low, close, reduce_only: bool | None = None) -> list[FuturesFill]:
        bar_time = timestamp_value(timestamp)
        high_value = decimal_value(high)
        low_value = decimal_value(low)
        if low_value > high_value:
            raise ValueError("bar low cannot exceed high")
        fills: list[FuturesFill] = []
        for order in list(self.active_orders):
            if order.order_type != "limit" or order.submitted_at >= bar_time:
                continue
            if reduce_only is not None and order.reduce_only != reduce_only:
                continue
            if order.reduce_only and not self._is_reducing(order):
                self.cancel_order(order.order_id, bar_time, "position_flat" if self.simulator.position.is_flat else "not_reducing")
                continue
            if order.side == "buy":
                crossed = low_value <= order.limit_price
            else:
                crossed = high_value >= order.limit_price
            if crossed:
                fills.extend(self._fill_order(order, order.limit_price, bar_time, "maker"))
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
        return fills

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


__all__ = ["FuturesOrder", "FuturesOrderBook"]
