from datetime import datetime, timedelta
import socket

import pandas as pd
import pytest

from backend.intraday.random_selector import IntradayRandomSelector


TIMES = ("10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00")


def make_frame(trading_days, *, first_time="10:00", history_start=None):
    rows = []
    times = (first_time,) + tuple(time_text for time_text in TIMES if time_text > first_time)
    if history_start is not None:
        rows.append({"datetime": pd.Timestamp(history_start)})
    for trading_day in trading_days:
        for time_text in times:
            rows.append({"datetime": pd.Timestamp(f"{pd.Timestamp(trading_day).date()} {time_text}")})
    return pd.DataFrame(rows)


class SequenceProvider:
    def __init__(self, codes):
        self.codes = list(codes)
        self.calls = 0

    def __call__(self, sector, date_start, date_end):
        value = self.codes[min(self.calls, len(self.codes) - 1)]
        self.calls += 1
        if isinstance(value, Exception):
            raise value
        return value


class FrameService:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_30m(self, stock_code, start, end):
        self.calls.append((stock_code, start, end))
        response = self.responses[stock_code]
        if isinstance(response, Exception):
            raise response
        return response.copy() if response is not None else None


class IndexedRng:
    def __init__(self, index):
        self.index = index
        self.choices = []

    def choice(self, values):
        self.choices.append(tuple(values))
        return values[self.index]


def viable_frame(*, first_time="10:00"):
    days = pd.bdate_range("2024-01-02", periods=12)
    return make_frame(days, first_time=first_time, history_start="2022-01-01 10:00")


def select(selector, *, start="2024-01-01", end="2024-01-31", max_training_days=3):
    return selector.select(
        sector="all",
        date_start=datetime.fromisoformat(start),
        date_end=datetime.fromisoformat(end),
        max_training_days=max_training_days,
    )


def test_selects_random_real_trading_date_inside_requested_range():
    rng = IndexedRng(2)
    selector = IntradayRandomSelector(
        candidate_provider=SequenceProvider(["600000"]),
        data_service=FrameService({"600000": viable_frame()}),
        rng=rng,
        max_attempts=2,
    )

    result = select(selector)

    assert result.stock_code == "600000"
    assert result.start_time.date().isoformat() == "2024-01-04"
    assert result.start_time in rng.choices[0]


def test_uses_selected_dates_first_real_30m_timestamp():
    selector = IntradayRandomSelector(
        candidate_provider=SequenceProvider(["600000"]),
        data_service=FrameService({"600000": viable_frame(first_time="10:30")}),
        rng=IndexedRng(0),
    )

    result = select(selector)

    assert result.start_time == datetime(2024, 1, 2, 10, 30)


@pytest.mark.parametrize("prefix", ["43", "83", "87", "92"])
def test_retries_all_bse_prefixes(prefix):
    provider = SequenceProvider([f"{prefix}0001", "600000"])
    service = FrameService({f"{prefix}0001": viable_frame(), "600000": viable_frame()})
    selector = IntradayRandomSelector(provider, service, rng=IndexedRng(0), max_attempts=2)

    result = select(selector)

    assert result.stock_code == "600000"
    assert provider.calls == 2
    assert [call[0] for call in service.calls] == ["600000"]


def test_retries_candidate_with_less_than_730_natural_days_of_history():
    selected_day = pd.Timestamp("2024-01-02")
    short = make_frame(
        [selected_day],
        history_start=selected_day - timedelta(days=729),
    )
    provider = SequenceProvider(["600001", "600000"])
    selector = IntradayRandomSelector(
        provider,
        FrameService({"600001": short, "600000": viable_frame()}),
        rng=IndexedRng(0),
        max_attempts=2,
    )

    result = select(selector, max_training_days=0)

    assert result.stock_code == "600000"
    assert (result.start_time - result.context_start).days >= 730


def test_requires_enough_remaining_distinct_trading_dates():
    insufficient = make_frame(
        ["2024-01-02", "2024-01-03", "2024-01-08"],
        history_start="2022-01-01 10:00",
    )
    selector = IntradayRandomSelector(
        SequenceProvider(["600001", "600000"]),
        FrameService({"600001": insufficient, "600000": viable_frame()}),
        rng=IndexedRng(0),
        max_attempts=2,
    )

    result = select(selector, max_training_days=4)

    assert result.stock_code == "600000"
    assert result.available_training_days >= 4


