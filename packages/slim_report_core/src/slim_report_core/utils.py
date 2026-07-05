"""Utility helpers for core report serialization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .exceptions import ReportSerializationError, ReportValidationError


def ensure_mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    """Return value as a mapping or raise a report validation error."""
    if not isinstance(value, Mapping):
        raise ReportValidationError(f"{context} must be a mapping.")
    return value


def ensure_list(value: Any, *, context: str) -> list[Any]:
    """Return value as a list or raise a report validation error."""
    if not isinstance(value, list):
        raise ReportValidationError(f"{context} must be a list.")
    return value


def parse_json_object(payload: str | bytes | bytearray) -> Mapping[str, Any]:
    """Parse a JSON object payload into a mapping."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ReportSerializationError(f"Invalid report JSON: {exc.msg}") from exc

    return ensure_mapping(data, context="Report JSON")


def dump_json_object(data: Mapping[str, Any], *, indent: int | None = 2) -> str:
    """Serialize a mapping to JSON."""
    try:
        return json.dumps(data, indent=indent)
    except TypeError as exc:
        raise ReportSerializationError(f"Report data is not JSON serializable: {exc}") from exc

