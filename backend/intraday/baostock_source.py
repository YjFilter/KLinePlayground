from __future__ import annotations

from datetime import datetime

import pandas as pd

NORMALIZED_COLUMNS = ["datetime", "open", "high", "low", "close", "volume", "amount"]
BAOSTOCK_FIELDS = "date,time,code,open,high,low,close,volume,amount,adjustflag"


class IntradaySourceError(RuntimeError):
    pass


def _to_baostock_symbol(stock_code: str) -> str:
    code = str(stock_code).strip().split(".")[0]
    if len(code) != 6 or not code.isdigit():
        raise ValueError(f"invalid A-share stock code: {stock_code}")
    if code.startswith(("43", "83", "87", "92")):
        raise IntradaySourceError(
            f"BaoStock does not provide Beijing Stock Exchange 30m data: {code}"
        )
    market = "sh" if code.startswith(("5", "6", "9")) else "sz"
    return f"{market}.{code}"


class BaoStockSource:
    def __init__(self, api=None):
        if api is None:
            import baostock as api
        self.api = api

    def fetch_30m(self, stock_code: str, start: datetime, end: datetime) -> pd.DataFrame:
        symbol = _to_baostock_symbol(stock_code)
        login_result = self.api.login()
        if login_result.error_code != "0":
            raise IntradaySourceError(f"BaoStock login failed: {login_result.error_msg}")
        try:
            result = self.api.query_history_k_data_plus(
                symbol,
                BAOSTOCK_FIELDS,
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                frequency="30",
                adjustflag="3",
            )
            if result.error_code != "0":
                raise IntradaySourceError(f"BaoStock query failed: {result.error_msg}")
            rows = []
            while result.next():
                rows.append(result.get_row_data())
            if not rows:
                return pd.DataFrame(columns=NORMALIZED_COLUMNS)
            frame = pd.DataFrame(rows, columns=result.fields)
            frame["datetime"] = pd.to_datetime(frame["time"].astype(str).str[:14], format="%Y%m%d%H%M%S")
            for column in NORMALIZED_COLUMNS[1:]:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
            frame = frame[NORMALIZED_COLUMNS]
            return frame.sort_values("datetime").drop_duplicates("datetime", keep="last").reset_index(drop=True)
        finally:
            self.api.logout()

