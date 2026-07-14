"""Parameter value conversion for safe driver binding."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from ..data_sources import QueryParameter
from .errors import InvalidQueryParameterValueError, MissingQueryParameterValueError

_MISSING = object()
_TRUE_VALUES = {"true", "yes", "1"}
_FALSE_VALUES = {"false", "no", "0"}


class QueryParameterValueConverter:
    """Convert declared query parameter values into DB-API native values."""

    def convert(self, *, parameter: QueryParameter, value: object = _MISSING) -> object:
        """Return a safe value for driver binding without interpolating SQL."""
        if value is _MISSING:
            if parameter.default is not None:
                value = parameter.default
            elif parameter.required:
                raise MissingQueryParameterValueError(
                    f"The required query parameter ':{parameter.name}' has no discovery value."
                )
            else:
                return None

        if value is None:
            if parameter.required:
                raise MissingQueryParameterValueError(
                    f"The required query parameter ':{parameter.name}' has no discovery value."
                )
            return None

        try:
            if parameter.data_type == "string":
                return str(value)
            if parameter.data_type == "integer":
                return self._integer(value)
            if parameter.data_type == "float":
                return self._float(value)
            if parameter.data_type == "decimal":
                return self._decimal(value)
            if parameter.data_type == "boolean":
                return self._boolean(value)
            if parameter.data_type == "date":
                return self._date(value)
            if parameter.data_type == "time":
                return self._time(value)
            if parameter.data_type == "datetime":
                return self._datetime(value)
        except (TypeError, ValueError, InvalidOperation) as exc:
            raise InvalidQueryParameterValueError(
                f"The query parameter ':{parameter.name}' has an invalid discovery value."
            ) from exc

        raise InvalidQueryParameterValueError(
            f"The query parameter ':{parameter.name}' has an unsupported type."
        )

    @staticmethod
    def _integer(value: object) -> int:
        if isinstance(value, bool):
            raise ValueError
        if isinstance(value, int):
            return value
        text = str(value).strip()
        if text == "":
            raise ValueError
        return int(text, 10)

    @staticmethod
    def _float(value: object) -> float:
        if isinstance(value, bool):
            raise ValueError
        return float(value)

    @staticmethod
    def _decimal(value: object) -> Decimal:
        if isinstance(value, bool):
            raise ValueError
        text = str(value).strip()
        if text == "":
            raise ValueError
        return Decimal(text)

    @staticmethod
    def _boolean(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in {0, 1}:
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in _TRUE_VALUES:
                return True
            if normalized in _FALSE_VALUES:
                return False
        raise ValueError

    @staticmethod
    def _date(value: object) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value.strip())
        raise ValueError

    @staticmethod
    def _time(value: object) -> time:
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            return time.fromisoformat(value.strip())
        raise ValueError

    @staticmethod
    def _datetime(value: object) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.strip())
        raise ValueError


def missing_parameter_value() -> Any:
    """Return the private sentinel used by callers that need explicit missing state."""
    return _MISSING
