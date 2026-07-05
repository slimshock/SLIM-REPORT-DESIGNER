"""Framework-independent event system for report domain events."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReportEvent:
    """Event emitted by report domain objects."""

    name: str
    source: Any
    payload: dict[str, Any] = field(default_factory=dict)


EventListener = Callable[[ReportEvent], None]


class EventDispatcher:
    """Synchronous observer-pattern event dispatcher."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[EventListener]] = defaultdict(list)

    def on(self, event_name: str, listener: EventListener) -> EventListener:
        """Register a listener for an event name."""
        normalized_name = _normalize_event_name(event_name)
        self._listeners[normalized_name].append(listener)
        return listener

    def off(self, event_name: str, listener: EventListener) -> None:
        """Remove a listener from an event name."""
        normalized_name = _normalize_event_name(event_name)
        listeners = self._listeners.get(normalized_name, [])
        if listener in listeners:
            listeners.remove(listener)
        if not listeners and normalized_name in self._listeners:
            del self._listeners[normalized_name]

    def emit(self, event_name: str, source: Any, **payload: Any) -> ReportEvent:
        """Emit an event to registered listeners."""
        normalized_name = _normalize_event_name(event_name)
        event = ReportEvent(name=normalized_name, source=source, payload=dict(payload))
        for listener in list(self._listeners.get(normalized_name, [])):
            listener(event)
        return event

    def clear(self, event_name: str | None = None) -> None:
        """Clear listeners for one event or all events."""
        if event_name is None:
            self._listeners.clear()
            return
        self._listeners.pop(_normalize_event_name(event_name), None)

    def listeners(self, event_name: str) -> list[EventListener]:
        """Return listeners registered for an event name."""
        return list(self._listeners.get(_normalize_event_name(event_name), []))


def _normalize_event_name(event_name: str) -> str:
    normalized_name = event_name.strip()
    if not normalized_name:
        raise ValueError("Event name must be a non-empty string.")
    return normalized_name
