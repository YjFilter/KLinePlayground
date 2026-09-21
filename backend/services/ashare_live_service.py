"""
A股实时行情服务层 (A-Share Live Service)
负责通过公开免费行情通道拉取：
1. 股票拼音/代码联想搜索 (EastMoney Suggest API)
2. 1分钟分时 K 线历史与当日走势 (EastMoney Kline API)
3. 实时最新行情快照 (Tencent Finance API)
"""
import json
import logging
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def search_stocks(query: str, limit: int = 10) -> List[Dict[str, str]]:
    """
    根据输入的股票代码或拼音缩写（如 '600519' 或 'gzmt'）搜索股票
    """
    if not query or not query.strip():
        return []
    clean_query = query.strip()
    encoded_query = urllib.parse.quote(clean_query)
    url = f"https://searchapi.eastmoney.com/api/suggest/get?input={encoded_query}&type=14"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=4) as resp:
            raw_data = resp.read().decode("utf-8")
            data = json.loads(raw_data)
            items = data.get("QuotationCodeTable", {}).get("Data", []) or []
            
            results = []
            for item in items:
                code = item.get("Code", "")
                name = item.get("Name", "")
                market_type = item.get("SecurityTypeName", "")
                # 过滤 A 股普通股票与主要指数
                if code and name:
                    quote_id = str(item.get("QuoteID", ""))
                    mkt_num = str(item.get("MktNum", ""))
                    if quote_id.startswith("1.") or mkt_num == "1":
                        prefix = "sh"
                    elif quote_id.startswith("0.") or mkt_num == "0":
                        prefix = "sz"
                    elif quote_id.startswith("2.") or mkt_num in ("2", "3"):
                        prefix = "bj"
                    else:
                        prefix = "sh" if code.startswith(("6", "9", "5", "11")) else "sz" if code.startswith(("0", "3", "12", "15", "18")) else "bj"
                    results.append({
                        "code": code,
                        "name": name,
                        "symbol": f"{prefix}{code}",
                        "market_type": market_type
                    })
                if len(results) >= limit:
                    break
            return results
    except Exception as e:
        logger.warning(f"搜索股票失败 query={query}: {e}")
        return []


from datetime import datetime, time, timezone
from collections import OrderedDict


def get_secid(symbol_or_code: str) -> str:
    """
    转换股票代码为东财 secid (例如 600519 -> 1.600519, 000001 -> 0.000001, sh000001 -> 1.000001, sz000001 -> 0.000001)
    """
    clean_sym = str(symbol_or_code or "").strip()
    low = clean_sym.lower()
    if low.startswith("sh"):
        return f"1.{low[2:]}"
    elif low.startswith("sz"):
        return f"0.{low[2:]}"
    elif low.startswith("bj"):
        return f"0.{low[2:]}"
    
    code = clean_sym
    if code.startswith(("6", "9", "5", "11")):
        return f"1.{code}"
    return f"0.{code}"