def test_zero_training_days_allows_last_available_trading_date():
    selector = IntradayRandomSelector(
        SequenceProvider(["600000"]),
        FrameService({"600000": viable_frame()}),
        rng=IndexedRng(-1),
    )

    result = select(selector, max_training_days=0)

    assert result.start_time.date().isoformat() == "2024-01-17"
    assert result.available_training_days == 1


def test_retries_empty_and_invalid_datetime_candidates():
    invalid = pd.DataFrame({"datetime": ["not-a-date"]})
    selector = IntradayRandomSelector(
        SequenceProvider(["600001", "600002", "600000"]),
        FrameService({"600001": pd.DataFrame(), "600002": invalid, "600000": viable_frame()}),
        rng=IndexedRng(0),
        max_attempts=3,
    )

    result = select(selector)

    assert result.stock_code == "600000"


def test_retries_candidate_provider_and_data_source_exceptions():
    provider = SequenceProvider([RuntimeError("provider unavailable"), "600001", "600000"])
    selector = IntradayRandomSelector(
        provider,
        FrameService({"600001": RuntimeError("source unavailable"), "600000": viable_frame()}),
        rng=IndexedRng(0),
        max_attempts=3,
    )

    result = select(selector)

    assert result.stock_code == "600000"
    assert provider.calls == 3


def test_attempt_count_is_bounded():
    provider = SequenceProvider(["600001"])
    selector = IntradayRandomSelector(
        provider,
        FrameService({"600001": pd.DataFrame()}),
        rng=IndexedRng(0),
        max_attempts=3,
    )

    with pytest.raises(ValueError, match="after 3 attempts"):
        select(selector)

    assert provider.calls == 3


def test_final_error_is_actionable():
    selector = IntradayRandomSelector(
        SequenceProvider(["600001"]),
        FrameService({"600001": pd.DataFrame()}),
        rng=IndexedRng(0),
        max_attempts=2,
    )

    with pytest.raises(ValueError) as exc_info:
        select(selector, max_training_days=150)

    message = str(exc_info.value)
    assert "no valid intraday blind-box candidate" in message
    assert "widen the date range" in message
    assert "reduce max_training_days" in message
    assert "change sector or data source" in message


def test_injected_rng_makes_selection_fully_deterministic():
    frame = viable_frame()
    first = IntradayRandomSelector(
        SequenceProvider(["600000"]), FrameService({"600000": frame}), rng=IndexedRng(4)
    )
    second = IntradayRandomSelector(
        SequenceProvider(["600000"]), FrameService({"600000": frame}), rng=IndexedRng(4)
    )

    first_result = select(first)
    second_result = select(second)

    assert first_result.stock_code == second_result.stock_code
    assert first_result.start_time == second_result.start_time
    assert first_result.context_start == second_result.context_start
    assert first_result.available_training_days == second_result.available_training_days
    pd.testing.assert_frame_equal(first_result.base_bars, second_result.base_bars)


def test_focused_tests_do_not_require_network(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    selector = IntradayRandomSelector(
        SequenceProvider(["600000"]),
        FrameService({"600000": viable_frame()}),
        rng=IndexedRng(0),
    )

    assert select(selector).stock_code == "600000"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"date_start": datetime(2024, 2, 1), "date_end": datetime(2024, 1, 1)}, "date_end"),
        ({"max_training_days": -1}, "max_training_days"),
    ],
)
def test_rejects_invalid_request_arguments(kwargs, message):
    selector = IntradayRandomSelector(
        SequenceProvider(["600000"]), FrameService({"600000": viable_frame()}), rng=IndexedRng(0)
    )
    arguments = {
        "sector": "all",
        "date_start": datetime(2024, 1, 1),
        "date_end": datetime(2024, 1, 31),
        "max_training_days": 3,
    }
    arguments.update(kwargs)

    with pytest.raises(ValueError, match=message):
        selector.select(**arguments)
