"""Validation helpers for selecting one runtime Detail dataset."""

from __future__ import annotations

from ..bindings import ReportBindingService
from ..data_sources import ReportDataset
from ..report import Report
from .errors import (
    RuntimeBandConfigurationError,
    RuntimeBindingResolutionError,
    RuntimeDatasetSelectionError,
    RuntimeUnsupportedBindingError,
)


def resolve_runtime_dataset(
    report: Report,
    execution_service: object,
    dataset_id: str | None,
) -> ReportDataset:
    try:
        dataset = execution_service.resolve_primary_dataset(report, dataset_id)
    except Exception as exc:
        raise RuntimeDatasetSelectionError(
            "Select the dataset to use for report preview."
        ) from exc
    detail_bands = [
        band
        for band in report.bands
        if band.id.casefold() == "detail" or band.type.casefold() == "detail"
    ]
    bound_details = [band for band in detail_bands if band.dataset_id is not None]
    ids = {band.dataset_id for band in bound_details}
    if len(ids) > 1:
        raise RuntimeBandConfigurationError(
            "The report contains multiple Detail datasets and cannot be previewed."
        )
    if not detail_bands:
        raise RuntimeBandConfigurationError(
            "This report does not contain a dataset-bound Detail band."
        )
    if not bound_details and dataset_id is None:
        raise RuntimeBandConfigurationError(
            "This report does not contain a dataset-bound Detail band."
        )
    if ids and ids != {dataset.id}:
        raise RuntimeBandConfigurationError(
            "The Detail band is not configured for the selected dataset."
        )
    return dataset


def validate_runtime_bindings(report: Report, dataset: ReportDataset) -> None:
    result = ReportBindingService().validate(report)
    if result.issues:
        issue = result.issues[0]
        if issue.code == "unsupported_object_type":
            raise RuntimeUnsupportedBindingError(issue.message)
        field = f' Field "{issue.field_name}".' if issue.field_name else ""
        raise RuntimeBindingResolutionError(
            f"Report preview cannot continue because a field binding is invalid.{field}"
        )
    detail_ids = {
        band.id
        for band in report.bands
        if band.id.casefold() == "detail" or band.type.casefold() == "detail"
    }
    for item in report.objects:
        binding = item.dataset_binding
        if binding is None:
            continue
        if item.band_id not in detail_ids:
            raise RuntimeBandConfigurationError(
                "Dataset-field bindings must be placed in the runtime Detail band."
            )
        if binding.dataset_id != dataset.id:
            raise RuntimeBandConfigurationError(
                "The Detail band contains bindings from more than one dataset."
            )
