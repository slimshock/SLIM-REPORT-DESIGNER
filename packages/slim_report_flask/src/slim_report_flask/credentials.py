"""Process-local runtime credential storage for interactive designer sessions."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Protocol


class RuntimeCredentialStore(Protocol):
    def set_password(self, report_key: str, data_source_id: str, password: str) -> None: ...

    def get_password(self, report_key: str, data_source_id: str) -> str | None: ...

    def clear_password(self, report_key: str, data_source_id: str) -> None: ...

    def clear_report(self, report_key: str) -> None: ...


@dataclass(repr=False)
class InMemoryRuntimeCredentialStore:
    """Thread-safe, expiring session store; this is not a credential vault."""

    ttl_seconds: float = 1800.0
    _entries: dict[tuple[str, str], tuple[str, float]] = field(
        default_factory=dict, init=False, repr=False
    )
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.ttl_seconds, bool) or self.ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive.")

    def __repr__(self) -> str:
        return f"{type(self).__name__}(ttl_seconds={self.ttl_seconds!r})"

    def set_password(self, report_key: str, data_source_id: str, password: str) -> None:
        key = self._key(report_key, data_source_id)
        if not isinstance(password, str):
            raise TypeError("Runtime password must be text.")
        with self._lock:
            self._entries[key] = (password, time.monotonic() + self.ttl_seconds)

    def get_password(self, report_key: str, data_source_id: str) -> str | None:
        key = self._key(report_key, data_source_id)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            password, expires_at = entry
            if expires_at <= time.monotonic():
                self._entries.pop(key, None)
                return None
            return password

    def clear_password(self, report_key: str, data_source_id: str) -> None:
        key = self._key(report_key, data_source_id)
        with self._lock:
            self._entries.pop(key, None)

    def clear_report(self, report_key: str) -> None:
        normalized = self._text(report_key, "report_key")
        with self._lock:
            for key in tuple(self._entries):
                if key[0] == normalized:
                    self._entries.pop(key, None)

    @classmethod
    def _key(cls, report_key: str, data_source_id: str) -> tuple[str, str]:
        return cls._text(report_key, "report_key"), cls._text(data_source_id, "data_source_id")

    @staticmethod
    def _text(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise ValueError(f"{field_name} must be non-empty text.")
        return value.strip()
