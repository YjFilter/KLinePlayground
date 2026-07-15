from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


ZERO = Decimal("0")


def decimal_value(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def timestamp_value(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def decimal_text(value: Decimal) -> str:
    return format(value, "f")


@dataclass
class FuturesAccount:
    initial_balance: Decimal
    balance: Decimal | None = None
    used_margin: Decimal = ZERO
    realized_pnl: Decimal = ZERO
    total_fees: Decimal = ZERO
    maker_fees: Decimal = ZERO
    taker_fees: Decimal = ZERO
    liquidation_fees: Decimal = ZERO
    funding_paid: Decimal = ZERO
    funding_received: Decimal = ZERO

    def __post_init__(self) -> None:
        self.initial_balance = decimal_value(self.initial_balance)
        self.balance = self.initial_balance if self.balance is None else decimal_value(self.balance)
        for name in (
            "used_margin", "realized_pnl", "total_fees", "maker_fees", "taker_fees",
            "liquidation_fees", "funding_paid", "funding_received",
        ):
            setattr(self, name, decimal_value(getattr(self, name)))

    @property
    def available_balance(self) -> Decimal:
        return max(ZERO, self.balance - self.used_margin)

    def charge_fee(self, fee: Decimal, fee_type: str) -> None:
        fee = decimal_value(fee)
        self.balance -= fee
        self.total_fees += fee
        if fee_type == "maker":
            self.maker_fees += fee
        elif fee_type == "liquidation":
            self.liquidation_fees += fee
        else:
            self.taker_fees += fee

    def apply_funding(self, transfer: Decimal) -> None:
        transfer = decimal_value(transfer)
        self.balance += transfer
        if transfer < ZERO:
            self.funding_paid += -transfer
        else:
            self.funding_received += transfer

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_balance": float(self.initial_balance),
            "balance": float(self.balance),
            "used_margin": float(self.used_margin),
            "available_balance": float(self.available_balance),
            "realized_pnl": float(self.realized_pnl),
            "total_fees": float(self.total_fees),
            "maker_fees": float(self.maker_fees),
            "taker_fees": float(self.taker_fees),
            "liquidation_fees": float(self.liquidation_fees),
            "funding_paid": float(self.funding_paid),
            "funding_received": float(self.funding_received),
        }

    def to_state(self) -> dict[str, str]:
        return {name: decimal_text(getattr(self, name)) for name in (
            "initial_balance", "balance", "used_margin", "realized_pnl", "total_fees",
            "maker_fees", "taker_fees", "liquidation_fees", "funding_paid", "funding_received",
        )}

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "FuturesAccount":
        return cls(**{name: decimal_value(value) for name, value in state.items()})


@dataclass
class FuturesPosition:
    quantity: Decimal = ZERO
    entry_price: Decimal = ZERO
    leverage: int = 5
    isolated_margin: Decimal = ZERO

    def __post_init__(self) -> None:
        self.quantity = decimal_value(self.quantity)
        self.entry_price = decimal_value(self.entry_price)
        self.isolated_margin = decimal_value(self.isolated_margin)

    @property
    def is_flat(self) -> bool:
        return self.quantity == ZERO

    @property
    def side(self) -> str:
        if self.quantity > ZERO:
            return "long"
        if self.quantity < ZERO:
            return "short"
        return "flat"

    @property
    def absolute_quantity(self) -> Decimal:
        return abs(self.quantity)

    def unrealized_pnl(self, mark_price: Decimal | int | float | str) -> Decimal:
        if self.is_flat:
            return ZERO
        return self.quantity * (decimal_value(mark_price) - self.entry_price)

    def notional(self, mark_price: Decimal | int | float | str) -> Decimal:
        return self.absolute_quantity * decimal_value(mark_price)

    def to_dict(self, mark_price: Decimal | int | float | str | None = None) -> dict[str, Any]:
        selected_mark = self.entry_price if mark_price is None else decimal_value(mark_price)
        return {
            "side": self.side,
            "quantity": float(self.absolute_quantity),
            "signed_quantity": float(self.quantity),
            "entry_price": float(self.entry_price),
            "mark_price": float(selected_mark),
            "leverage": self.leverage,
            "isolated_margin": float(self.isolated_margin),
            "unrealized_pnl": float(self.unrealized_pnl(selected_mark)),
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "quantity": decimal_text(self.quantity),
            "entry_price": decimal_text(self.entry_price),
            "leverage": self.leverage,
            "isolated_margin": decimal_text(self.isolated_margin),
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "FuturesPosition":
        return cls(
            quantity=decimal_value(state["quantity"]),
            entry_price=decimal_value(state["entry_price"]),
            leverage=int(state["leverage"]),
            isolated_margin=decimal_value(state["isolated_margin"]),
        )


@dataclass
class FuturesFill:
    fill_id: str
    order_id: str
    action: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    fee_type: str
    timestamp: datetime
    realized_pnl: Decimal = ZERO
    reduce_only: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.quantity = decimal_value(self.quantity)
        self.price = decimal_value(self.price)
        self.fee = decimal_value(self.fee)
        self.realized_pnl = decimal_value(self.realized_pnl)
        self.timestamp = timestamp_value(self.timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "action": self.action,
            "side": self.side,
            "quantity": float(self.quantity),
            "price": float(self.price),
            "notional": float(self.quantity * self.price),
            "fee": float(self.fee),
            "fee_type": self.fee_type,
            "timestamp": self.timestamp.isoformat(),
            "realized_pnl": float(self.realized_pnl),
            "reduce_only": self.reduce_only,
            "metadata": dict(self.metadata),
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "action": self.action,
            "side": self.side,
            "quantity": decimal_text(self.quantity),
            "price": decimal_text(self.price),
            "fee": decimal_text(self.fee),
            "fee_type": self.fee_type,
            "timestamp": self.timestamp.isoformat(),
            "realized_pnl": decimal_text(self.realized_pnl),
            "reduce_only": self.reduce_only,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "FuturesFill":
        return cls(
            fill_id=state["fill_id"],
            order_id=state.get("order_id", ""),
            action=state["action"],
            side=state["side"],
            quantity=decimal_value(state["quantity"]),
            price=decimal_value(state["price"]),
            fee=decimal_value(state["fee"]),
            fee_type=state["fee_type"],
            timestamp=datetime.fromisoformat(state["timestamp"]),
            realized_pnl=decimal_value(state.get("realized_pnl", ZERO)),
            reduce_only=bool(state.get("reduce_only", False)),
            metadata=dict(state.get("metadata", {})),
        )


__all__ = [
    "FuturesAccount", "FuturesFill", "FuturesPosition", "ZERO", "decimal_text",
    "decimal_value", "timestamp_value",
]
