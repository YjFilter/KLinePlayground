from __future__ import annotations

from typing import Callable, Dict, List, Optional

from backend.market_rules import is_buy_blocked, is_sell_blocked


BuyCallback = Callable[[int, float, Dict], Dict]
SellCallback = Callable[[int, float, Dict], Dict]


class PendingOrderManager:
    def __init__(self):
        self._next_id = 1
        self.buy_orders: List[Dict] = []
        self.exit_orders: List[Dict] = []

    @property
    def active_buy_orders(self) -> List[Dict]:
        return [order for order in self.buy_orders if order["status"] == "active"]

    @property
    def active_exit_orders(self) -> List[Dict]:
        return [order for order in self.exit_orders if order["status"] == "active"]

    def clear(self):
        self.buy_orders = []
        self.exit_orders = []
        self._next_id = 1

    def add_buy_order(
        self,
        order_type: str,
        quantity: int,
        trigger_price: float,
        take_profit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        reason: str = "",
    ) -> Dict:
        if order_type not in {"limit", "breakout"}:
            raise ValueError("buy order_type must be limit or breakout")
        order = self._new_order(
            side="buy",
            order_type=order_type,
            quantity=quantity,
            trigger_price=trigger_price,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            reason=reason or "",
        )
        self.buy_orders.append(order)
        return order.copy()

    def add_exit_order(
        self,
        order_type: str,
        quantity: int,
        trigger_price: float,
        group_id: Optional[int] = None,
        reason: str = "",
    ) -> Dict:
        if order_type not in {"take_profit", "stop_loss"}:
            raise ValueError("exit order_type must be take_profit or stop_loss")
        order = self._new_order(
            side="sell",
            order_type=order_type,
            quantity=quantity,
            trigger_price=trigger_price,
            group_id=group_id,
            reason=reason or "",
        )
        self.exit_orders.append(order)
        return order.copy()

    def add_bracket_orders(
        self,
        quantity: int,
        take_profit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        base_reason: str = "",
    ) -> List[Dict]:
        group_id = self._next_id
        created = []
        if take_profit_price:
            created.append(self.add_exit_order("take_profit", quantity, float(take_profit_price), group_id=group_id, reason=f"止盈触发。{base_reason}".strip()))
        if stop_loss_price:
            created.append(self.add_exit_order("stop_loss", quantity, float(stop_loss_price), group_id=group_id, reason=f"止损触发。{base_reason}".strip()))
        return created

    def cancel_order(self, order_id: int) -> bool:
        for order in self.buy_orders + self.exit_orders:
            if order["id"] == order_id and order["status"] == "active":
                order["status"] = "cancelled"
                return True
        return False

    def process_bar(
        self,
        bar: Dict,
        prev_close: Optional[float],
        stock_code: str,
        trade_date: str,
        execute_buy: BuyCallback,
        execute_sell: SellCallback,
    ) -> List[Dict]:
        events: List[Dict] = []
        events.extend(self._process_exit_orders(bar, prev_close, stock_code, trade_date, execute_sell))
        events.extend(self._process_buy_orders(bar, prev_close, stock_code, trade_date, execute_buy))
        return events

    def to_dict(self) -> Dict:
        return {
            "buy_orders": [order.copy() for order in self.active_buy_orders],
            "exit_orders": [order.copy() for order in self.active_exit_orders],
        }

    def _new_order(self, **kwargs) -> Dict:
        quantity = int(kwargs["quantity"])
        trigger_price = float(kwargs["trigger_price"])
        if quantity <= 0:
            raise ValueError("quantity must be greater than 0")
        if trigger_price <= 0:
            raise ValueError("trigger_price must be greater than 0")

        order = {
            "id": self._next_id,
            "status": "active",
            **kwargs,
            "quantity": quantity,
            "trigger_price": trigger_price,
        }
        self._next_id += 1
        return order

    def _process_buy_orders(
        self,
        bar: Dict,
        prev_close: Optional[float],
        stock_code: str,
        trade_date: str,
        execute_buy: BuyCallback,
    ) -> List[Dict]:
        events: List[Dict] = []
        for order in list(self.active_buy_orders):
            fill_price = self._buy_fill_price(order, bar)
            if fill_price is None:
                continue

            if is_buy_blocked(stock_code, prev_close, fill_price):
                events.append(self._event(order, "blocked", fill_price, trade_date, "limit up blocks buy"))
                continue

            result = execute_buy(order["quantity"], fill_price, order)
            if result.get("success"):
                order["status"] = "filled"
                events.append(self._event(order, "filled", fill_price, trade_date, result.get("message", "")))
                self._create_exit_orders_for_buy(order)
            else:
                events.append(self._event(order, "rejected", fill_price, trade_date, result.get("message", "")))
        return events

    def _process_exit_orders(
        self,
        bar: Dict,
        prev_close: Optional[float],
        stock_code: str,
        trade_date: str,
        execute_sell: SellCallback,
    ) -> List[Dict]:
        events: List[Dict] = []
        ordered_exits = sorted(
            self.active_exit_orders,
            key=lambda order: (0 if order["order_type"] == "stop_loss" else 1, order["id"]),
        )
        handled_groups = set()

        for order in ordered_exits:
            group_id = order.get("group_id")
            if group_id is not None and group_id in handled_groups:
                continue

            fill_price = self._exit_fill_price(order, bar)
            if fill_price is None:
                continue

            if is_sell_blocked(stock_code, prev_close, fill_price):
                events.append(self._event(order, "blocked", fill_price, trade_date, "limit down blocks sell"))
                if order["order_type"] == "stop_loss":
                    break
                continue

            result = execute_sell(order["quantity"], fill_price, order)
            if result.get("success"):
                order["status"] = "filled"
                events.append(self._event(order, "filled", fill_price, trade_date, result.get("message", "")))
                if group_id is not None:
                    handled_groups.add(group_id)
                    self._cancel_sibling_exit_orders(group_id, keep_id=order["id"])
                if order["order_type"] == "stop_loss":
                    break
            else:
                events.append(self._event(order, "rejected", fill_price, trade_date, result.get("message", "")))
                if order["order_type"] == "stop_loss":
                    break
        return events

    def _create_exit_orders_for_buy(self, order: Dict):
        group_id = order["id"]
        take_profit_price = order.get("take_profit_price")
        stop_loss_price = order.get("stop_loss_price")

        if take_profit_price:
            self.add_exit_order("take_profit", order["quantity"], float(take_profit_price), group_id=group_id, reason=f"止盈触发。{order.get('reason', '')}".strip())
        if stop_loss_price:
            self.add_exit_order("stop_loss", order["quantity"], float(stop_loss_price), group_id=group_id, reason=f"止损触发。{order.get('reason', '')}".strip())

    def _cancel_sibling_exit_orders(self, group_id: int, keep_id: int):
        for order in self.active_exit_orders:
            if order.get("group_id") == group_id and order["id"] != keep_id:
                order["status"] = "cancelled"

    def _buy_fill_price(self, order: Dict, bar: Dict) -> Optional[float]:
        trigger = float(order["trigger_price"])
        if order["order_type"] == "limit":
            if float(bar["low"]) > trigger:
                return None
            return float(bar["open"]) if float(bar["open"]) <= trigger else trigger
        if order["order_type"] == "breakout":
            if float(bar["high"]) < trigger:
                return None
            return float(bar["open"]) if float(bar["open"]) >= trigger else trigger
        return None

    def _exit_fill_price(self, order: Dict, bar: Dict) -> Optional[float]:
        trigger = float(order["trigger_price"])
        if order["order_type"] == "stop_loss":
            if float(bar["low"]) > trigger:
                return None
            return float(bar["open"]) if float(bar["open"]) <= trigger else trigger
        if order["order_type"] == "take_profit":
            if float(bar["high"]) < trigger:
                return None
            return float(bar["open"]) if float(bar["open"]) >= trigger else trigger
        return None

    def _event(self, order: Dict, status: str, price: float, trade_date: str, message: str) -> Dict:
        return {
            "order_id": order["id"],
            "side": order["side"],
            "order_type": order["order_type"],
            "quantity": order["quantity"],
            "price": round(float(price), 2),
            "status": status,
            "date": trade_date,
            "message": message,
        }
