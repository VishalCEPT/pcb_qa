import threading
import time

from backend.async_runner import AsyncRunner

from conftest import pump_until


def test_success_callback_runs_on_ui_thread(tk_root):
    outcome = {}

    def on_success(value):
        outcome["value"] = value
        outcome["thread"] = threading.current_thread()

    AsyncRunner(tk_root, poll_interval_ms=10).run(lambda: 6 * 7, on_success=on_success)
    assert pump_until(tk_root, lambda: "value" in outcome)

    assert outcome["value"] == 42
    assert outcome["thread"] is threading.main_thread()


def test_error_callback_receives_exception(tk_root):
    outcome = {}

    def boom():
        raise ValueError("bad board")

    AsyncRunner(tk_root, poll_interval_ms=10).run(boom, on_error=lambda exc: outcome.setdefault("exc", exc))
    assert pump_until(tk_root, lambda: "exc" in outcome)

    assert isinstance(outcome["exc"], ValueError)


def test_on_progress_receives_values_reported_from_worker_thread(tk_root):
    outcome = {}
    progress_values = []

    def work(report):
        for i in range(3):
            report(i)
        return "done"

    AsyncRunner(tk_root, poll_interval_ms=10).run(
        work,
        on_success=lambda v: outcome.setdefault("value", v),
        on_progress=progress_values.append,
    )
    assert pump_until(tk_root, lambda: "value" in outcome)

    assert outcome["value"] == "done"
    assert progress_values == [0, 1, 2]


def test_on_busy_change_fires_at_start_and_end_with_label(tk_root):
    outcome = {}
    busy_events = []

    AsyncRunner(
        tk_root, poll_interval_ms=10,
        on_busy_change=lambda is_busy, label: busy_events.append((is_busy, label)),
    ).run(lambda: 1, on_success=lambda v: outcome.setdefault("value", v), label="doing work")
    assert pump_until(tk_root, lambda: "value" in outcome)

    assert busy_events == [(True, "doing work"), (False, "")]


def test_ui_stays_responsive_during_slow_work(tk_root):
    done = {}
    ticks = []

    def tick():
        ticks.append(time.monotonic())
        if "v" not in done:
            tk_root.after(20, tick)

    tk_root.after(0, tick)
    AsyncRunner(tk_root, poll_interval_ms=10).run(
        lambda: time.sleep(0.5) or 1, on_success=lambda v: done.setdefault("v", v)
    )
    assert pump_until(tk_root, lambda: "v" in done)

    assert done["v"] == 1
    assert len(ticks) >= 10
