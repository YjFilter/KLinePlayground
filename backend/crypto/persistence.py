from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Iterator

from .futures_models import ZERO, decimal_value
from .models import CryptoPeriod


SESSION_METADATA_COLUMNS = {
    "market_type": "TEXT",
    "symbol": "TEXT",
    "quote_currency": "TEXT",
    "base_interval": "TEXT",
    "timezone": "TEXT",
    "source": "TEXT",
    "simulator_type": "TEXT",
}


EVENT_TABLES = {
    "crypto_futures_orders": ("order_id", "submitted_at"),
    "crypto_futures_fills": ("fill_id", "timestamp"),
    "crypto_funding_events": ("event_key", "timestamp"),
    "crypto_liquidation_events": ("liquidation_id", "timestamp"),
    "crypto_equity_snapshots": ("snapshot_id", "timestamp"),
}

EVENT_DECIMAL_FIELDS = {
    "crypto_futures_orders": {"quantity", "margin", "limit_price", "reserved_margin"},
    "crypto_futures_fills": {"quantity", "price", "fee", "realized_pnl", "notional"},
    "crypto_funding_events": {"rate", "mark_price", "notional", "transfer"},
    "crypto_liquidation_events": {"quantity", "entry_price", "price", "fee", "equity_before", "maintenance_margin"},
    "crypto_equity_snapshots": {"equity", "balance", "unrealized_pnl", "mark_price"},
}


@contextmanager
def _connection(target: str | Path | sqlite3.Connection) -> Iterator[tuple[sqlite3.Connection, bool]]:
    if isinstance(target, sqlite3.Connection):
        yield target, False
        return
    connection = sqlite3.connect(str(target))
    try:
        yield connection, True
    finally:
        connection.close()