def get_ashare_bucket_time(dt: datetime, period: str) -> datetime:
    """
    计算 A 股交易时段的聚合周期时间边界
    A股交易时间：上午 09:30-11:30 (120分钟)，下午 13:00-15:00 (120分钟)
    """
    t = dt.time()
    p = period.lower()
    if p in ("3m",):
        interval = 3
    elif p in ("5m",):
        interval = 5
    elif p in ("15m",):
        interval = 15
    elif p in ("30m",):
        interval = 30
    elif p in ("60m", "1h"):
        interval = 60
    elif p in ("120m", "2h"):
        interval = 120
    elif p in ("240m", "4h", "4h_session", "3h", "6h", "8h", "12h"):
        return dt.replace(hour=15, minute=0, second=0, microsecond=0)
    else:
        return dt

    if time(9, 15) <= t <= time(11, 30):
        passed = (dt.hour - 9) * 60 + dt.minute - 30
        bucket_offset = interval if passed <= 0 else ((passed - 1) // interval + 1) * interval
        bucket_mins = min(9 * 60 + 30 + bucket_offset, 11 * 60 + 30)
        return dt.replace(hour=bucket_mins // 60, minute=bucket_mins % 60, second=0, microsecond=0)
    elif time(13, 0) <= t <= time(15, 0):
        passed = (dt.hour - 13) * 60 + dt.minute
        bucket_offset = interval if passed <= 0 else ((passed - 1) // interval + 1) * interval
        bucket_mins = min(13 * 60 + bucket_offset, 15 * 60)
        return dt.replace(hour=bucket_mins // 60, minute=bucket_mins % 60, second=0, microsecond=0)
    return dt


def parse_raw_kline_bar(b: list) -> Optional[Dict[str, Any]]:
    """解析单根原始 K 线数据并按 UTC 墙上时间打时间戳"""
    if len(b) < 6:
        return None
    t_str = str(b[0])
    try:
        open_p = float(b[1])
        close_p = float(b[2])
        high_p = float(b[3])
        low_p = float(b[4])
        vol = float(b[5])
    except (ValueError, TypeError):
        return None

    if len(t_str) == 12:
        dt = datetime.strptime(t_str, "%Y%m%d%H%M")
        disp_time = dt.strftime("%Y-%m-%d %H:%M")
    elif len(t_str) == 8:
        dt = datetime.strptime(t_str, "%Y%m%d")
        disp_time = dt.strftime("%Y-%m-%d")
    elif "-" in t_str:
        dt = datetime.strptime(t_str, "%Y-%m-%d %H:%M" if ":" in t_str else "%Y-%m-%d")
        disp_time = dt.strftime("%Y-%m-%d %H:%M" if ":" in t_str else "%Y-%m-%d")
    else:
        return None

    ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
    color = "rgba(246, 70, 93, 0.7)" if close_p >= open_p else "rgba(14, 203, 129, 0.7)"
    return {
        "dt": dt,
        "time": ts,
        "time_str": disp_time,
        "open": open_p,
        "high": high_p,
        "low": low_p,
        "close": close_p,
        "volume": vol,
        "color": color
    }


def aggregate_ashare_bars(raw_1m_bars: list, period: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    根据 1 分钟基础分时数据，动态聚合生成目标周期的 K 线与成交量数组
    """
    if not raw_1m_bars:
        return [], []

    parsed_bars = []
    for b in raw_1m_bars:
        parsed = parse_raw_kline_bar(b)
        if parsed:
            parsed_bars.append(parsed)

    if not parsed_bars:
        return [], []

    if period == "1m":
        bars = []
        volumes = []
        for item in parsed_bars:
            bars.append({
                "time": item["time"],
                "time_str": item["time_str"],
                "open": item["open"],
                "high": item["high"],
                "low": item["low"],
                "close": item["close"]
            })
            volumes.append({
                "time": item["time"],
                "value": item["volume"],
                "color": item["color"]
            })
        return bars, volumes

    # 聚合指定周期
    groups = OrderedDict()
    for item in parsed_bars:
        bucket_dt = get_ashare_bucket_time(item["dt"], period)
        if bucket_dt not in groups:
            groups[bucket_dt] = []
        groups[bucket_dt].append(item)

    bars = []
    volumes = []
    for bucket_dt, bucket_items in groups.items():
        o = bucket_items[0]["open"]
        c = bucket_items[-1]["close"]
        h = max(x["high"] for x in bucket_items)
        l = min(x["low"] for x in bucket_items)
        v = sum(x["volume"] for x in bucket_items)
        ts = int(bucket_dt.replace(tzinfo=timezone.utc).timestamp())
        display_time = bucket_dt.strftime("%Y-%m-%d %H:%M")

        bars.append({
            "time": ts,
            "time_str": display_time,
            "open": o,
            "high": h,
            "low": l,
            "close": c
        })
        volumes.append({
            "time": ts,
            "value": v,
            "color": "rgba(246, 70, 93, 0.7)" if c >= o else "rgba(14, 203, 129, 0.7)"
        })

    return bars, volumes


def get_minute_klines(symbol_or_code: str, period: str = "1m", limit: int = 240) -> Dict[str, Any]:
    """
    获取 A 股分时/日K/周K数据，全面支持与币圈完全一致的 16 个周期：
    1m, 3m, 5m, 15m, 30m, 1h, 2h, 3h, 4h, 6h, 8h, 12h, daily, 2d, 3d, weekly
    """
    clean_sym = symbol_or_code.strip()
    if clean_sym.startswith(("sh", "sz", "bj")):
        prefix = clean_sym[:2].lower()
        code = clean_sym[2:]
    else:
        code = clean_sym
        prefix = "sh" if code.startswith(("6", "9", "5", "11")) else "sz" if code.startswith(("0", "3", "12", "15", "18")) else "bj"
    qt_symbol = f"{prefix}{code}"

    p_norm = period.lower()

    try:
        # 1. 月K (monthly, month, mon) 与 周K (weekly, 1w)
        if p_norm in ("monthly", "month", "mon") or period == "1M":
            tx_url = f"https://ifzq.gtimg.cn/appstock/app/kline/kline?param={qt_symbol},month,,,{limit}"
            req = urllib.request.Request(tx_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            stock_data = data.get("data", {}).get(qt_symbol, {})
            qt_info = stock_data.get("qt", {}).get(qt_symbol, [])
            stock_name = qt_info[1] if len(qt_info) > 1 else code
            raw_bars = stock_data.get("month", []) or []

            bars = []
            volumes = []
            for b in raw_bars:
                parsed = parse_raw_kline_bar(b)
                if parsed:
                    bars.append({
                        "time": parsed["time"],
                        "time_str": parsed["time_str"],
                        "open": parsed["open"],
                        "high": parsed["high"],
                        "low": parsed["low"],
                        "close": parsed["close"]
                    })
                    volumes.append({
                        "time": parsed["time"],
                        "value": parsed["volume"],
                        "color": parsed["color"]
                    })
            return {
                "code": code,
                "name": stock_name,
                "period": period,
                "kline_data": bars,
                "volume_data": volumes,
                "count": len(bars)
            }

        if p_norm in ("weekly", "1w", "week"):
            tx_url = f"https://ifzq.gtimg.cn/appstock/app/kline/kline?param={qt_symbol},week,,,{limit}"
            req = urllib.request.Request(tx_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            stock_data = data.get("data", {}).get(qt_symbol, {})
            qt_info = stock_data.get("qt", {}).get(qt_symbol, [])
            stock_name = qt_info[1] if len(qt_info) > 1 else code
            raw_bars = stock_data.get("week", []) or []

            bars = []
            volumes = []
            for b in raw_bars:
                parsed = parse_raw_kline_bar(b)
                if parsed:
                    bars.append({
                        "time": parsed["time"],
                        "time_str": parsed["time_str"],
                        "open": parsed["open"],
                        "high": parsed["high"],
                        "low": parsed["low"],
                        "close": parsed["close"]
                    })
                    volumes.append({
                        "time": parsed["time"],
                        "value": parsed["volume"],
                        "color": parsed["color"]
                    })
            return {
                "code": code,
                "name": stock_name,
                "period": period,
                "kline_data": bars,
                "volume_data": volumes,
                "count": len(bars)
            }

        # 2. 日K (daily, 1d) 与多日周期 (2d, 3d)
        if p_norm in ("daily", "1d", "day", "2d", "3d"):
            fetch_limit = limit if p_norm in ("daily", "1d", "day") else max(limit * 3, 120)
            tx_daily_url = f"https://ifzq.gtimg.cn/appstock/app/kline/kline?param={qt_symbol},day,,,{fetch_limit}"
            req_daily = urllib.request.Request(tx_daily_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req_daily, timeout=5) as resp:
                daily_raw = json.loads(resp.read().decode("utf-8"))
            stock_data = daily_raw.get("data", {}).get(qt_symbol, {})
            qt_info = stock_data.get("qt", {}).get(qt_symbol, [])
            stock_name = qt_info[1] if len(qt_info) > 1 else code
            raw_day_bars = stock_data.get("day", []) or []

            bars = []
            volumes = []
            for b in raw_day_bars:
                parsed = parse_raw_kline_bar(b)
                if parsed:
                    bars.append({
                        "time": parsed["time"],
                        "time_str": parsed["time_str"],
                        "open": parsed["open"],
                        "high": parsed["high"],
                        "low": parsed["low"],
                        "close": parsed["close"]
                    })
                    volumes.append({
                        "time": parsed["time"],
                        "value": parsed["volume"],
                        "color": parsed["color"]
                    })

            # 用今日 1m 实时数据动态合成今日最新日K棒并覆盖/追加
            try:
                tx_1m_url = f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={qt_symbol},m1,,241"
                req_1m = urllib.request.Request(tx_1m_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req_1m, timeout=4) as resp_1m:
                    data_1m = json.loads(resp_1m.read().decode("utf-8"))
                m1_bars = data_1m.get("data", {}).get(qt_symbol, {}).get("m1", []) or []
                if m1_bars:
                    last_m1_date = m1_bars[-1][0][:8]  # YYYYMMDD
                    today_m1 = [b for b in m1_bars if b[0].startswith(last_m1_date)]
                    if today_m1:
                        synth_o = float(today_m1[0][1])
                        synth_c = float(today_m1[-1][2])
                        synth_h = max(float(x[3]) for x in today_m1)
                        synth_l = min(float(x[4]) for x in today_m1)
                        synth_v = sum(float(x[5]) for x in today_m1)
                        synth_dt = datetime.strptime(last_m1_date, "%Y%m%d")
                        synth_ts = int(synth_dt.replace(tzinfo=timezone.utc).timestamp())
                        synth_time_str = synth_dt.strftime("%Y-%m-%d")

                        synth_bar = {
                            "time": synth_ts,
                            "time_str": synth_time_str,
                            "open": synth_o,
                            "high": synth_h,
                            "low": synth_l,
                            "close": synth_c
                        }
                        synth_vol = {
                            "time": synth_ts,
                            "value": synth_v,
                            "color": "rgba(246, 70, 93, 0.7)" if synth_c >= synth_o else "rgba(14, 203, 129, 0.7)"
                        }

                        if bars and bars[-1]["time_str"] == synth_time_str:
                            bars[-1] = synth_bar
                            volumes[-1] = synth_vol
                        else:
                            bars.append(synth_bar)
                            volumes.append(synth_vol)
            except Exception as synth_err:
                logger.warning(f"合成今日实时日K异常: {synth_err}")

            if p_norm in ("2d", "3d"):
                chunk_size = 2 if p_norm == "2d" else 3
                agg_bars = []
                agg_vols = []
                for i in range(0, len(bars), chunk_size):
                    chunk = bars[i:i + chunk_size]
                    if not chunk:
                        continue
                    v_chunk = volumes[i:i + chunk_size]
                    o = chunk[0]["open"]
                    c = chunk[-1]["close"]
                    h = max(x["high"] for x in chunk)
                    l = min(x["low"] for x in chunk)
                    v = sum(x["value"] for x in v_chunk)
                    t = chunk[-1]["time"]
                    t_str = chunk[-1]["time_str"]
                    agg_bars.append({
                        "time": t, "time_str": t_str, "open": o, "high": h, "low": l, "close": c
                    })
                    agg_vols.append({
                        "time": t, "value": v, "color": "rgba(246, 70, 93, 0.7)" if c >= o else "rgba(14, 203, 129, 0.7)"
                    })
                bars = agg_bars[-limit:]
                volumes = agg_vols[-limit:]
            else:
                bars = bars[-limit:]
                volumes = volumes[-limit:]

            return {
                "code": code,
                "name": stock_name,
                "period": period,
                "kline_data": bars,
                "volume_data": volumes,
                "count": len(bars)
            }

        # 3. 分时直出周期 (5m, 15m, 30m, 60m/1h) 优先使用原生接口
        native_map = {
            "5m": "m5",
            "15m": "m15",
            "30m": "m30",
            "60m": "m60",
            "1h": "m60"
        }
        if p_norm in native_map:
            tx_p = native_map[p_norm]
            tx_url = f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={qt_symbol},{tx_p},,{limit}"
            req = urllib.request.Request(tx_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            stock_data = data.get("data", {}).get(qt_symbol, {})
            qt_info = stock_data.get("qt", {}).get(qt_symbol, [])
            stock_name = qt_info[1] if len(qt_info) > 1 else code
            raw_bars = stock_data.get(tx_p, []) or []
            bars = []
            volumes = []
            for b in raw_bars:
                parsed = parse_raw_kline_bar(b)
                if parsed:
                    bars.append({
                        "time": parsed["time"],
                        "time_str": parsed["time_str"],
                        "open": parsed["open"],
                        "high": parsed["high"],
                        "low": parsed["low"],
                        "close": parsed["close"]
                    })
                    volumes.append({
                        "time": parsed["time"],
                        "value": parsed["volume"],
                        "color": parsed["color"]
                    })
            return {
                "code": code,
                "name": stock_name,
                "period": period,
                "kline_data": bars,
                "volume_data": volumes,
                "count": len(bars)
            }

        # 4. 高小时级分时 (2h, 3h, 4h, 6h, 8h, 12h) 基于 m60 聚合
        if p_norm in ("2h", "120m", "4h", "240m", "4h_session", "3h", "6h", "8h", "12h"):
            fetch_count = 800
            tx_url = f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={qt_symbol},m60,,{fetch_count}"
            req = urllib.request.Request(tx_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            stock_data = data.get("data", {}).get(qt_symbol, {})
            qt_info = stock_data.get("qt", {}).get(qt_symbol, [])
            stock_name = qt_info[1] if len(qt_info) > 1 else code
            raw_bars = stock_data.get("m60", []) or []
            parsed_m60 = [parse_raw_kline_bar(b) for b in raw_bars if parse_raw_kline_bar(b)]

            bars = []
            volumes = []

            if p_norm in ("2h", "120m"):
                # 2h: 每日分为两根 (09:30-11:30 对应 11:30; 13:00-15:00 对应 15:00)
                groups = OrderedDict()
                for item in parsed_m60:
                    dt = item["dt"]
                    bucket_dt = dt.replace(hour=11, minute=30, second=0, microsecond=0) if dt.hour <= 11 else dt.replace(hour=15, minute=0, second=0, microsecond=0)
                    if bucket_dt not in groups:
                        groups[bucket_dt] = []
                    groups[bucket_dt].append(item)
                for bucket_dt, items in groups.items():
                    o = items[0]["open"]
                    c = items[-1]["close"]
                    h = max(x["high"] for x in items)
                    l = min(x["low"] for x in items)
                    v = sum(x["volume"] for x in items)
                    ts = int(bucket_dt.replace(tzinfo=timezone.utc).timestamp())
                    bars.append({
                        "time": ts,
                        "time_str": bucket_dt.strftime("%Y-%m-%d %H:%M"),
                        "open": o,
                        "high": h,
                        "low": l,
                        "close": c
                    })
                    volumes.append({
                        "time": ts,
                        "value": v,
                        "color": "rgba(246, 70, 93, 0.7)" if c >= o else "rgba(14, 203, 129, 0.7)"
                    })
            elif p_norm in ("4h", "240m", "4h_session"):
                # 4h: 整个A股交易日为4小时，聚合为 1 根 15:00
                groups = OrderedDict()
                for item in parsed_m60:
                    dt = item["dt"]
                    bucket_dt = dt.replace(hour=15, minute=0, second=0, microsecond=0)
                    if bucket_dt not in groups:
                        groups[bucket_dt] = []
                    groups[bucket_dt].append(item)
                for bucket_dt, items in groups.items():
                    o = items[0]["open"]
                    c = items[-1]["close"]
                    h = max(x["high"] for x in items)
                    l = min(x["low"] for x in items)
                    v = sum(x["volume"] for x in items)
                    ts = int(bucket_dt.replace(tzinfo=timezone.utc).timestamp())
                    bars.append({
                        "time": ts,
                        "time_str": bucket_dt.strftime("%Y-%m-%d %H:%M"),
                        "open": o,
                        "high": h,
                        "low": l,
                        "close": c
                    })
                    volumes.append({
                        "time": ts,
                        "value": v,
                        "color": "rgba(246, 70, 93, 0.7)" if c >= o else "rgba(14, 203, 129, 0.7)"
                    })
            else:
                # 3h, 6h, 8h, 12h: 按相应连续 60m 根数聚合
                chunk_size = 3 if p_norm == "3h" else 6 if p_norm == "6h" else 8 if p_norm == "8h" else 12
                for i in range(0, len(parsed_m60), chunk_size):
                    chunk = parsed_m60[i:i + chunk_size]
                    if not chunk:
                        continue
                    o = chunk[0]["open"]
                    c = chunk[-1]["close"]
                    h = max(x["high"] for x in chunk)
                    l = min(x["low"] for x in chunk)
                    v = sum(x["volume"] for x in chunk)
                    ts = chunk[-1]["time"]
                    t_str = chunk[-1]["time_str"]
                    bars.append({
                        "time": ts,
                        "time_str": t_str,
                        "open": o,
                        "high": h,
                        "low": l,
                        "close": c
                    })
                    volumes.append({
                        "time": ts,
                        "value": v,
                        "color": "rgba(246, 70, 93, 0.7)" if c >= o else "rgba(14, 203, 129, 0.7)"
                    })

            return {
                "code": code,
                "name": stock_name,
                "period": period,
                "kline_data": bars[-limit:],
                "volume_data": volumes[-limit:],
                "count": len(bars[-limit:])
            }

        # 5. 1m 和 3m 由底层 1m 动态聚合
        tx_1m_url = f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={qt_symbol},m1,,640"
        req_1m = urllib.request.Request(tx_1m_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req_1m, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        stock_data = data.get("data", {}).get(qt_symbol, {})
        qt_info = stock_data.get("qt", {}).get(qt_symbol, [])
        stock_name = qt_info[1] if len(qt_info) > 1 else code
        raw_1m_bars = stock_data.get("m1", []) or []

        bars, volumes = aggregate_ashare_bars(raw_1m_bars, p_norm)
        return {
            "code": code,
            "name": stock_name,
            "period": period,
            "kline_data": bars[-limit:],
            "volume_data": volumes[-limit:],
            "count": len(bars[-limit:])
        }
    except Exception as e:
        logger.warning(f"腾讯行情服务拉取/合成走势异常 code={code}: {e}，尝试备用接口...")

    # 备用方案：东财 HTTP 接口
    secid = get_secid(qt_symbol)
    if p_norm in ("monthly", "month", "mon") or period == "1M":
        base_klt = "103"
        pull_limit = limit
    elif p_norm in ("weekly", "1w", "week"):
        base_klt = "102"
        pull_limit = limit
    elif p_norm in ("daily", "1d", "day"):
        base_klt = "101"
        pull_limit = limit
    elif p_norm in ("2d", "3d"):
        base_klt = "101"
        pull_limit = limit * 3
    elif p_norm in ("2h", "120m", "4h", "240m", "4h_session", "3h", "6h", "8h", "12h"):
        base_klt = "60"
        pull_limit = max(limit * 12, 360)
    elif p_norm == "3m":
        base_klt = "1"
        pull_limit = min(limit * 3, 640)
    elif p_norm in ("1m", "5m", "15m", "30m", "60m", "1h"):
        klt_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60", "1h": "60"}
        base_klt = klt_map[p_norm]
        pull_limit = limit
    else:
        base_klt = "1"
        pull_limit = limit

    url = (
        f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
        f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6&"
        f"fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&"
        f"klt={base_klt}&fqt=1&end=20500101&lmt={pull_limit}"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            kline_payload = data.get("data") or {}
            raw_klines = kline_payload.get("klines", []) or []
            stock_name = kline_payload.get("name", code)
            bars = []
            volumes = []

            for line in raw_klines:
                parts = line.split(",")
                if len(parts) < 6:
                    continue
                time_str = parts[0]
                open_p = float(parts[1])
                close_p = float(parts[2])
                high_p = float(parts[3])
                low_p = float(parts[4])
                vol = float(parts[5])
                dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M" if ":" in time_str else "%Y-%m-%d")
                timestamp = int(dt.replace(tzinfo=timezone.utc).timestamp())
                bars.append({
                    "dt": dt,
                    "time": timestamp,
                    "time_str": time_str,
                    "open": open_p,
                    "high": high_p,
                    "low": low_p,
                    "close": close_p,
                    "volume": vol
                })
                volumes.append({
                    "time": timestamp,
                    "value": vol,
                    "color": "rgba(246, 70, 93, 0.7)" if close_p >= open_p else "rgba(14, 203, 129, 0.7)"
                })

            if p_norm == "3m" and base_klt == "1":
                # 将 1m bars 聚合为 3m
                raw_1m_for_agg = [[b["dt"].strftime("%Y%m%d%H%M"), b["open"], b["close"], b["high"], b["low"], b["volume"]] for b in bars]
                bars, volumes = aggregate_ashare_bars(raw_1m_for_agg, "3m")
            elif p_norm in ("2d", "3d") and base_klt == "101":
                chunk_size = 2 if p_norm == "2d" else 3
                agg_bars = []
                agg_vols = []
                for i in range(0, len(bars), chunk_size):
                    chunk = bars[i:i + chunk_size]
                    if not chunk:
                        continue
                    v_chunk = volumes[i:i + chunk_size]
                    o = chunk[0]["open"]
                    c = chunk[-1]["close"]
                    h = max(x["high"] for x in chunk)
                    l = min(x["low"] for x in chunk)
                    v = sum(x["value"] for x in v_chunk)
                    ts = chunk[-1]["time"]
                    t_str = chunk[-1]["time_str"]
                    agg_bars.append({"time": ts, "time_str": t_str, "open": o, "high": h, "low": l, "close": c})
                    agg_vols.append({"time": ts, "value": v, "color": "rgba(246, 70, 93, 0.7)" if c >= o else "rgba(14, 203, 129, 0.7)"})
                bars = agg_bars
                volumes = agg_vols
            elif p_norm in ("2h", "120m", "4h", "240m", "4h_session", "3h", "6h", "8h", "12h") and base_klt == "60":
                chunk_size = 2 if p_norm in ("2h", "120m") else 4 if p_norm in ("4h", "240m", "4h_session") else (3 if p_norm == "3h" else 6 if p_norm == "6h" else 8 if p_norm == "8h" else 12)
                agg_bars = []
                agg_vols = []
                for i in range(0, len(bars), chunk_size):
                    chunk = bars[i:i + chunk_size]
                    if not chunk:
                        continue
                    v_chunk = volumes[i:i + chunk_size]
                    o = chunk[0]["open"]
                    c = chunk[-1]["close"]
                    h = max(x["high"] for x in chunk)
                    l = min(x["low"] for x in chunk)
                    v = sum(x["value"] for x in v_chunk)
                    ts = chunk[-1]["time"]
                    t_str = chunk[-1]["time_str"]
                    agg_bars.append({"time": ts, "time_str": t_str, "open": o, "high": h, "low": l, "close": c})
                    agg_vols.append({"time": ts, "value": v, "color": "rgba(246, 70, 93, 0.7)" if c >= o else "rgba(14, 203, 129, 0.7)"})
                bars = agg_bars
                volumes = agg_vols

            # 清理临时 dt 字段
            cleaned_bars = []
            for b in bars:
                cleaned_bars.append({
                    "time": b["time"],
                    "time_str": b["time_str"],
                    "open": b["open"],
                    "high": b["high"],
                    "low": b["low"],
                    "close": b["close"]
                })

            return {
                "code": code,
                "name": stock_name,
                "period": period,
                "kline_data": cleaned_bars[-limit:],
                "volume_data": volumes[-limit:],
                "count": len(cleaned_bars[-limit:])
            }
    except Exception as e:
        logger.error(f"东财分时K线接口也失败 code={code}: {e}")
        return {
            "code": code,
            "name": code,
            "period": period,
            "kline_data": [],
            "volume_data": [],
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"获取A股分时K线失败 code={code}: {e}")
        return {
            "code": code,
            "name": code,
            "period": period,
            "kline_data": [],
            "volume_data": [],
            "error": str(e)
        }


def get_realtime_snapshot(symbol_or_code: str) -> Dict[str, Any]:
    """
    通过腾讯财经接口获取单只股票的实时行情快照 (买一卖一、现价、涨跌幅、昨收等)
    """
    clean_sym = symbol_or_code.strip()
    if clean_sym.startswith(("sh", "sz", "bj")):
        prefix = clean_sym[:2].lower()
        code = clean_sym[2:]
    else:
        code = clean_sym
        prefix = "sh" if code.startswith(("6", "9", "5", "11")) else "sz" if code.startswith(("0", "3", "12", "15", "18")) else "bj"
    qt_symbol = f"{prefix}{code}"
    
    url = f"http://qt.gtimg.cn/q={qt_symbol}"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=4) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            if "~" not in content:
                return {"code": code, "error": "未查找到股票数据"}
            
            raw_data = content.split('="')[1].split('";')[0]
            fields = raw_data.split("~")
            if len(fields) < 35:
                return {"code": code, "error": "数据格式异常"}
            
            name = fields[1]
            code = fields[2]
            current_price = float(fields[3]) if fields[3] else 0.0
            prev_close = float(fields[4]) if fields[4] else 0.0
            open_price = float(fields[5]) if fields[5] else 0.0
            volume_shares = float(fields[6]) if fields[6] else 0.0
            high_price = float(fields[33]) if fields[33] else current_price
            low_price = float(fields[34]) if fields[34] else current_price
            change_amount = float(fields[31]) if fields[31] else 0.0
            change_percent = float(fields[32]) if fields[32] else 0.0
            time_str = fields[30] if len(fields) > 30 else ""
            turnover_val = float(fields[37]) if len(fields) > 37 and fields[37] else 0.0
            amplitude_val = float(fields[43]) if len(fields) > 43 and fields[43] else (round((high_price - low_price) / prev_close * 100, 2) if prev_close > 0 else 0.0)
            
            buy1_price = float(fields[9]) if fields[9] else current_price
            buy1_vol = int(fields[10]) if fields[10] else 0
            sell1_price = float(fields[19]) if fields[19] else current_price
            sell1_vol = int(fields[20]) if fields[20] else 0
            
            limit_up = round(prev_close * 1.10, 2)
            limit_down = round(prev_close * 0.90, 2)
            if code.startswith(("30", "68")):
                limit_up = round(prev_close * 1.20, 2)
                limit_down = round(prev_close * 0.80, 2)
                
            return {
                "code": code,
                "symbol": f"{prefix}{code}",
                "name": name,
                "price": current_price,
                "prev_close": prev_close,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "volume": volume_shares,
                "turnover": turnover_val,
                "amplitude": amplitude_val,
                "change": change_amount,
                "change_percent": change_percent,
                "time_str": time_str,
                "limit_up": limit_up,
                "limit_down": limit_down,
                "buy1_price": buy1_price,
                "buy1_vol": buy1_vol,
                "sell1_price": sell1_price,
                "sell1_vol": sell1_vol
            }
    except Exception as e:
        logger.error(f"获取A股实时快照失败 {qt_symbol}: {e}")
        return {"code": code, "error": str(e)}


def get_batch_snapshots(symbols_or_codes: List[str]) -> List[Dict[str, Any]]:
    """
    批量获取多只股票的实时行情快照 (用于自选股列表高效轮询)
    """
    if not symbols_or_codes:
        return []

    seen = set()
    clean_items = []
    for s in symbols_or_codes:
        s_str = str(s).strip()
        if not s_str:
            continue
        if s_str.startswith(("sh", "sz", "bj")):
            prefix = s_str[:2].lower()
            code = s_str[2:]
            full_sym = f"{prefix}{code}"
        else:
            code = s_str
            prefix = "sh" if code.startswith(("6", "9", "5", "11")) else "sz" if code.startswith(("0", "3", "12", "15", "18")) else "bj"
            full_sym = f"{prefix}{code}"

        if code and full_sym not in seen:
            seen.add(full_sym)
            clean_items.append((code, full_sym, prefix))

    if not clean_items:
        return []

    results = []
    chunk_size = 40
    for i in range(0, len(clean_items), chunk_size):
        chunk = clean_items[i:i + chunk_size]
        qt_query = ",".join(item[1] for item in chunk)
        url = f"http://qt.gtimg.cn/q={qt_query}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=4) as resp:
                content = resp.read().decode("gbk", errors="ignore")
                lines = content.strip().split(";\n")
                for line in lines:
                    line = line.strip()
                    if not line or "~" not in line or '="' not in line:
                        continue
                    try:
                        raw_data = line.split('="')[1].split('";')[0]
                        fields = raw_data.split("~")
                        if len(fields) < 35:
                            continue
                        name = fields[1]
                        code = fields[2]
                        current_price = float(fields[3]) if fields[3] else 0.0
                        prev_close = float(fields[4]) if fields[4] else 0.0
                        open_price = float(fields[5]) if fields[5] else 0.0
                        volume_shares = float(fields[6]) if fields[6] else 0.0
                        high_price = float(fields[33]) if fields[33] else current_price
                        low_price = float(fields[34]) if fields[34] else current_price
                        change_amount = float(fields[31]) if fields[31] else 0.0
                        change_percent = float(fields[32]) if fields[32] else 0.0
                        time_str = fields[30] if len(fields) > 30 else ""
                        turnover_val = float(fields[37]) if len(fields) > 37 and fields[37] else 0.0

                        # 优先从返回行的前缀判断属于哪个市场
                        line_sym = line.split("=")[0].replace("v_", "").strip()
                        prefix = line_sym[:2] if line_sym.startswith(("sh", "sz", "bj")) else ("sh" if code.startswith(("6", "9", "5", "11")) else "sz" if code.startswith(("0", "3", "12", "15", "18")) else "bj")

                        results.append({
                            "code": code,
                            "symbol": f"{prefix}{code}",
                            "name": name,
                            "price": current_price,
                            "prev_close": prev_close,
                            "open": open_price,
                            "high": high_price,
                            "low": low_price,
                            "volume": volume_shares,
                            "turnover": turnover_val,
                            "change": change_amount,
                            "change_percent": change_percent,
                            "time_str": time_str
                        })
                    except Exception as parse_err:
                        logger.warning(f"解析批量行情单行失败: {parse_err}")
        except Exception as e:
            logger.error(f"批量获取A股实时快照失败: {e}")

    return results

