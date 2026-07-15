"""Closeable bounded public dataset row stream."""

from __future__ import annotations

import logging
import math
from collections.abc import Iterator, Mapping, Sequence
from datetime import date, datetime, time
from decimal import Decimal
from time import monotonic

from .cancellation import DatasetExecutionCancellationToken
from .errors import (
    DatasetExecutionCancelledError,
    DatasetResultLimitError,
    DatasetRowShapeError,
    DatasetValueTypeError,
)
from .models import (
    DatasetExecutionSchema,
    DatasetExecutionSummary,
    DatasetRow,
    DatasetRowBatch,
)
from .policy import EffectiveDatasetExecutionConfiguration
from .provider import ProviderDatasetRowStream

logger = logging.getLogger(__name__)


class DatasetRowStream(Iterator[DatasetRow]):
    """Incrementally normalize and yield rows from one provider-owned stream."""

    def __init__(
        self,
        *,
        raw_stream: ProviderDatasetRowStream,
        schema: DatasetExecutionSchema,
        returned_column_names: tuple[str, ...],
        provider: str,
        configuration: EffectiveDatasetExecutionConfiguration,
        cancellation_token: DatasetExecutionCancellationToken | None = None,
        started: float | None = None,
    ) -> None:
        self.schema = schema
        self._raw_stream = raw_stream
        self._returned_column_names = tuple(returned_column_names)
        self._provider = provider
        self._configuration = configuration
        self._cancellation_token = cancellation_token
        self._started = monotonic() if started is None else started
        self._buffer: list[object] = []
        self._buffer_index = 0
        self._row_count = 0
        self._total_bytes = 0
        self._truncated = False
        self._cancelled = False
        self._complete = False
        self._closed = False
        self._warnings: list[str] = []

    def __enter__(self) -> DatasetRowStream:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.close()

    def __iter__(self) -> DatasetRowStream:
        return self

    def __next__(self) -> DatasetRow:
        if self._closed or self._complete:
            raise StopIteration
        self._check_cancelled()
        if self._row_count >= self._configuration.max_rows:
            self._detect_truncation()
            raise StopIteration
        if self._buffer_index >= len(self._buffer):
            remaining = self._configuration.max_rows - self._row_count
            self._buffer = self._fetchmany(min(self._configuration.batch_size, remaining))
            self._buffer_index = 0
            if not self._buffer:
                self._finish()
                raise StopIteration
        raw_row = self._buffer[self._buffer_index]
        self._buffer_index += 1
        try:
            values, row_bytes = self._normalize_row(raw_row)
            if self._total_bytes + row_bytes > self._configuration.max_total_bytes:
                raise DatasetResultLimitError(
                    "Dataset execution exceeded the configured result-size limit."
                )
        except Exception:
            self.close()
            raise
        self._total_bytes += row_bytes
        self._row_count += 1
        return DatasetRow(self._row_count, values)

    def iter_batches(self) -> Iterator[DatasetRowBatch]:
        """Yield non-empty immutable batches without retaining previous batches."""
        while True:
            rows: list[DatasetRow] = []
            for _ in range(self._configuration.batch_size):
                try:
                    rows.append(next(self))
                except StopIteration:
                    break
            if not rows:
                return
            yield DatasetRowBatch(rows[0].index, tuple(rows))

    def close(self) -> None:
        """Close provider resources idempotently."""
        if self._closed:
            return
        self._closed = True
        self._buffer.clear()
        self._buffer_index = 0
        try:
            self._raw_stream.close()
        except Exception:
            logger.warning("Dataset execution resources could not be closed cleanly.")

    def summary(self) -> DatasetExecutionSummary:
        """Return the current safe state before, during, or after iteration."""
        return DatasetExecutionSummary(
            dataset_id=self.schema.dataset_id,
            dataset_name=self.schema.dataset_name,
            provider=self._provider,
            row_count=self._row_count,
            field_count=len(self.schema.fields),
            truncated=self._truncated,
            cancelled=self._cancelled,
            elapsed_ms=max(0.0, (monotonic() - self._started) * 1000.0),
            warnings=tuple(self._warnings),
        )

    def _fetchmany(self, size: int) -> list[object]:
        self._check_cancelled()
        try:
            rows = self._raw_stream.fetchmany(size)
        except Exception:
            if self._cancellation_token is not None and self._cancellation_token.is_cancelled:
                self._cancelled = True
                self.close()
                raise DatasetExecutionCancelledError("Dataset execution was cancelled.") from None
            self.close()
            raise
        self._check_cancelled()
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            self.close()
            raise DatasetRowShapeError(
                "The MySQL driver returned an invalid dataset row collection."
            )
        return list(rows)

    def _detect_truncation(self) -> None:
        lookahead = self._fetchmany(1)
        if lookahead:
            self._truncated = True
            self._warnings.append(
                "Dataset execution stopped after the configured limit of "
                f"{self._configuration.max_rows} rows."
            )
        self._finish()

    def _finish(self) -> None:
        if self._complete:
            return
        self._complete = True
        self.close()
        logger.info(
            "Dataset execution completed for dataset %s: rows=%d, truncated=%s, "
            "cancelled=%s, elapsed_ms=%.3f.",
            self.schema.dataset_id,
            self._row_count,
            self._truncated,
            self._cancelled,
            max(0.0, (monotonic() - self._started) * 1000.0),
        )

    def _check_cancelled(self) -> None:
        if self._cancellation_token is None or not self._cancellation_token.is_cancelled:
            return
        self._cancelled = True
        self.close()
        raise DatasetExecutionCancelledError("Dataset execution was cancelled.")

    def _normalize_row(self, row: object) -> tuple[dict[str, object], int]:
        raw_values = self._row_values(row)
        if len(raw_values) != len(self.schema.fields):
            raise DatasetRowShapeError(
                "The MySQL driver returned a row that does not match the dataset schema."
            )
        values: dict[str, object] = {}
        total = 0
        for field, raw_value in zip(self.schema.fields, raw_values, strict=True):
            value = self._normalize_value(raw_value)
            size = self._value_size(value)
            if size > self._configuration.max_cell_bytes:
                raise DatasetResultLimitError(
                    f"The value returned for field '{field.name}' exceeds the configured "
                    "cell-size limit."
                )
            values[field.name] = value
            total += size
        return values, total

    def _row_values(self, row: object) -> tuple[object, ...]:
        if isinstance(row, Mapping):
            if len(row) != len(self._returned_column_names):
                raise DatasetRowShapeError(
                    "The MySQL driver returned a row that does not match the dataset schema."
                )
            by_name: dict[str, object] = {}
            for key, value in row.items():
                if not isinstance(key, str) or not key:
                    raise DatasetRowShapeError(
                        "The MySQL driver returned a row that does not match the dataset schema."
                    )
                normalized = key.casefold()
                if normalized in by_name:
                    raise DatasetRowShapeError(
                        "The MySQL driver returned a row that does not match the dataset schema."
                    )
                by_name[normalized] = value
            try:
                return tuple(by_name[name.casefold()] for name in self._returned_column_names)
            except KeyError as exc:
                raise DatasetRowShapeError(
                    "The MySQL driver returned a row that does not match the dataset schema."
                ) from exc
        if isinstance(row, Sequence) and not isinstance(row, (str, bytes, bytearray)):
            return tuple(row)
        raise DatasetRowShapeError(
            "The MySQL driver returned a row that does not match the dataset schema."
        )

    def _normalize_value(self, value: object) -> object:
        if value is None or isinstance(value, (str, bool, int, date, time, datetime)):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise DatasetValueTypeError("The MySQL driver returned a non-finite numeric value.")
            return value
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise DatasetValueTypeError("The MySQL driver returned a non-finite numeric value.")
            return value
        if isinstance(value, (bytes, bytearray, memoryview)):
            if not self._configuration.allow_binary_values:
                raise DatasetValueTypeError(
                    "The dataset returned a binary value disabled by execution policy."
                )
            return bytes(value)
        if self._configuration.allow_unknown_value_types:
            return str(value)
        raise DatasetValueTypeError("The MySQL driver returned an unsupported value type.")

    @staticmethod
    def _value_size(value: object) -> int:
        if value is None:
            return 0
        if isinstance(value, str):
            try:
                return len(value.encode("utf-8"))
            except UnicodeEncodeError as exc:
                raise DatasetValueTypeError(
                    "The MySQL driver returned an invalid text value."
                ) from exc
        if isinstance(value, bytes):
            return len(value)
        if isinstance(value, Decimal):
            return len(str(value).encode("ascii"))
        if isinstance(value, (date, time, datetime)):
            return len(value.isoformat().encode("ascii"))
        return 8