def migrate_crypto_futures_schema(target: str | Path | sqlite3.Connection) -> None:
    with _connection(target) as (connection, owned):
        savepoint = "crypto_futures_migration"
        try:
            connection.execute(f"SAVEPOINT {savepoint}")
            connection.execute("CREATE TABLE IF NOT EXISTS training_sessions (session_id TEXT PRIMARY KEY)")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(training_sessions)")}
            for name, column_type in SESSION_METADATA_COLUMNS.items():
                if name not in columns:
                    connection.execute(f"ALTER TABLE training_sessions ADD COLUMN {name} {column_type}")
            for table, (identifier, timestamp_column) in EVENT_TABLES.items():
                connection.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        {identifier} TEXT NOT NULL,
                        {timestamp_column} TEXT,
                        payload TEXT NOT NULL,
                        UNIQUE(session_id, {identifier})
                    )
                    """
                )
                connection.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_session_time ON {table}(session_id, {timestamp_column}, id)"
                )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS crypto_futures_runtime (
                    session_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            if owned:
                connection.commit()
        except Exception:
            connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            if owned:
                connection.rollback()
            raise


class CryptoFuturesRepository:
    def __init__(self, target: str | Path | sqlite3.Connection, *, migrate: bool = True) -> None:
        self.target = target
        if migrate:
            migrate_crypto_futures_schema(target)

    def save_session_metadata(self, session_id: str, **metadata: Any) -> None:
        unknown = sorted(set(metadata) - set(SESSION_METADATA_COLUMNS))
        if unknown:
            raise ValueError(f"unsupported session metadata: {', '.join(unknown)}")
        if not metadata:
            return
        assignments = ", ".join(f"{name} = ?" for name in metadata)
        values = list(metadata.values()) + [session_id]
        with _connection(self.target) as (connection, _owned):
            exists = connection.execute(
                "SELECT 1 FROM training_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if not exists:
                connection.execute("INSERT INTO training_sessions(session_id) VALUES (?)", (session_id,))
            connection.execute(f"UPDATE training_sessions SET {assignments} WHERE session_id = ?", values)
            connection.commit()

    def get_session_metadata(self, session_id: str) -> dict[str, Any] | None:
        columns = list(SESSION_METADATA_COLUMNS)
        with _connection(self.target) as (connection, _owned):
            row = connection.execute(
                f"SELECT {', '.join(columns)} FROM training_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        metadata = dict(zip(columns, row))
        metadata["market_type"] = metadata["market_type"] or "a_share"
        if metadata["market_type"] == "a_share":
            metadata.setdefault("quote_currency", None)
            metadata.setdefault("base_interval", None)
            metadata.setdefault("timezone", None)
            metadata.setdefault("simulator_type", None)
        return metadata

    def record_order(self, session_id: str, payload: dict[str, Any]) -> None:
        self._record("crypto_futures_orders", session_id, payload)

    def record_fill(self, session_id: str, payload: dict[str, Any]) -> None:
        self._record("crypto_futures_fills", session_id, payload)

    def record_funding(self, session_id: str, payload: dict[str, Any]) -> None:
        self._record("crypto_funding_events", session_id, payload)

    def record_liquidation(self, session_id: str, payload: dict[str, Any]) -> None:
        self._record("crypto_liquidation_events", session_id, payload)

    def record_equity(self, session_id: str, payload: dict[str, Any]) -> None:
        selected = dict(payload)
        selected.setdefault("snapshot_id", selected.get("timestamp"))
        self._record("crypto_equity_snapshots", session_id, selected)

    def record_orders(self, session_id: str, payloads: Iterable[dict[str, Any]]) -> None:
        self._record_many("crypto_futures_orders", session_id, payloads)

    def record_fills(self, session_id: str, payloads: Iterable[dict[str, Any]]) -> None:
        self._record_many("crypto_futures_fills", session_id, payloads)

    def record_funding_events(self, session_id: str, payloads: Iterable[dict[str, Any]]) -> None:
        self._record_many("crypto_funding_events", session_id, payloads)

    def record_liquidations(self, session_id: str, payloads: Iterable[dict[str, Any]]) -> None:
        self._record_many("crypto_liquidation_events", session_id, payloads)

    def record_equities(self, session_id: str, payloads: Iterable[dict[str, Any]]) -> None:
        normalized = []
        for payload in payloads:
            item = dict(payload)
            item.setdefault("snapshot_id", item.get("timestamp"))
            normalized.append(item)
        self._record_many("crypto_equity_snapshots", session_id, normalized)

    def _record(self, table: str, session_id: str, payload: dict[str, Any]) -> None:
        identifier, timestamp_column = EVENT_TABLES[table]
        if identifier not in payload:
            raise ValueError(f"{identifier} is required")
        encoded_payload = _encode_event_payload(table, payload)
        encoded = json.dumps(encoded_payload, ensure_ascii=False, sort_keys=True, default=_json_default)
        with _connection(self.target) as (connection, _owned):
            connection.execute(
                f"""
                INSERT INTO {table}(session_id, {identifier}, {timestamp_column}, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, {identifier}) DO UPDATE SET
                    {timestamp_column}=excluded.{timestamp_column}, payload=excluded.payload
                """,
                (session_id, str(payload[identifier]), payload.get(timestamp_column), encoded),
            )
            connection.commit()

    def _record_many(self, table: str, session_id: str, payloads: Iterable[dict[str, Any]]) -> None:
        rows = []
        identifier, timestamp_column = EVENT_TABLES[table]
        for payload in payloads:
            if identifier not in payload:
                raise ValueError(f"{identifier} is required")
            encoded_payload = _encode_event_payload(table, payload)
            encoded = json.dumps(encoded_payload, ensure_ascii=False, sort_keys=True, default=_json_default)
            rows.append((session_id, str(payload[identifier]), payload.get(timestamp_column), encoded))
        if not rows:
            return
        with _connection(self.target) as (connection, _owned):
            connection.executemany(
                f"""
                INSERT INTO {table}(session_id, {identifier}, {timestamp_column}, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, {identifier}) DO UPDATE SET
                    {timestamp_column}=excluded.{timestamp_column}, payload=excluded.payload
                """,
                rows,
            )
            connection.commit()

    def load_session_state(self, session_id: str) -> dict[str, Any]:
        return {
            "metadata": self.get_session_metadata(session_id),
            "orders": self._load("crypto_futures_orders", session_id),
            "fills": self._load("crypto_futures_fills", session_id),
            "funding_events": self._load("crypto_funding_events", session_id),
            "liquidation_events": self._load("crypto_liquidation_events", session_id),
            "equity_snapshots": self._load("crypto_equity_snapshots", session_id),
            "runtime": self.load_runtime_state(session_id),
        }

    def _load(self, table: str, session_id: str) -> list[dict[str, Any]]:
        _identifier, timestamp_column = EVENT_TABLES[table]
        with _connection(self.target) as (connection, _owned):
            rows = connection.execute(
                f"SELECT payload FROM {table} WHERE session_id = ? ORDER BY {timestamp_column}, id",
                (session_id,),
            ).fetchall()
        return [_decode_event_payload(table, json.loads(row[0])) for row in rows]

    def save_runtime_state(self, session_id: str, executor_or_state: Any) -> None:
        state = executor_or_state.export_state() if hasattr(executor_or_state, "export_state") else executor_or_state
        if not isinstance(state, dict) or state.get("version") != 1:
            raise ValueError("unsupported futures runtime state")
        encoded = json.dumps(state, ensure_ascii=False, sort_keys=True, default=_json_default)
        with _connection(self.target) as (connection, _owned):
            connection.execute(
                """
                INSERT INTO crypto_futures_runtime(session_id, payload, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET payload=excluded.payload, updated_at=CURRENT_TIMESTAMP
                """,
                (session_id, encoded),
            )
            connection.commit()

    def update_runtime_period(self, session_id: str, period: str) -> None:
        normalized = CryptoPeriod.parse(period).value
        with _connection(self.target) as (connection, _owned):
            cursor = connection.execute(
                """
                UPDATE crypto_futures_runtime
                SET payload = json_set(
                    payload,
                    '$.training.period', ?,
                    '$.clock.active_period', ?
                ), updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (normalized, normalized, session_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("no persisted futures runtime state")
            connection.commit()

    def load_runtime_state(self, session_id: str) -> dict[str, Any] | None:
        with _connection(self.target) as (connection, _owned):
            row = connection.execute(
                "SELECT payload FROM crypto_futures_runtime WHERE session_id = ?", (session_id,)
            ).fetchone()
        return None if row is None else json.loads(row[0])

    def rehydrate_executor(self, session_id: str, *, trade_bars, mark_bars, funding_events=()):
        from .trading import FuturesReplayExecutor

        state = self.load_runtime_state(session_id)
        if state is None:
            raise ValueError("no persisted futures runtime state")
        return FuturesReplayExecutor.from_state(
            state, trade_bars=trade_bars, mark_bars=mark_bars, funding_events=funding_events,
        )


def build_crypto_futures_report(
    *,
    initial_equity,
    final_equity,
    unrealized_pnl=ZERO,
    fills: Iterable[dict[str, Any]] = (),
    orders: Iterable[dict[str, Any]] = (),
    funding_events: Iterable[dict[str, Any]] = (),
    liquidation_events: Iterable[dict[str, Any]] = (),
    equity_snapshots: Iterable[dict[str, Any]] = (),
    max_drawdown_percent=None,
    leverage: int = 5,
    source: str = "",
    symbol: str = "",
    display_period: str = "5m",
) -> dict[str, Any]:
    fills = list(fills)
    orders = list(orders)
    funding_events = list(funding_events)
    liquidation_events = list(liquidation_events)
    snapshots = list(equity_snapshots)
    initial = decimal_value(initial_equity)
    final = decimal_value(final_equity)
    realized = sum((decimal_value(fill.get("realized_pnl", ZERO)) for fill in fills), ZERO)
    unrealized = decimal_value(unrealized_pnl)
    maker_fees = sum((decimal_value(fill.get("fee", ZERO)) for fill in fills if fill.get("fee_type") == "maker"), ZERO)
    taker_fees = sum((decimal_value(fill.get("fee", ZERO)) for fill in fills if fill.get("fee_type") == "taker"), ZERO)
    liquidation_fees = sum((decimal_value(fill.get("fee", ZERO)) for fill in fills if fill.get("fee_type") == "liquidation"), ZERO)
    if liquidation_fees == ZERO:
        liquidation_fees = sum((decimal_value(event.get("fee", ZERO)) for event in liquidation_events), ZERO)
    transfers = [decimal_value(event.get("transfer", ZERO)) for event in funding_events]
    funding_paid = sum((-value for value in transfers if value < ZERO), ZERO)
    funding_received = sum((value for value in transfers if value > ZERO), ZERO)
    closed_fills = [fill for fill in fills if fill.get("action") in {"close", "liquidation"}]
    wins = sum(1 for fill in closed_fills if decimal_value(fill.get("realized_pnl", ZERO)) > ZERO)
    win_rate = Decimal(wins) / Decimal(len(closed_fills)) * Decimal("100") if closed_fills else ZERO
    total_return = (final - initial) / initial * Decimal("100") if initial else ZERO
    if max_drawdown_percent is not None:
        drawdown = decimal_value(max_drawdown_percent)
    else:
        drawdown = _maximum_drawdown([decimal_value(item["equity"]) for item in snapshots])
    return {
        "initial_equity": float(initial),
        "final_equity": float(final),
        "realized_pnl": float(realized),
        "unrealized_pnl": float(unrealized),
        "total_return": float(total_return),
        "max_drawdown": float(drawdown),
        "maker_fees": float(maker_fees),
        "taker_fees": float(taker_fees),
        "liquidation_fees": float(liquidation_fees),
        "total_fees": float(maker_fees + taker_fees + liquidation_fees),
        "funding_paid": float(funding_paid),
        "funding_received": float(funding_received),
        "liquidation_count": len(liquidation_events),
        "order_count": len(orders),
        "fill_count": len(fills),
        "win_rate": float(win_rate),
        "leverage": leverage,
        "source": source,
        "symbol": symbol,
        "display_period": display_period,
    }


def _maximum_drawdown(equities: list[Decimal]) -> Decimal:
    peak = ZERO
    maximum = ZERO
    for equity in equities:
        peak = max(peak, equity)
        if peak > ZERO:
            maximum = max(maximum, (peak - equity) / peak * Decimal("100"))
    return maximum


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _encode_event_payload(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    encoded = dict(payload)
    for field in EVENT_DECIMAL_FIELDS[table]:
        if field in encoded and encoded[field] is not None:
            encoded[field] = format(decimal_value(encoded[field]), "f")
    return encoded


def _decode_event_payload(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(payload)
    for field in EVENT_DECIMAL_FIELDS[table]:
        if field in decoded and decoded[field] is not None:
            decoded[field] = decimal_value(decoded[field])
    return decoded


generate_crypto_report = build_crypto_futures_report
migrate_schema = migrate_crypto_futures_schema


__all__ = [
    "CryptoFuturesRepository", "build_crypto_futures_report", "generate_crypto_report",
    "migrate_crypto_futures_schema", "migrate_schema",
]
