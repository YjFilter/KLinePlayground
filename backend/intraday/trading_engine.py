from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import pandas as pd

from .advance_executor import AdvanceCallbacks, AdvanceExecutionResult, execute_advance
from .models import ReplayAdvance, ReplayPeriod
from .replay_clock import ReplayClock
from .trading_context import PreviousCloseIndex


@dataclass
class IntradayTradingCallbacks(AdvanceCallbacks):
    base_bars: pd.DataFrame
    previous_closes: PreviousCloseIndex
    simulator: Any
    order_manager: Any
    stock_code: str
    display_period: ReplayPeriod | str

    def __post_init__(self) -> None:
        frame = self.base_bars.copy()
        frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
        if frame["datetime"].isna().any():
            raise ValueError("base_bars contains invalid datetime values")
        if frame["datetime"].duplicated().any():
            raise ValueError("base_bars contains duplicate timestamps")
        if not frame["datetime"].is_monotonic_increasing:
            raise ValueError("base_bars timestamps must be strictly increasing")
        self._period = ReplayPeriod.parse(self.display_period).value
        self._bars = {
            timestamp.to_pydatetime(): ({**row.to_dict(), "datetime": timestamp}, index + 1)
            for index, (_, row) in enumerate(frame.iterrows())
            for timestamp in [row["datetime"]]
        }

    def fetch_base_bar(self, timestamp: datetime) -> dict[str, Any]:
        try:
            bar, _ = self._bars[timestamp]
        except KeyError as exc:
            raise ValueError(f"missing base bar for replay timestamp: {timestamp}") from exc
        return bar.copy()

    def update_price_and_state(self, timestamp: datetime, bar: dict[str, Any]) -> None:
        _, bar_id = self._bars[timestamp]
        self.simulator.update_current_price(float(bar["close"]), bar_id)

    def get_previous_close(self, trade_date: date) -> float | None:
        return self.previous_closes.previous_close_for_date(trade_date)

    def process_pending_orders(
        self,
        timestamp: datetime,
        bar: dict[str, Any],
        prev_close: float | None,
    ) -> list[dict[str, Any]]:
        trade_date = timestamp.date().isoformat()
        trade_time = timestamp.isoformat(sep=" ")
        return self.order_manager.process_bar(
            bar=bar,
            prev_close=prev_close,
            stock_code=self.stock_code,
            trade_date=trade_date,
            execute_buy=lambda quantity, price, order: self.simulator.buy(
                quantity,
                price,
                trade_date,
                reason=order.get("reason", ""),
                trade_time=trade_time,
                display_period=self._period,
            ),
            execute_sell=lambda quantity, price, order: self.simulator.sell(
                quantity,
                price,
                trade_date,
                reason=order.get("reason", ""),
                trade_time=trade_time,
                display_period=self._period,
            ),
        )


def execute_trading_advance(
    *,
    plan: ReplayAdvance,
    clock: ReplayClock,
    base_bars: pd.DataFrame,
    previous_closes: PreviousCloseIndex,
    simulator: Any,
    order_manager: Any,
    stock_code: str,
    display_period: ReplayPeriod | str,
) -> AdvanceExecutionResult:
    callbacks = IntradayTradingCallbacks(
        base_bars=base_bars,
        previous_closes=previous_closes,
        simulator=simulator,
        order_manager=order_manager,
        stock_code=stock_code,
        display_period=display_period,
    )
    return execute_advance(plan, callbacks, clock=clock)
