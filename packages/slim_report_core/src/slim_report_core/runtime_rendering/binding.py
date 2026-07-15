"""Structured binding resolution and safe scalar formatting."""

from __future__ import annotations

import math
from datetime import date, datetime, time
from decimal import Decimal

from ..data_sources import DatasetField, ReportDataset
from ..dataset_execution import DatasetRow
from ..models import DatasetFieldBinding, Object
from .errors import RuntimeBindingResolutionError, RuntimeUnsupportedBindingError


class RuntimeBindingResolver:
    """Resolve authoritative dataset-field bindings against one current row."""

    def resolve(
        self,
        binding: DatasetFieldBinding,
        *,
        dataset: ReportDataset,
        row: DatasetRow | None,
    ) -> object:
        if binding.dataset_id != dataset.id:
            raise RuntimeBindingResolutionError(
                "The object binding references another dataset."
            )
        field = next((item for item in dataset.fields if item.name == binding.field_name), None)
        if field is None:
            raise RuntimeBindingResolutionError(
                f'The field "{binding.field_name}" is not available in the selected dataset.'
            )
        if row is None:
            raise RuntimeBindingResolutionError(
                "Dataset fields cannot be resolved without a current Detail row."
            )
        if binding.field_name in row.values:
            return row.values[binding.field_name]
        raise RuntimeBindingResolutionError(
            f'The field "{binding.field_name}" is not available in the current dataset row.'
        )


class RuntimeValueFormatter:
    """Convert supported database scalar values to stable display text."""

    def format_value(
        self,
        value: object,
        *,
        field: DatasetField,
        report_object: Object,
    ) -> str:
        del field
        if report_object.type != "text":
            raise RuntimeUnsupportedBindingError(
                "Only text objects support dataset-field bindings in live preview."
            )
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            if not math.isfinite(value):
                raise RuntimeUnsupportedBindingError(
                    "A dataset field contains an unsupported numeric value."
                )
            return format(Decimal(str(value)), "f")
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise RuntimeUnsupportedBindingError(
                    "A dataset field contains an unsupported numeric value."
                )
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat(sep=" ")
        if isinstance(value, (date, time)):
            return value.isoformat()
        if isinstance(value, (bytes, bytearray, memoryview)):
            raise RuntimeUnsupportedBindingError(
                "Binary dataset fields cannot be rendered as text."
            )
        raise RuntimeUnsupportedBindingError(
            "A dataset field contains a value that cannot be rendered safely."
        )
