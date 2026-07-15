from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable

import pandas as pd

from .futures_engine import FuturesEngine
from .futures_models import decimal_value, timestamp_value
from .models import CryptoReplayAdvance, FundingEvent
from .replay_clock import CryptoReplayClock


class FuturesReplayExecutor:
    def __init__(
        self,
        *,
        clock: CryptoReplayClock,
        trade_bars: pd.DataFrame | Iterable[dict[str, Any]],
        mark_bars: pd.DataFrame | Iterable[dict[str, Any]],
        engine: FuturesEngine,
        funding_events: Iterable[FundingEvent] = (),
        symbol: str = "",
        source: str = "",
    ) -> None:
        self.clock = clock
        self.engine = engine
        self.symbol = symbol.upper()
        self.source = source
        self._trade_bars = self._index_bars(trade_bars, "trade")
        self._mark_bars = self._index_bars(mark_bars, "mark")
        self._funding_events = tuple(sorted(funding_events, key=lambda event: timestamp_value(event.timestamp)))
        if self.clock.current_time not in self._trade_bars:
            raise ValueError("current replay time is missing a trade bar")
        if self.clock.current_time not in self._mark_bars:
            raise ValueError("current replay time is missing a mark bar")
        current_trade = self._trade_bars[self.clock.current_time]
        current_mark = self._mark_bars[self.clock.current_time]
        self.engine.last_trade_price = current_trade["close"]
        self.engine.last_mark_price = current_mark["close"]
        self.engine.simulator.last_mark_price = current_mark["close"]

    @staticmethod
    def _index_bars(bars: pd.DataFrame | Iterable[dict[str, Any]], kind: str) -> dict[datetime, dict[str, Decimal]]:
        records = bars.to_dict("records") if isinstance(bars, pd.DataFrame) else list(bars)
        indexed = {}
        for record in records:
            if "timestamp" not in record:
                raise ValueError(f"{kind} bars require timestamps")
            timestamp = timestamp_value(record["timestamp"].to_pydatetime() if hasattr(record["timestamp"], "to_pydatetime") else record["timestamp"])
            indexed[timestamp] = {
                name: decimal_value(record[name]) for name in ("open", "high", "low", "close")
            }
        return indexed

    def submit_order(self, **order_data):
        order_data.setdefault("timestamp", self.clock.current_time)
        order_data.setdefault("current_price", self._trade_bars[self.clock.current_time]["close"])
        return self.engine.order_book.submit_order(**order_data)

    def advance(self) -> dict[str, Any]:
        plan = self.clock.plan_next()
        if plan.finished:
            result = self.snapshot()
            result["completed_times"] = []
            return result
        self._validate_plan_inputs(plan)
        for timestamp in plan.base_bar_times:
            self.engine.process_bar(
                timestamp=timestamp,
                trade_bar=self._trade_bars[timestamp],
                mark_bar=self._mark_bars[timestamp],
                funding_events=self._funding_events,
            )
        self.clock.advance(plan)
        result = self.snapshot()
        result["completed_times"] = [timestamp.isoformat() for timestamp in plan.base_bar_times]
        return result

    def on_bar(self, timestamp: datetime, _trade_row: Any = None) -> dict[str, Any]:
        normalized = timestamp_value(timestamp)
        if normalized not in self._trade_bars:
            raise ValueError(f"missing trade bar for {normalized.isoformat()}")
        if normalized not in self._mark_bars:
            raise ValueError(f"missing mark bar for {normalized.isoformat()}")
        return self.engine.process_bar(
            timestamp=normalized,
            trade_bar=self._trade_bars[normalized],
            mark_bar=self._mark_bars[normalized],
            funding_events=self._funding_events,
        )

    def _validate_plan_inputs(self, plan: CryptoReplayAdvance) -> None:
        for timestamp in plan.base_bar_times:
            if timestamp not in self._trade_bars:
                raise ValueError(f"missing trade bar for {timestamp.isoformat()}")
            if timestamp not in self._mark_bars:
                raise ValueError(f"missing mark bar for {timestamp.isoformat()}")

    def snapshot(self) -> dict[str, Any]:
        mark_price = self._mark_bars[self.clock.current_time]["close"]
        simulator_snapshot = self.engine.simulator.snapshot(mark_price)
        return {
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "symbol": self.symbol,
            "source": self.source,
            "current_time": self.clock.current_time.isoformat(),
            "active_period": self.clock.active_period.value,
            "finished": not self.clock.has_next(),
            "account": simulator_snapshot["account"],
            "position": simulator_snapshot["position"],
            "orders": self.engine.order_book.to_dict(),
            "fills": [fill.to_dict() for fill in self.engine.simulator.fills],
            "funding_events": [event.to_dict() for event in self.engine.funding_events],
            "liquidation_events": [event.to_dict() for event in self.engine.liquidation_events],
            "equity_snapshots": [self._serialize_equity(item) for item in self.engine.equity_snapshots],
            "trade_markers": self._trade_markers(),
        }

    def _trade_markers(self) -> list[dict[str, Any]]:
        markers = []
        marker_types = {"open_long": "L", "open_short": "S", "close": "X", "liquidation": "X"}
        for fill in self.engine.simulator.fills:
            marker_type = marker_types.get(fill.action)
            if marker_type is None:
                continue
            markers.append({
                "type": marker_type,
                "timestamp": fill.timestamp.isoformat(),
                "price": float(fill.price),
                "quantity": float(fill.quantity),
                "action": fill.action,
            })
        return markers

    @staticmethod
    def _serialize_equity(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "timestamp": item["timestamp"].isoformat(),
            "equity": float(item["equity"]),
            "balance": float(item["balance"]),
            "unrealized_pnl": float(item["unrealized_pnl"]),
            "mark_price": float(item["mark_price"]),
        }

    def state_signature(self) -> tuple[Any, ...]:
        account = self.engine.simulator.account
        position = self.engine.simulator.position
        return (
            self.clock.current_time,
            str(account.balance),
            str(account.used_margin),
            str(account.realized_pnl),
            str(account.total_fees),
            str(account.funding_paid),
            str(account.funding_received),
            str(position.quantity),
            str(position.entry_price),
            str(position.isolated_margin),
            tuple((order.order_id, order.status, order.fill_id) for order in self.engine.order_book.orders),
            tuple((fill.fill_id, fill.action, str(fill.quantity), str(fill.price), fill.timestamp) for fill in self.engine.simulator.fills),
            tuple(event.event_key for event in self.engine.funding_events),
            tuple(event.liquidation_id for event in self.engine.liquidation_events),
        )

    def export_state(self) -> dict[str, Any]:
        return {
            "version": 1,
            "symbol": self.symbol,
            "source": self.source,
            "clock": {
                "current_time": self.clock.current_time.isoformat(),
                "active_period": self.clock.active_period.value,
            },
            "simulator": self.engine.simulator.to_state(),
            "order_book": self.engine.order_book.to_state(),
            "engine": self.engine.to_state(),
        }

    @classmethod
    def from_state(
        cls, state: dict[str, Any], *, trade_bars, mark_bars,
        funding_events: Iterable[FundingEvent] = (),
    ) -> "FuturesReplayExecutor":
        from .futures_orders import FuturesOrderBook
        from .futures_simulator import FuturesSimulator

        simulator = FuturesSimulator.from_state(state["simulator"])
        order_book = FuturesOrderBook.from_state(simulator, state["order_book"])
        engine = FuturesEngine.from_state(simulator, order_book, state["engine"])
        records = trade_bars.to_dict("records") if isinstance(trade_bars, pd.DataFrame) else list(trade_bars)
        timestamps = [record["timestamp"] for record in records]
        clock = CryptoReplayClock(
            timestamps,
            initial_time=datetime.fromisoformat(state["clock"]["current_time"]),
            active_period=state["clock"]["active_period"],
        )
        return cls(
            clock=clock, trade_bars=trade_bars, mark_bars=mark_bars, engine=engine,
            funding_events=funding_events, symbol=state.get("symbol", ""), source=state.get("source", ""),
        )


def execute_futures_advance(**kwargs) -> dict[str, Any]:
    return FuturesReplayExecutor(**kwargs).advance()


__all__ = ["FuturesReplayExecutor", "execute_futures_advance"]
