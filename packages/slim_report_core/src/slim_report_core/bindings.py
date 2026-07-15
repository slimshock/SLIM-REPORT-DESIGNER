"""Dataset-field binding operations for stored report definitions."""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import ReportObjectNotFoundError, ReportValidationError
from .models import Band, DatasetFieldBinding, Object


@dataclass(frozen=True)
class BindingValidationIssue:
    """One non-destructive dataset-binding validation finding."""

    code: str
    message: str
    object_id: str | None = None
    dataset_id: str | None = None
    field_name: str | None = None


@dataclass(frozen=True)
class BindingValidationResult:
    """Validation result for all structured bindings in a report."""

    issues: tuple[BindingValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.issues


class ReportBindingService:
    """Create, clear, inspect, and validate dataset-field report bindings."""

    supported_object_types = frozenset({"text"})

    def bind_object(
        self,
        report: object,
        object_id: str,
        dataset_id: str,
        field_name: str,
    ) -> Object:
        """Bind one text object after validating the entire requested change."""
        report_object = self._require_object(report, object_id)
        if report_object.type not in self.supported_object_types:
            raise ReportValidationError(
                f"Object {object_id!r} does not support dataset-field bindings."
            )
        dataset = self._require_dataset(report, dataset_id)
        field = next((item for item in dataset.fields if item.name == field_name), None)
        if field is None:
            raise ReportValidationError(
                f"Dataset {dataset_id!r} does not contain field {field_name!r}."
            )
        band = self._object_band(report, report_object)
        if band is not None and band.dataset_id not in (None, dataset.id):
            raise ReportValidationError(
                f"Band {band.id!r} is already bound to dataset {band.dataset_id!r}."
            )

        binding = DatasetFieldBinding(dataset_id=dataset.id, field_name=field.name)
        report_object.dataset_binding = binding
        report_object.text = f"{{{{{dataset.id}.{field.name}}}}}"
        if band is not None:
            band.dataset_id = dataset.id
        return report_object

    def clear_binding(self, report: object, object_id: str) -> Object:
        """Clear one binding while preserving the object's displayed text."""
        report_object = self._require_object(report, object_id)
        report_object.dataset_binding = None
        band = self._object_band(report, report_object)
        if band is not None and not self._band_bindings(report, band.id):
            band.dataset_id = None
        return report_object

    def get_binding(self, report: object, object_id: str) -> DatasetFieldBinding | None:
        """Return one object's binding without changing report state."""
        return self._require_object(report, object_id).dataset_binding

    def find_dataset_bindings(self, report: object, dataset_id: str) -> tuple[Object, ...]:
        """Return all object bindings for a stable dataset ID."""
        return self.dataset_references(report, dataset_id)

    def find_field_bindings(
        self,
        report: object,
        dataset_id: str,
        field_name: str,
    ) -> tuple[Object, ...]:
        """Return bindings for an exact dataset ID and field name."""
        return tuple(
            item
            for item in self.dataset_references(report, dataset_id)
            if item.dataset_binding.field_name == field_name
        )

    def validate(self, report: object) -> BindingValidationResult:
        """Validate stored references without connecting to a data source."""
        issues: list[BindingValidationIssue] = []
        datasets = {dataset.id: dataset for dataset in report.datasets}
        for report_object in report.objects:
            binding = report_object.dataset_binding
            if binding is None:
                continue
            if report_object.type not in self.supported_object_types:
                issues.append(self._issue("unsupported_object_type", report_object, binding))
                continue
            dataset = datasets.get(binding.dataset_id)
            if dataset is None:
                issues.append(self._issue("missing_dataset", report_object, binding))
                continue
            if not any(field.name == binding.field for field in dataset.fields):
                issues.append(self._issue("missing_field", report_object, binding))
            band = self._object_band(report, report_object)
            if band is not None and band.dataset_id not in (None, binding.dataset_id):
                issues.append(self._issue("band_dataset_mismatch", report_object, binding))
        for band in report.bands:
            if band.dataset_id is not None and band.dataset_id not in datasets:
                issues.append(
                    BindingValidationIssue(
                        code="missing_band_dataset",
                        message=f"Band {band.id!r} references missing dataset {band.dataset_id!r}.",
                        dataset_id=band.dataset_id,
                    )
                )
        return BindingValidationResult(tuple(issues))

    def dataset_references(self, report: object, dataset_id: str) -> tuple[Object, ...]:
        """Return objects that explicitly reference a dataset."""
        return tuple(
            item
            for item in report.objects
            if item.dataset_binding is not None and item.dataset_binding.dataset_id == dataset_id
        )

    def dataset_band_references(self, report: object, dataset_id: str) -> tuple[Band, ...]:
        """Return bands whose dataset context references a dataset."""
        return tuple(item for item in report.bands if item.dataset_id == dataset_id)

    @staticmethod
    def _require_object(report: object, object_id: str) -> Object:
        report_object = report.find_object(object_id)
        if report_object is None:
            raise ReportObjectNotFoundError(f"Report object not found: {object_id}.")
        return report_object

    @staticmethod
    def _require_dataset(report: object, dataset_id: str) -> object:
        dataset = report.get_dataset(dataset_id)
        if dataset is None:
            raise ReportValidationError(f"Report dataset not found: {dataset_id}.")
        return dataset

    @staticmethod
    def _object_band(report: object, report_object: Object) -> Band | None:
        if report_object.band_id is None:
            return None
        return next((band for band in report.bands if band.id == report_object.band_id), None)

    @staticmethod
    def _band_bindings(report: object, band_id: str) -> tuple[Object, ...]:
        return tuple(
            item
            for item in report.objects
            if item.band_id == band_id and item.dataset_binding is not None
        )

    @staticmethod
    def _issue(
        code: str,
        report_object: Object,
        binding: DatasetFieldBinding,
    ) -> BindingValidationIssue:
        messages = {
            "unsupported_object_type": "Object type does not support dataset-field bindings.",
            "missing_dataset": "Bound dataset is missing from the report.",
            "missing_field": "Bound field is missing from the dataset definition.",
            "band_dataset_mismatch": "Object binding conflicts with its band dataset context.",
        }
        return BindingValidationIssue(
            code=code,
            message=messages[code],
            object_id=report_object.id,
            dataset_id=binding.dataset_id,
            field_name=binding.field,
        )
