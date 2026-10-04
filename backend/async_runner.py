"""
Runs a backend call on a worker thread and delivers its result back to the
Tkinter main thread via root.after() polling, so long-running operations
(SPICE simulation, Gemini requests, benchmark runs) never block the GUI
event loop. Any exception raised in the worker - including BackendError
subclasses - is captured and handed to on_error instead of crashing the
thread silently.
"""

import queue
import threading


class AsyncRunner:
    def __init__(self, root, poll_interval_ms: int = 100, on_busy_change=None):
        self._root = root
        self._poll_interval_ms = poll_interval_ms
        self._on_busy_change = on_busy_change

    def run(self, work, on_success=None, on_error=None, on_progress=None, label: str = ""):
        """
        Run `work` on a background thread. If `on_progress` is given, `work` is
        called as `work(report)` where `report(value)` may be called from the
        worker thread to deliver `value` to `on_progress(value)` on the main
        thread; otherwise `work` is called with no arguments (unchanged
        behaviour). on_success(result) is called on the main thread if `work`
        returns normally; on_error(exc) is called on the main thread if it
        raises. If this runner was built with `on_busy_change`, it's called
        with (True, label) when the work starts and (False, "") when it ends.
        """
        result_queue: "queue.Queue" = queue.Queue(maxsize=1)
        progress_queue: "queue.Queue | None" = queue.Queue() if on_progress is not None else None

        def report(value):
            progress_queue.put(value)

        def _worker():
            try:
                result = work(report) if on_progress is not None else work()
                result_queue.put(("success", result))
            except Exception as exc:  # noqa: BLE001 - forward any failure to the GUI thread
                result_queue.put(("error", exc))

        if self._on_busy_change is not None:
            self._on_busy_change(True, label)

        threading.Thread(target=_worker, daemon=True).start()

        def _poll():
            if progress_queue is not None:
                while True:
                    try:
                        value = progress_queue.get_nowait()
                    except queue.Empty:
                        break
                    on_progress(value)

            try:
                status, payload = result_queue.get_nowait()
            except queue.Empty:
                self._root.after(self._poll_interval_ms, _poll)
                return

            if self._on_busy_change is not None:
                self._on_busy_change(False, "")

            if status == "success":
                if on_success is not None:
                    on_success(payload)
            elif on_error is not None:
                on_error(payload)
            else:
                raise payload

        self._root.after(self._poll_interval_ms, _poll)
