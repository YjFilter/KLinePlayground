from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable

from .futures_models import ZERO, decimal_value, timestamp_value
from .futures_orders import FuturesOrderBook
from .futures_simulator import FuturesSimulator
from .models import FundingEvent


@dataclass
class FundingSettlement:
    event_key: str
    source: str
    symbol: str
    timestamp: datetime
    rate: Decimal
    mark_price: Decimal
    notional: Decimal
    transfer: Decimal
    position_side: str
    status: str = "settled"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_key": self.event_key,
            "source": self.source,
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "rate": float(self.rate),
            "mark_price": float(self.mark_price),
            "notional": float(self.notional),
            "transfer": float(self.transfer),
            "position_side": self.position_side,
            "status": self.status,
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "event_key": self.event_key, "source": self.source, "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(), "rate": format(self.rate, "f"),
            "mark_price": format(self.mark_price, "f"), "notional": format(self.notional, "f"),
            "transfer": format(self.transfer, "f"), "position_side": self.position_side, "status": self.status,
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "FundingSettlement":
        return cls(
            event_key=state["event_key"], source=state["source"], symbol=state["symbol"],
            timestamp=datetime.fromisoformat(state["timestamp"]), rate=decimal_value(state["rate"]),
            mark_price=decimal_value(state["mark_price"]), notional=decimal_value(state["notional"]),
            transfer=decimal_value(state["transfer"]), position_side=state["position_side"], status=state.get("status", "settled"),
        )


