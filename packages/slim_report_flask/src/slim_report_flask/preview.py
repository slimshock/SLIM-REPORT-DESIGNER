"""Ephemeral cancellation state for synchronous live-preview requests."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from threading import Lock
from time import monotonic

from slim_report_core import DatasetExecutionCancellationToken


@dataclass(frozen=True)
class _PreviewCancellationEntry:
    user_key: str
    report_key: str
    token: DatasetExecutionCancellationToken
    started: float


class PreviewCancellationRegistry:
    """Thread-safe, process-local registry containing cancellation tokens only."""

    def __init__(self, *, expiry_seconds: int = 120) -> None:
        if isinstance(expiry_seconds, bool) or not isinstance(expiry_seconds, int):
            raise ValueError("expiry_seconds must be a positive integer.")
        if expiry_seconds <= 0:
            raise ValueError("expiry_seconds must be a positive integer.")
        self.expiry_seconds = expiry_seconds
        self._entries: dict[str, _PreviewCancellationEntry] = {}
        self._lock = Lock()

    def register(
        self,
        *,
        user_key: str,
        report_key: str,
        token: DatasetExecutionCancellationToken,
        request_id: str | None = None,
    ) -> str:
        """Register one token under a random or client-generated cryptographic ID."""
        resolved_id = str(request_id or secrets.token_urlsafe(32)).strip()
        if len(resolved_id) < 20 or len(resolved_id) > 128:
            raise ValueError("Preview request ID is invalid.")
        now = monotonic()
        with self._lock:
            self._cleanup_locked(now)
            if resolved_id in self._entries:
                raise ValueError("Preview request ID is already active.")
            self._entries[resolved_id] = _PreviewCancellationEntry(
                user_key=str(user_key),
                report_key=str(report_key),
                token=token,
                started=now,
            )
        return resolved_id

    def cancel(self, request_id: str, *, user_key: str) -> bool:
        """Signal an owned active preview without revealing whether another user owns it."""
        with self._lock:
            self._cleanup_locked(monotonic())
            entry = self._entries.get(str(request_id))
            if entry is None or entry.user_key != str(user_key):
                return False
            token = entry.token
        token.cancel()
        return True

    def remove(self, request_id: str) -> None:
        """Remove one record idempotently."""
        with self._lock:
            self._entries.pop(str(request_id), None)

    def _cleanup_locked(self, now: float) -> None:
        expired = [
            request_id
            for request_id, entry in self._entries.items()
            if now - entry.started >= self.expiry_seconds
        ]
        for request_id in expired:
            entry = self._entries.pop(request_id)
            entry.token.cancel()
