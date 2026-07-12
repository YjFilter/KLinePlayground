from dataclasses import dataclass


@dataclass(frozen=True)
class LimitStatus:
    status: str
    limit_up: float
    limit_down: float
    limit_pct: float


def get_limit_percent(stock_code: str) -> float:
    code = str(stock_code or "").strip()
    if code.startswith(("30", "68")):
        return 0.20
    if code.startswith(("43", "83", "87", "92")):
        return 0.30
    return 0.10


def get_limit_prices(stock_code: str, prev_close: float) -> tuple[float, float, float]:
    limit_pct = get_limit_percent(stock_code)
    limit_up = round(float(prev_close) * (1 + limit_pct), 2)
    limit_down = round(float(prev_close) * (1 - limit_pct), 2)
    return limit_up, limit_down, limit_pct


def get_limit_status(
    stock_code: str,
    prev_close: float | None,
    price: float | None,
    tolerance: float = 0.001,
) -> LimitStatus:
    if not prev_close or prev_close <= 0 or price is None:
        limit_up, limit_down, limit_pct = get_limit_prices(stock_code, 0)
        return LimitStatus("normal", limit_up, limit_down, limit_pct)

    limit_up, limit_down, limit_pct = get_limit_prices(stock_code, prev_close)
    threshold = max(abs(float(prev_close)) * tolerance, 0.001)
    current_price = float(price)

    if current_price >= limit_up - threshold:
        status = "limit_up"
    elif current_price <= limit_down + threshold:
        status = "limit_down"
    else:
        status = "normal"

    return LimitStatus(status, limit_up, limit_down, limit_pct)


def is_buy_blocked(stock_code: str, prev_close: float | None, price: float | None) -> bool:
    return get_limit_status(stock_code, prev_close, price).status == "limit_up"


def is_sell_blocked(stock_code: str, prev_close: float | None, price: float | None) -> bool:
    return get_limit_status(stock_code, prev_close, price).status == "limit_down"