@dataclass
class LiquidationEvent:
    liquidation_id: str
    timestamp: datetime
    side: str
    quantity: Decimal
    entry_price: Decimal
    price: Decimal
    fee: Decimal
    equity_before: Decimal
    maintenance_margin: Decimal
    reason: str = "isolated_margin"

    def to_dict(self) -> dict[str, Any]:
        return {
            "liquidation_id": self.liquidation_id,
            "timestamp": self.timestamp.isoformat(),
            "side": self.side,
            "quantity": float(self.quantity),
            "entry_price": float(self.entry_price),
            "price": float(self.price),
            "fee": float(self.fee),
            "equity_before": float(self.equity_before),
            "maintenance_margin": float(self.maintenance_margin),
            "reason": self.reason,
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "liquidation_id": self.liquidation_id, "timestamp": self.timestamp.isoformat(), "side": self.side,
            "quantity": format(self.quantity, "f"), "entry_price": format(self.entry_price, "f"),
            "price": format(self.price, "f"), "fee": format(self.fee, "f"),
            "equity_before": format(self.equity_before, "f"),
            "maintenance_margin": format(self.maintenance_margin, "f"), "reason": self.reason,
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "LiquidationEvent":
        return cls(
            liquidation_id=state["liquidation_id"], timestamp=datetime.fromisoformat(state["timestamp"]),
            side=state["side"], quantity=decimal_value(state["quantity"]),
            entry_price=decimal_value(state["entry_price"]), price=decimal_value(state["price"]),
            fee=decimal_value(state["fee"]), equity_before=decimal_value(state["equity_before"]),
            maintenance_margin=decimal_value(state["maintenance_margin"]), reason=state.get("reason", "isolated_margin"),
        )


class FuturesEngine:
    def __init__(
        self,
        simulator: FuturesSimulator,
        order_book: FuturesOrderBook,
        *,
        liquidation_fee_rate: Decimal | int | float | str = "0",
    ) -> None:
        self.simulator = simulator
        self.order_book = order_book
        self.liquidation_fee_rate = decimal_value(liquidation_fee_rate)
        if self.liquidation_fee_rate < ZERO:
            raise ValueError("liquidation fee rate cannot be negative")
        self.funding_events: list[FundingSettlement] = []
        self.liquidation_events: list[LiquidationEvent] = []
        self.equity_snapshots: list[dict[str, Any]] = []
        self._processed_funding: set[str] = set()
        # 资金费率事件只排序一次，用游标增量结算，避免每根 base bar 全量重排重扫。
        self._funding_queue: list[FundingEvent] | None = None
        self._funding_cursor = 0
        # 最大回撤用“峰值权益 + 当前最大回撤”增量维护，与逐条扫描 _maximum_drawdown 完全等价，
        # 因此权益快照可以按显示周期降采样，而不损失回撤精度。
        self._peak_equity: Decimal = ZERO
        self._max_drawdown_percent: Decimal = ZERO
        self.last_trade_price: Decimal | None = None
        self.last_mark_price: Decimal | None = None
        self._next_liquidation_id = 1

    def _funding_key(self, event: FundingEvent) -> str:
        normalized = timestamp_value(event.timestamp)
        return f"{event.source}:{event.symbol}:{normalized.isoformat()}"

    def settle_funding(self, event: FundingEvent) -> FundingSettlement | None:
        event_key = self._funding_key(event)
        if event_key in self._processed_funding:
            return None
        self._processed_funding.add(event_key)
        mark_price = decimal_value(event.mark_price if event.mark_price is not None else self.last_mark_price)
        timestamp = timestamp_value(event.timestamp)
        position_side = self.simulator.position.side
        if self.simulator.position.is_flat:
            settlement = FundingSettlement(
                event_key, event.source, event.symbol, timestamp, decimal_value(event.rate),
                mark_price, ZERO, ZERO, position_side, "skipped_flat",
            )
            self.funding_events.append(settlement)
            return settlement
        notional = self.simulator.position.notional(mark_price)
        payment = notional * decimal_value(event.rate)
        transfer = -payment if self.simulator.position.quantity > ZERO else payment
        self.simulator.account.apply_funding(transfer)
        self.simulator.position.isolated_margin += transfer
        self.simulator.account.used_margin = max(ZERO, self.simulator.account.used_margin + transfer)
        settlement = FundingSettlement(
            event_key, event.source, event.symbol, timestamp, decimal_value(event.rate),
            mark_price, notional, transfer, position_side,
        )
        self.funding_events.append(settlement)
        return settlement

    def liquidation_price(self) -> Decimal | None:
        position = self.simulator.position
        if position.is_flat:
            return None
        quantity = position.absolute_quantity
        reserve_rate = self.simulator.maintenance_margin_rate + self.liquidation_fee_rate
        # 全仓（Cross）：用账户余额（balance）作为仓位风险支撑，
        # 而非单仓保证金 isolated_margin。余额充足时强平价远离现价甚至为 0（不会触发）。
        balance = self.simulator.account.balance
        if position.quantity > ZERO:
            denominator = quantity * (Decimal("1") - reserve_rate)
            if denominator <= ZERO:
                raise ValueError("liquidation rates leave no valid long trigger")
            return max(ZERO, (quantity * position.entry_price - balance) / denominator)
        denominator = quantity * (Decimal("1") + reserve_rate)
        return max(ZERO, (balance + quantity * position.entry_price) / denominator)

    def check_liquidation(self, *, timestamp: datetime, mark_low, mark_high) -> LiquidationEvent | None:
        position = self.simulator.position
        if position.is_flat:
            return None
        trigger = self.liquidation_price()
        low_value = decimal_value(mark_low)
        high_value = decimal_value(mark_high)
        crossed = low_value <= trigger if position.quantity > ZERO else high_value >= trigger
        if not crossed:
            return None
        side = position.side
        quantity = position.absolute_quantity
        entry_price = position.entry_price
        equity_before = self.simulator.equity(trigger)
        maintenance = self.simulator.maintenance_margin(trigger)
        liquidation_fee = quantity * trigger * self.liquidation_fee_rate
        event_time = timestamp_value(timestamp)
        self.order_book.cancel_all(event_time)
        fill_side = "sell" if position.quantity > ZERO else "buy"
        self.simulator.apply_quantity(
            fill_side,
            quantity,
            trigger,
            timestamp=event_time,
            fee_rate=self.liquidation_fee_rate,
            fee_type="liquidation",
            action="liquidation",
            order_id=f"liquidation-{self._next_liquidation_id}",
            reduce_only=True,
        )
        self.simulator.account.balance = max(ZERO, self.simulator.account.balance)
        event = LiquidationEvent(
            liquidation_id=f"liquidation-{self._next_liquidation_id}",
            timestamp=event_time,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            price=trigger,
            fee=liquidation_fee,
            equity_before=max(ZERO, equity_before),
            maintenance_margin=maintenance,
        )
        self._next_liquidation_id += 1
        self.liquidation_events.append(event)
        return event

    def process_bar(
        self,
        *,
        timestamp: datetime,
        trade_bar: dict[str, Any] | Any,
        mark_bar: dict[str, Any] | Any,
        funding_events: Iterable[FundingEvent] = (),
        record_equity: bool = True,
    ) -> dict[str, Any]:
        event_time = timestamp_value(timestamp)
        trade = self._bar_values(trade_bar)
        mark = self._bar_values(mark_bar)
        self.last_trade_price = trade["close"]
        self.last_mark_price = mark["close"]
        self.simulator.last_mark_price = mark["close"]

        settled = []
        if self._funding_queue is None:
            # 首次结算时对资金事件排序一次并缓存；后续调用复用同一队列（回放中事件集合不变）。
            self._funding_queue = sorted(
                funding_events, key=lambda item: timestamp_value(item.timestamp)
            )
        while self._funding_cursor < len(self._funding_queue):
            event = self._funding_queue[self._funding_cursor]
            if timestamp_value(event.timestamp) <= event_time:
                self._funding_cursor += 1
                result = self.settle_funding(event)
                if result is not None:
                    settled.append(result)
            else:
                break

        liquidation = self.check_liquidation(timestamp=event_time, mark_low=mark["low"], mark_high=mark["high"])
        fills = []
        if liquidation is None:
            trigger_prices = {"trigger_high": mark["high"], "trigger_low": mark["low"]}
            fills.extend(self.order_book.process_bar(
                timestamp=event_time,
                **trade,
                **trigger_prices,
                reduce_only=True,
            ))
            fills.extend(self.order_book.process_bar(
                timestamp=event_time,
                **trade,
                **trigger_prices,
                reduce_only=False,
            ))

        equity = self.simulator.equity(mark["close"])
        # 增量更新最大回撤：peak 先取 max，再算 (peak - equity) / peak，与 _maximum_drawdown 一致。
        if equity > self._peak_equity:
            self._peak_equity = equity
        if self._peak_equity > ZERO:
            drawdown = (self._peak_equity - equity) / self._peak_equity * Decimal("100")
            if drawdown > self._max_drawdown_percent:
                self._max_drawdown_percent = drawdown
        snapshot = {
            "timestamp": event_time,
            "equity": equity,
            "balance": self.simulator.account.balance,
            "unrealized_pnl": self.simulator.unrealized_pnl(mark["close"]),
            "mark_price": mark["close"],
        }
        if record_equity:
            self.equity_snapshots.append(snapshot)
        return {
            "timestamp": event_time,
            "funding": settled,
            "liquidations": [] if liquidation is None else [liquidation],
            "fills": fills,
            "equity": max(ZERO, equity),
            "snapshot": snapshot,
        }

    @staticmethod
    def _bar_values(bar: dict[str, Any] | Any) -> dict[str, Decimal]:
        def read(name: str):
            if isinstance(bar, dict):
                return bar.get(name, bar["close"] if name == "open" else None)
            return getattr(bar, name, getattr(bar, "close") if name == "open" else None)
        return {name: decimal_value(read(name)) for name in ("open", "high", "low", "close")}

    def max_drawdown_percent(self) -> Decimal:
        return self._max_drawdown_percent

    def to_state(self) -> dict[str, Any]:
        return {
            "liquidation_fee_rate": format(self.liquidation_fee_rate, "f"),
            "funding_events": [event.to_state() for event in self.funding_events],
            "liquidation_events": [event.to_state() for event in self.liquidation_events],
            "equity_snapshots": [{
                "timestamp": item["timestamp"].isoformat(),
                "equity": format(item["equity"], "f"),
                "balance": format(item["balance"], "f"),
                "unrealized_pnl": format(item["unrealized_pnl"], "f"),
                "mark_price": format(item["mark_price"], "f"),
            } for item in self.equity_snapshots],
            "processed_funding": sorted(self._processed_funding),
            "peak_equity": format(self._peak_equity, "f"),
            "max_drawdown_percent": format(self._max_drawdown_percent, "f"),
            "last_trade_price": None if self.last_trade_price is None else format(self.last_trade_price, "f"),
            "last_mark_price": None if self.last_mark_price is None else format(self.last_mark_price, "f"),
            "next_liquidation_id": self._next_liquidation_id,
        }

    @classmethod
    def from_state(cls, simulator: FuturesSimulator, order_book: FuturesOrderBook, state: dict[str, Any]) -> "FuturesEngine":
        engine = cls(simulator, order_book, liquidation_fee_rate=state["liquidation_fee_rate"])
        engine.funding_events = [FundingSettlement.from_state(event) for event in state.get("funding_events", [])]
        engine.liquidation_events = [LiquidationEvent.from_state(event) for event in state.get("liquidation_events", [])]
        engine.equity_snapshots = [{
            "timestamp": datetime.fromisoformat(item["timestamp"]),
            "equity": decimal_value(item["equity"]), "balance": decimal_value(item["balance"]),
            "unrealized_pnl": decimal_value(item["unrealized_pnl"]), "mark_price": decimal_value(item["mark_price"]),
        } for item in state.get("equity_snapshots", [])]
        engine._processed_funding = set(state.get("processed_funding", []))
        engine._peak_equity = decimal_value(state.get("peak_equity", ZERO))
        engine._max_drawdown_percent = decimal_value(state.get("max_drawdown_percent", ZERO))
        engine.last_trade_price = None if state.get("last_trade_price") is None else decimal_value(state["last_trade_price"])
        engine.last_mark_price = None if state.get("last_mark_price") is None else decimal_value(state["last_mark_price"])
        engine._next_liquidation_id = int(state.get("next_liquidation_id", len(engine.liquidation_events) + 1))
        return engine


__all__ = ["FundingSettlement", "FuturesEngine", "LiquidationEvent"]
