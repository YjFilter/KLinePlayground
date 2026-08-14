from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_DOWN

from .futures_models import (
    FuturesAccount,
    FuturesFill,
    FuturesPosition,
    ZERO,
    decimal_value,
    timestamp_value,
)


class FuturesSimulator:
    def __init__(
        self,
        initial_balance: Decimal | int | float | str,
        quantity_step: Decimal | int | float | str,
        min_quantity: Decimal | int | float | str,
        min_notional: Decimal | int | float | str,
        leverage: int = 5,
        maintenance_margin_rate: Decimal | int | float | str = "0.005",
    ) -> None:
        self.quantity_step = decimal_value(quantity_step)
        self.min_quantity = decimal_value(min_quantity)
        self.min_notional = decimal_value(min_notional)
        self.maintenance_margin_rate = decimal_value(maintenance_margin_rate)
        if min(self.quantity_step, self.min_quantity, self.min_notional) <= ZERO:
            raise ValueError("quantity and notional rules must be positive")
        self._validate_leverage(leverage)
        self.leverage = leverage
        self.account = FuturesAccount(decimal_value(initial_balance))
        self.position = FuturesPosition(leverage=leverage)
        self.fills: list[FuturesFill] = []
        self.last_mark_price: Decimal | None = None
        self._next_fill_id = 1

    @staticmethod
    def _validate_leverage(leverage: int) -> None:
        if isinstance(leverage, bool) or not isinstance(leverage, int) or not 1 <= leverage <= 100:
            raise ValueError("leverage must be a whole number from 1 through 100")

    def set_leverage(self, leverage: int, *, has_active_orders: bool = False) -> None:
        self._validate_leverage(leverage)
        if not self.position.is_flat or has_active_orders:
            raise ValueError("leverage can change only while flat without active orders")
        self.leverage = leverage
        self.position.leverage = leverage

    def margin_to_quantity(
        self,
        margin: Decimal | int | float | str,
        leverage: Decimal | int | float | str,
        price: Decimal | int | float | str,
    ) -> Decimal:
        margin_value = decimal_value(margin)
        leverage_value = decimal_value(leverage)
        price_value = decimal_value(price)
        if min(margin_value, leverage_value, price_value) <= ZERO:
            raise ValueError("margin, leverage, and price must be positive")
        raw_quantity = margin_value * leverage_value / price_value
        steps = (raw_quantity / self.quantity_step).to_integral_value(rounding=ROUND_DOWN)
        quantity = steps * self.quantity_step
        if quantity < self.min_quantity:
            raise ValueError("order is below minimum quantity")
        if quantity * price_value < self.min_notional:
            raise ValueError("order is below minimum notional")
        return quantity

    def open_long(self, *, margin, price, timestamp, leverage: int | None = None, **fill_options) -> FuturesFill:
        selected_leverage = self.leverage if leverage is None else leverage
        self._validate_leverage(selected_leverage)
        quantity = self.margin_to_quantity(margin, selected_leverage, price)
        return self.apply_quantity("buy", quantity, price, timestamp=timestamp, leverage=selected_leverage, action="open_long", **fill_options)

    def open_short(self, *, margin, price, timestamp, leverage: int | None = None, **fill_options) -> FuturesFill:
        selected_leverage = self.leverage if leverage is None else leverage
        self._validate_leverage(selected_leverage)
        quantity = self.margin_to_quantity(margin, selected_leverage, price)
        return self.apply_quantity("sell", quantity, price, timestamp=timestamp, leverage=selected_leverage, action="open_short", **fill_options)

    def close(self, *, price, timestamp, quantity=None, **fill_options) -> FuturesFill:
        if self.position.is_flat:
            raise ValueError("cannot close a flat position")
        close_quantity = self.position.absolute_quantity if quantity is None else min(decimal_value(quantity), self.position.absolute_quantity)
        side = "sell" if self.position.quantity > ZERO else "buy"
        return self.apply_quantity(side, close_quantity, price, timestamp=timestamp, action="close", reduce_only=True, **fill_options)

    def apply_quantity(
        self,
        side: str,
        quantity,
        price,
        *,
        timestamp: datetime,
        leverage: int | None = None,
        fee_rate=ZERO,
        fee_type: str = "taker",
        action: str | None = None,
        order_id: str = "",
        reduce_only: bool = False,
        fill_id: str | None = None,
    ) -> FuturesFill:
        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        quantity_value = decimal_value(quantity)
        price_value = decimal_value(price)
        if quantity_value <= ZERO or price_value <= ZERO:
            raise ValueError("quantity and price must be positive")
        selected_leverage = self.leverage if leverage is None else leverage
        self._validate_leverage(selected_leverage)
        if not self.position.is_flat and selected_leverage != self.position.leverage:
            raise ValueError("leverage cannot change while a position is open")
        if self.position.is_flat and selected_leverage != self.leverage:
            self.set_leverage(selected_leverage)
        signed_delta = quantity_value if side == "buy" else -quantity_value
        current_quantity = self.position.quantity
        if reduce_only and (current_quantity == ZERO or current_quantity * signed_delta >= ZERO):
            raise ValueError("reduce-only order cannot increase exposure")
        if reduce_only:
            signed_delta = (Decimal("1") if signed_delta > ZERO else Decimal("-1")) * min(quantity_value, abs(current_quantity))

        same_direction = current_quantity == ZERO or current_quantity * signed_delta > ZERO
        fee_rate_value = decimal_value(fee_rate)
        old_absolute = abs(current_quantity)
        if same_direction:
            added_absolute = abs(signed_delta)
            required_margin = added_absolute * price_value / Decimal(selected_leverage)
            fee = added_absolute * price_value * fee_rate_value
            if required_margin + fee > self.account.available_balance:
                raise ValueError("insufficient available margin including fee")
            new_absolute = old_absolute + added_absolute
            if old_absolute == ZERO:
                self.position.entry_price = price_value
            else:
                self.position.entry_price = (
                    old_absolute * self.position.entry_price + added_absolute * price_value
                ) / new_absolute
            self.position.quantity = current_quantity + signed_delta
            self.position.isolated_margin += required_margin
            self.account.used_margin += required_margin
            self.position.leverage = selected_leverage
            if fee:
                self.account.charge_fee(fee, fee_type)
            fill = self._create_fill(
                order_id=order_id,
                action=action or ("open_long" if side == "buy" else "open_short"),
                side=side,
                quantity=added_absolute,
                price=price_value,
                fee=fee,
                fee_type=fee_type,
                timestamp=timestamp,
                realized_pnl=ZERO,
                reduce_only=reduce_only,
                fill_id=fill_id,
            )
            self.last_mark_price = price_value
            return fill

        closing_quantity = min(old_absolute, abs(signed_delta))
        direction = Decimal("1") if current_quantity > ZERO else Decimal("-1")
        realized_pnl = closing_quantity * (price_value - self.position.entry_price) * direction
        released_margin = self.position.isolated_margin * closing_quantity / old_absolute
        close_fee = closing_quantity * price_value * fee_rate_value
        self.position.isolated_margin -= released_margin
        self.account.used_margin -= released_margin
        self.account.balance += realized_pnl
        self.account.realized_pnl += realized_pnl
        remaining_position = old_absolute - closing_quantity
        if remaining_position > ZERO:
            self.position.quantity = direction * remaining_position
        else:
            self.position = FuturesPosition(leverage=self.leverage)
        if close_fee:
            self.account.charge_fee(close_fee, fee_type)
        self.account.balance = max(ZERO, self.account.balance)
        if self.account.used_margin > self.account.balance:
            reduction = self.account.used_margin - self.account.balance
            self.account.used_margin = self.account.balance
            self.position.isolated_margin = max(ZERO, self.position.isolated_margin - reduction)
        close_fill = self._create_fill(
            order_id=order_id,
            action="liquidation" if action == "liquidation" else "close",
            side=side,
            quantity=closing_quantity,
            price=price_value,
            fee=close_fee,
            fee_type=fee_type,
            timestamp=timestamp,
            realized_pnl=realized_pnl,
            reduce_only=True,
            fill_id=fill_id,
        )
        remaining_delta = abs(signed_delta) - closing_quantity
        if remaining_delta > ZERO:
            required_margin = remaining_delta * price_value / Decimal(selected_leverage)
            opening_fee = remaining_delta * price_value * fee_rate_value
            if required_margin + opening_fee <= self.account.available_balance:
                reverse_direction = Decimal("1") if signed_delta > ZERO else Decimal("-1")
                self.position.quantity = reverse_direction * remaining_delta
                self.position.entry_price = price_value
                self.position.isolated_margin = required_margin
                self.position.leverage = selected_leverage
                self.account.used_margin += required_margin
                if opening_fee:
                    self.account.charge_fee(opening_fee, fee_type)
                self._create_fill(
                    order_id=order_id,
                    action=action or ("open_long" if side == "buy" else "open_short"),
                    side=side,
                    quantity=remaining_delta,
                    price=price_value,
                    fee=opening_fee,
                    fee_type=fee_type,
                    timestamp=timestamp,
                    realized_pnl=ZERO,
                    reduce_only=False,
                )
            else:
                close_fill.metadata["reversal_rejected_quantity"] = format(remaining_delta, "f")
                close_fill.metadata["cancel_reason"] = "insufficient_margin_for_reversal"
        self.last_mark_price = price_value
        return close_fill

    def _create_fill(
        self, *, order_id, action, side, quantity, price, fee, fee_type,
        timestamp, realized_pnl, reduce_only, fill_id=None,
    ) -> FuturesFill:
        selected_fill_id = fill_id or f"fill-{self._next_fill_id}"
        if fill_id is None:
            self._next_fill_id += 1
        fill = FuturesFill(
            fill_id=selected_fill_id,
            order_id=order_id,
            action=action,
            side=side,
            quantity=quantity,
            price=price,
            fee=fee,
            fee_type=fee_type,
            timestamp=timestamp_value(timestamp),
            realized_pnl=realized_pnl,
            reduce_only=reduce_only,
        )
        self.fills.append(fill)
        return fill

    def unrealized_pnl(self, mark_price) -> Decimal:
        return self.position.unrealized_pnl(mark_price)

    def equity(self, mark_price) -> Decimal:
        return max(ZERO, self.account.balance + self.unrealized_pnl(mark_price))

    def maintenance_margin(self, mark_price) -> Decimal:
        return self.position.notional(mark_price) * self.maintenance_margin_rate

    def isolated_equity(self, mark_price) -> Decimal:
        return max(ZERO, self.position.isolated_margin + self.unrealized_pnl(mark_price))

    def margin_ratio(self, mark_price) -> Decimal:
        # 全仓（Cross）：保证金率 = 维持保证金 ÷ 账户总权益（余额+浮动盈亏），
        # 账户剩余资金共同支撑仓位，单仓保证金不再单独决定风险。
        account_equity = self.equity(mark_price)
        if self.position.is_flat or account_equity <= ZERO:
            return ZERO
        return self.maintenance_margin(mark_price) / account_equity * Decimal("100")

    def snapshot(self, mark_price=None) -> dict:
        selected_mark = self.last_mark_price if mark_price is None else decimal_value(mark_price)
        if selected_mark is None:
            selected_mark = self.position.entry_price
        return {
            "account": {**self.account.to_dict(), "equity": float(self.equity(selected_mark))},
            "position": self.position.to_dict(selected_mark),
            "leverage": self.leverage,
            "maintenance_margin": float(self.maintenance_margin(selected_mark)),
            "margin_ratio": float(self.margin_ratio(selected_mark)),
            "fills": [fill.to_dict() for fill in self.fills],
        }

    def to_state(self) -> dict:
        return {
            "initial_balance": format(self.account.initial_balance, "f"),
            "quantity_step": format(self.quantity_step, "f"),
            "min_quantity": format(self.min_quantity, "f"),
            "min_notional": format(self.min_notional, "f"),
            "maintenance_margin_rate": format(self.maintenance_margin_rate, "f"),
            "leverage": self.leverage,
            "account": self.account.to_state(),
            "position": self.position.to_state(),
            "fills": [fill.to_state() for fill in self.fills],
            "last_mark_price": None if self.last_mark_price is None else format(self.last_mark_price, "f"),
            "next_fill_id": self._next_fill_id,
        }

    @classmethod
    def from_state(cls, state: dict) -> "FuturesSimulator":
        simulator = cls(
            initial_balance=state["initial_balance"],
            quantity_step=state["quantity_step"],
            min_quantity=state["min_quantity"],
            min_notional=state["min_notional"],
            leverage=int(state["leverage"]),
            maintenance_margin_rate=state["maintenance_margin_rate"],
        )
        simulator.account = FuturesAccount.from_state(state["account"])
        simulator.position = FuturesPosition.from_state(state["position"])
        simulator.fills = [FuturesFill.from_state(fill) for fill in state.get("fills", [])]
        last_mark = state.get("last_mark_price")
        simulator.last_mark_price = None if last_mark is None else decimal_value(last_mark)
        simulator._next_fill_id = int(state.get("next_fill_id", len(simulator.fills) + 1))
        return simulator


__all__ = ["FuturesSimulator"]
