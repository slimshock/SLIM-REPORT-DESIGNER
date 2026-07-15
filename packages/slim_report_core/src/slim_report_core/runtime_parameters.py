"""Runtime query parameter schemas and safe dataset-scoped resolution."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from .data_sources import (
    DatasetSourceType,
    QueryParameter,
    ReportDataset,
    query_parameter_default_to_json,
)
from .exceptions import DatasetValidationError, ReportValidationError
from .query_discovery import (
    InvalidQueryParameterValueError,
    MissingQueryParameterValueError,
    QueryParameterValueConverter,
)
from .report import Report

_MISSING = object()
_SCALAR_VALUES = (str, int, float, Decimal, bool, date, time, datetime)


class RuntimeParameterError(ReportValidationError):
    """Base error for safe runtime parameter resolution."""

    code = "runtime_parameter_error"

    def __init__(self, message: str, *, parameter_name: str | None = None) -> None:
        super().__init__(message)
        self.parameter_name = parameter_name


class RuntimeParameterDatasetError(RuntimeParameterError):
    """Raised when a requested runtime parameter dataset is invalid."""

    code = "dataset_not_found"


class RuntimeParameterMissingError(RuntimeParameterError):
    """Raised when a required parameter has no usable value."""

    code = "missing_required"


class RuntimeParameterConversionError(RuntimeParameterError):
    """Raised when a runtime value cannot be safely converted."""

    code = "invalid_value"


class RuntimeParameterUnknownError(RuntimeParameterError):
    """Raised when an undeclared parameter value is supplied."""

    code = "unknown_parameter"


class RuntimeParameterDefinitionError(RuntimeParameterError):
    """Raised when a stored parameter definition or default is invalid."""

    code = "invalid_default"


@dataclass(frozen=True)
class RuntimeParameterResolutionPolicy:
    """Fail-closed limits and normalization rules for runtime resolution."""

    reject_unknown_values: bool = True
    use_template_defaults: bool = True
    allow_optional_null: bool = True
    trim_non_string_input: bool = True
    trim_string_input: bool = False
    reject_non_finite_numbers: bool = True
    max_string_length: int = 100_000
    max_parameters: int = 100

    def __post_init__(self) -> None:
        boolean_fields = (
            "reject_unknown_values",
            "use_template_defaults",
            "allow_optional_null",
            "trim_non_string_input",
            "trim_string_input",
            "reject_non_finite_numbers",
        )
        if any(not isinstance(getattr(self, name), bool) for name in boolean_fields):
            raise ValueError("Runtime parameter policy flags must be boolean.")
        if (
            isinstance(self.max_string_length, bool)
            or not isinstance(self.max_string_length, int)
            or self.max_string_length <= 0
        ):
            raise ValueError("max_string_length must be positive.")
        if (
            isinstance(self.max_parameters, bool)
            or not isinstance(self.max_parameters, int)
            or self.max_parameters <= 0
        ):
            raise ValueError("max_parameters must be positive.")


@dataclass(frozen=True)
class RuntimeParameterRequirement:
    """Serializable runtime input metadata for one query parameter."""

    name: str
    data_type: str
    required: bool
    label: str
    has_default: bool
    default: Any = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "dataType": self.data_type,
            "required": self.required,
            "label": self.label,
            "hasDefault": self.has_default,
        }
        if self.has_default:
            data["default"] = query_parameter_default_to_json(self.default)
        return data


@dataclass(frozen=True)
class DatasetRuntimeParameterSchema:
    """Ordered runtime input requirements for one report dataset."""

    dataset_id: str
    dataset_name: str
    parameters: tuple[RuntimeParameterRequirement, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "datasetId": self.dataset_id,
            "datasetName": self.dataset_name,
            "parameters": [parameter.to_dict() for parameter in self.parameters],
        }


@dataclass(frozen=True)
class ResolvedParameterSet:
    """Immutable Python values suitable for future database-driver binding."""

    dataset_id: str
    values: Mapping[str, object]
    used_defaults: tuple[str, ...] = ()
    provided_parameters: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "used_defaults", tuple(self.used_defaults))
        object.__setattr__(self, "provided_parameters", tuple(self.provided_parameters))


@dataclass(frozen=True)
class RuntimeParameterIssue:
    """Safe field-addressable validation issue."""

    parameter_name: str | None
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameter": self.parameter_name,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class RuntimeParameterValidationResult:
    """Aggregate validation result that never exposes submitted values."""

    valid: bool
    issues: tuple[RuntimeParameterIssue, ...] = ()
    resolved: ResolvedParameterSet | None = field(default=None, repr=False, compare=False)


class RuntimeParameterResolver:
    """Build schemas and resolve runtime values without database access."""

    def __init__(
        self,
        *,
        converter: QueryParameterValueConverter | None = None,
        policy: RuntimeParameterResolutionPolicy | None = None,
    ) -> None:
        self.converter = converter or QueryParameterValueConverter()
        self.policy = policy or RuntimeParameterResolutionPolicy()

    def schema_for_dataset(self, dataset: ReportDataset) -> DatasetRuntimeParameterSchema:
        """Return ordered, JSON-safe input metadata; views have an empty schema."""
        if dataset.source_type is DatasetSourceType.VIEW:
            return DatasetRuntimeParameterSchema(dataset.id, dataset.name)
        self._validate_parameter_count(dataset)
        requirements = tuple(self._requirement(parameter) for parameter in dataset.parameters)
        return DatasetRuntimeParameterSchema(dataset.id, dataset.name, requirements)

    def resolve_dataset(
        self,
        dataset: ReportDataset,
        supplied_values: Mapping[str, object] | None = None,
        *,
        application_values: Mapping[str, object] | None = None,
    ) -> ResolvedParameterSet:
        """Resolve explicit values, host values, defaults, then optional nulls."""
        if dataset.source_type is not DatasetSourceType.QUERY:
            error = RuntimeParameterDatasetError(
                "Runtime parameters require a query-based dataset."
            )
            error.code = "dataset_not_query"
            raise error
        self._validate_parameter_count(dataset)
        supplied = self._mapping(supplied_values)
        application = self._mapping(application_values)
        declared = {parameter.name for parameter in dataset.parameters}
        self._reject_unknown(supplied, declared)
        self._reject_unknown(application, declared)

        values: dict[str, object] = {}
        used_defaults: list[str] = []
        provided: list[str] = []
        for parameter in dataset.parameters:
            raw, source = self._select_value(parameter, supplied, application)
            if source in {"supplied", "application"}:
                provided.append(parameter.name)
            if source == "default":
                used_defaults.append(parameter.name)
            values[parameter.name] = self._resolve_value(parameter, raw, source)
        return ResolvedParameterSet(
            dataset.id,
            values,
            tuple(used_defaults),
            tuple(provided),
        )

    def validate_dataset(
        self,
        dataset: ReportDataset,
        supplied_values: Mapping[str, object] | None = None,
        *,
        application_values: Mapping[str, object] | None = None,
    ) -> RuntimeParameterValidationResult:
        """Return a safe issue result around exception-based resolution."""
        try:
            resolved = self.resolve_dataset(
                dataset,
                supplied_values,
                application_values=application_values,
            )
        except RuntimeParameterError as exc:
            issue = RuntimeParameterIssue(exc.parameter_name, exc.code, str(exc))
            return RuntimeParameterValidationResult(False, (issue,))
        return RuntimeParameterValidationResult(True, resolved=resolved)

    def _requirement(self, parameter: QueryParameter) -> RuntimeParameterRequirement:
        default = None
        if parameter.default is not None:
            try:
                default = query_parameter_default_to_json(parameter.default)
                self._convert(parameter, default, is_default=True)
            except (DatasetValidationError, RuntimeParameterError) as exc:
                raise RuntimeParameterDefinitionError(
                    f'The configured default for parameter "{self._label(parameter)}" is invalid.',
                    parameter_name=parameter.name,
                ) from exc
        return RuntimeParameterRequirement(
            parameter.name,
            parameter.data_type,
            parameter.required,
            self._label(parameter),
            parameter.default is not None,
            default,
        )

    def _select_value(
        self,
        parameter: QueryParameter,
        supplied: Mapping[str, object],
        application: Mapping[str, object],
    ) -> tuple[object, str]:
        if parameter.name in supplied:
            raw = supplied[parameter.name]
            if not self._blank_non_string(parameter, raw):
                return raw, "supplied"
        if parameter.name in application:
            raw = application[parameter.name]
            if not self._blank_non_string(parameter, raw):
                return raw, "application"
        if self.policy.use_template_defaults and parameter.default is not None:
            return parameter.default, "default"
        return _MISSING, "missing"

    def _resolve_value(self, parameter: QueryParameter, raw: object, source: str) -> object:
        label = self._label(parameter)
        if raw is _MISSING:
            if parameter.required:
                raise RuntimeParameterMissingError(
                    f'The required parameter "{label}" has no value.',
                    parameter_name=parameter.name,
                )
            if not self.policy.allow_optional_null:
                raise RuntimeParameterMissingError(
                    f'The optional parameter "{label}" does not allow a null value.',
                    parameter_name=parameter.name,
                )
            return None
        if raw is None:
            if parameter.required:
                raise RuntimeParameterMissingError(
                    f'The required parameter "{label}" has no value.',
                    parameter_name=parameter.name,
                )
            return None
        if parameter.data_type == "string":
            value = self._string(parameter, raw)
            if value == "":
                if parameter.required:
                    raise RuntimeParameterMissingError(
                        f'The required parameter "{label}" has no value.',
                        parameter_name=parameter.name,
                    )
                return None
            return value
        return self._convert(parameter, raw, is_default=source == "default")

    def _string(self, parameter: QueryParameter, raw: object) -> str:
        if not isinstance(raw, _SCALAR_VALUES):
            raise self._conversion_error(parameter)
        value = str(raw)
        if self.policy.trim_string_input:
            value = value.strip()
        if len(value) > self.policy.max_string_length:
            error = RuntimeParameterConversionError(
                f'The parameter "{self._label(parameter)}" exceeds the maximum length.',
                parameter_name=parameter.name,
            )
            error.code = "string_too_long"
            raise error
        return value

    def _convert(self, parameter: QueryParameter, raw: object, *, is_default: bool) -> object:
        candidate = (
            raw.strip() if self.policy.trim_non_string_input and isinstance(raw, str) else raw
        )
        try:
            converted = self.converter.convert(parameter=parameter, value=candidate)
        except (InvalidQueryParameterValueError, MissingQueryParameterValueError) as exc:
            if is_default:
                raise RuntimeParameterDefinitionError(
                    f'The configured default for parameter "{self._label(parameter)}" is invalid.',
                    parameter_name=parameter.name,
                ) from exc
            raise self._conversion_error(parameter) from exc
        if self.policy.reject_non_finite_numbers:
            if isinstance(converted, float) and not math.isfinite(converted):
                raise self._non_finite_error(parameter)
            if isinstance(converted, Decimal) and not converted.is_finite():
                raise self._non_finite_error(parameter)
        return converted

    def _conversion_error(self, parameter: QueryParameter) -> RuntimeParameterConversionError:
        type_label = {"boolean": "true or false", "datetime": "an ISO datetime"}.get(
            parameter.data_type,
            f"a valid {parameter.data_type}",
        )
        error = RuntimeParameterConversionError(
            f'The parameter "{self._label(parameter)}" must be {type_label}.',
            parameter_name=parameter.name,
        )
        error.code = f"invalid_{parameter.data_type}"
        return error

    def _non_finite_error(self, parameter: QueryParameter) -> RuntimeParameterConversionError:
        error = RuntimeParameterConversionError(
            f'The parameter "{self._label(parameter)}" must be finite.',
            parameter_name=parameter.name,
        )
        error.code = f"non_finite_{parameter.data_type}"
        return error

    def _validate_parameter_count(self, dataset: ReportDataset) -> None:
        if len(dataset.parameters) > self.policy.max_parameters:
            raise RuntimeParameterDefinitionError(
                f"Dataset runtime parameters exceed the limit of {self.policy.max_parameters}."
            )

    def _reject_unknown(self, values: Mapping[str, object], declared: set[str]) -> None:
        if not self.policy.reject_unknown_values:
            return
        unknown = next((name for name in values if name not in declared), None)
        if unknown is not None:
            raise RuntimeParameterUnknownError(
                f"A value was supplied for unknown parameter ':{unknown}'.",
                parameter_name=unknown,
            )

    @staticmethod
    def _mapping(values: Mapping[str, object] | None) -> Mapping[str, object]:
        if values is None:
            return {}
        if not isinstance(values, Mapping):
            raise RuntimeParameterConversionError("Runtime parameter values must be a mapping.")
        return dict(values)

    @staticmethod
    def _blank_non_string(parameter: QueryParameter, raw: object) -> bool:
        return parameter.data_type != "string" and isinstance(raw, str) and raw.strip() == ""

    @staticmethod
    def _label(parameter: QueryParameter) -> str:
        if parameter.label:
            return parameter.label
        return " ".join(
            part.upper() if part.lower() == "id" else part.capitalize()
            for part in parameter.name.split("_")
        )


class ReportRuntimeParameterService:
    """Resolve one or more report datasets while preserving dataset scope."""

    def __init__(self, resolver: RuntimeParameterResolver | None = None) -> None:
        self.resolver = resolver or RuntimeParameterResolver()

    def schema_for_report(
        self,
        report: Report,
        dataset_ids: tuple[str, ...] | None = None,
    ) -> tuple[DatasetRuntimeParameterSchema, ...]:
        datasets = self._datasets(report, dataset_ids)
        return tuple(self.resolver.schema_for_dataset(dataset) for dataset in datasets)

    def schema_for_primary_dataset(
        self,
        report: Report,
        dataset_id: str | None = None,
    ) -> DatasetRuntimeParameterSchema:
        datasets = self._datasets(report, (dataset_id,) if dataset_id else None)
        if len(datasets) != 1:
            raise RuntimeParameterDatasetError("Select the dataset to use for report execution.")
        return self.resolver.schema_for_dataset(datasets[0])

    def resolve_report(
        self,
        report: Report,
        values_by_dataset: Mapping[str, Mapping[str, object]],
        dataset_ids: tuple[str, ...] | None = None,
        *,
        application_values_by_dataset: Mapping[str, Mapping[str, object]] | None = None,
    ) -> tuple[ResolvedParameterSet, ...]:
        datasets = self._datasets(report, dataset_ids)
        requested_ids = {dataset.id for dataset in datasets}
        unknown = next((key for key in values_by_dataset if key not in requested_ids), None)
        if unknown is not None:
            raise RuntimeParameterDatasetError(f"Report dataset '{unknown}' was not found.")
        application = application_values_by_dataset or {}
        return tuple(
            self.resolver.resolve_dataset(
                dataset,
                values_by_dataset.get(dataset.id, {}),
                application_values=application.get(dataset.id, {}),
            )
            for dataset in datasets
        )

    @staticmethod
    def _datasets(report: Report, dataset_ids: tuple[str, ...] | None) -> tuple[ReportDataset, ...]:
        if dataset_ids is None:
            return tuple(report.datasets)
        by_id = {dataset.id: dataset for dataset in report.datasets}
        selected: list[ReportDataset] = []
        for dataset_id in dataset_ids:
            dataset = by_id.get(dataset_id)
            if dataset is None:
                raise RuntimeParameterDatasetError(f"Report dataset '{dataset_id}' was not found.")
            selected.append(dataset)
        return tuple(selected)
