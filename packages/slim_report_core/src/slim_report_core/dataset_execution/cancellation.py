"""Thread-safe best-effort dataset execution cancellation."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event, Lock


class DatasetExecutionCancellationToken:
    """Signal cancellation and notify active execution resources."""

    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._next_callback_id = 1

    def cancel(self) -> None:
        """Cancel once and invoke registered cleanup callbacks best-effort."""
        self._event.set()
        with self._lock:
            callbacks = tuple(self._callbacks.values())
        for callback in callbacks:
            try:
                callback()
            except Exception:
                continue

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._event.is_set()

    def _register(self, callback: Callable[[], None]) -> Callable[[], None]:
        callback_id: int | None = None
        with self._lock:
            if not self._event.is_set():
                callback_id = self._next_callback_id
                self._next_callback_id += 1
                self._callbacks[callback_id] = callback
        if callback_id is None:
            callback()

        def unregister() -> None:
            if callback_id is None:
                return
            with self._lock:
                self._callbacks.pop(callback_id, None)

        return unregister
