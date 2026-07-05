"""Serializer interfaces for report persistence formats."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from os import PathLike
from typing import Any

from ..report import Report

PathValue = str | PathLike[str]


class BaseSerializer(ABC):
    """Base class for report serializers."""

    @abstractmethod
    def load_mapping(self, data: Mapping[str, Any]) -> Report:
        """Deserialize structured data into a report."""

    @abstractmethod
    def dump_mapping(self, report: Report) -> dict[str, Any]:
        """Serialize a report into structured data."""

    @abstractmethod
    def loads(self, payload: str | bytes | bytearray) -> Report:
        """Deserialize a payload into a report."""

    @abstractmethod
    def dumps(self, report: Report, *, indent: int | None = 2) -> str:
        """Serialize a report into a payload string."""

    @abstractmethod
    def load(self, path: PathValue) -> Report:
        """Deserialize a report from a path."""

    @abstractmethod
    def save(self, report: Report, path: PathValue, *, indent: int | None = 2) -> None:
        """Serialize a report to a path."""

