"""Immutable, driver-neutral metadata models and access policy."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SAFE_PREFIX_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class DatabaseViewInfo:
    """Safe metadata describing one database view."""

    schema_name: str
    view_name: str
    display_name: str | None = None
    is_updatable: bool | None = None
    definer: str | None = None
    security_type: str | None = None


@dataclass(frozen=True)
class DatabaseColumnInfo:
    """Safe metadata describing one view column."""

    name: str
    ordinal_position: int
    database_type: str
    normalized_type: str
    nullable: bool
    default: object | None = None
    character_maximum_length: int | None = None
    numeric_precision: int | None = None
    numeric_scale: int | None = None
    datetime_precision: int | None = None
    column_comment: str | None = None
    source_name: str | None = None


@dataclass(frozen=True)
class DatabaseViewSchema:
    """A reporting view and its complete ordered column metadata."""

    view: DatabaseViewInfo
    columns: tuple[DatabaseColumnInfo, ...]


@dataclass(frozen=True)
class MetadataAccessPolicy:
    """Fail-closed limits and allowlists for metadata discovery."""

    views_only: bool = True
    allow_cross_schema: bool = False
    allowed_schemas: tuple[str, ...] = ()
    allowed_view_prefixes: tuple[str, ...] = ()
    allowed_view_names: tuple[str, ...] = ()
    include_system_schemas: bool = False
    include_updatable_metadata: bool = False
    max_views: int = 1000
    max_columns_per_view: int = 1000

    def __post_init__(self) -> None:
        for field_name in (
            "views_only",
            "allow_cross_schema",
            "include_system_schemas",
            "include_updatable_metadata",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean.")
        if isinstance(self.max_views, bool) or not isinstance(self.max_views, int):
            raise ValueError("max_views must be a positive integer.")
        if self.max_views < 1:
            raise ValueError("max_views must be a positive integer.")
        if isinstance(self.max_columns_per_view, bool) or not isinstance(
            self.max_columns_per_view, int
        ):
            raise ValueError("max_columns_per_view must be a positive integer.")
        if self.max_columns_per_view < 1:
            raise ValueError("max_columns_per_view must be a positive integer.")

        schemas = _validated_values(self.allowed_schemas, "allowed_schemas", _SAFE_IDENTIFIER_RE)
        view_names = _validated_values(
            self.allowed_view_names,
            "allowed_view_names",
            _SAFE_IDENTIFIER_RE,
        )
        prefixes = _validated_values(
            self.allowed_view_prefixes,
            "allowed_view_prefixes",
            _SAFE_PREFIX_RE,
        )
        object.__setattr__(self, "allowed_schemas", schemas)
        object.__setattr__(self, "allowed_view_names", view_names)
        object.__setattr__(self, "allowed_view_prefixes", prefixes)

        if self.allow_cross_schema and not schemas:
            raise ValueError(
                "allowed_schemas must not be empty when cross-schema metadata access is enabled."
            )


def _validated_values(
    values: tuple[str, ...],
    field_name: str,
    pattern: re.Pattern[str],
) -> tuple[str, ...]:
    if isinstance(values, str):
        raise ValueError(f"{field_name} must be a tuple of identifiers.")
    normalized: list[str] = []
    seen: set[str] = set()
    try:
        candidates = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{field_name} must be a tuple of identifiers.") from exc
    for value in candidates:
        if not isinstance(value, str) or pattern.fullmatch(value) is None:
            raise ValueError(f"{field_name} contains an invalid identifier.")
        key = value.casefold()
        if key not in seen:
            normalized.append(value)
            seen.add(key)
    return tuple(normalized)
