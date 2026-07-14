from __future__ import annotations

from pathlib import Path

from flask import Flask

import slim_report_core
import slim_report_designer_ui
import slim_report_flask
from slim_report_core import (
    ConnectionTestResult,
    CreateMySQLDataSourceCommand,
    CreateQueryDatasetCommand,
    CreateViewDatasetCommand,
    DatabaseColumnInfo,
    DatabaseViewInfo,
    DatabaseViewSchema,
    DataManagementError,
    DataManagementResult,
    DataManagementValidationError,
    DatasetConfigurationResult,
    DatasetFieldChangeSummary,
    DatasetNotFoundError,
    DatasetSummary,
    DatasetTypeMismatchError,
    DataSourceConnectionError,
    DataSourceInUseError,
    DataSourceManagementService,
    DataSourceMetadataError,
    DataSourceNotFoundError,
    DataSourceProvider,
    DataSourceProviderRegistry,
    DataSourceSummary,
    DesignerDataService,
    DuplicateOutputColumnError,
    InvalidDatasetOperationError,
    JSONSerializer,
    MetadataAccessPolicy,
    MissingQueryParameterValueError,
    MySQLConnectionPolicy,
    MySQLDataSourceProvider,
    MySQLMetadataService,
    MySQLTypeMapper,
    QueryExecutionError,
    QueryExecutionTimeoutError,
    QueryFieldDiscoveryError,
    QueryFieldDiscoveryPolicy,
    QueryFieldDiscoveryResult,
    QueryFieldDiscoveryService,
    QueryParameterValueConverter,
    QueryReturnedNoColumnsError,
    StaleDiscoveryResultError,
    TooManyOutputColumnsError,
    UpdateMySQLDataSourceCommand,
    ViewNotFoundError,
    normalize_template,
    render_html,
    render_pdf,
)
from slim_report_core.storage import (
    DBAPITemplateProvider,
    PyMySQLTemplateProvider,
    SQLAlchemyTemplateProvider,
    TemplateNotFoundError,
)
from slim_report_core.storage import (
    FileSystemTemplateProvider as CoreFileSystemTemplateProvider,
)
from slim_report_core.storage import (
    TemplateProvider as CoreTemplateProvider,
)
from slim_report_designer_ui import get_designer_static_path, static_file
from slim_report_flask import (
    FileSystemTemplateProvider,
    SlimReportDesigner,
    TemplateProvider,
    create_blueprint,
)
from slim_report_flask import (
    PyMySQLTemplateProvider as FlaskPyMySQLTemplateProvider,
)
from slim_report_flask import TemplateNotFoundError as FlaskTemplateNotFoundError


def test_public_package_imports_are_stable() -> None:
    assert slim_report_core.__version__ == "0.6.0a0"
    assert slim_report_flask.__version__ == "0.6.0a0"
    assert slim_report_designer_ui.__version__ == "0.6.0a0"
    assert callable(render_html)
    assert callable(render_pdf)
    assert callable(normalize_template)
    assert ConnectionTestResult is not None
    assert CreateMySQLDataSourceCommand is not None
    assert CreateQueryDatasetCommand is not None
    assert CreateViewDatasetCommand is not None
    assert DatabaseColumnInfo is not None
    assert DatabaseViewInfo is not None
    assert DatabaseViewSchema is not None
    assert DataManagementError is not None
    assert DataManagementResult is not None
    assert DataManagementValidationError is not None
    assert DataSourceConnectionError is not None
    assert DataSourceInUseError is not None
    assert DataSourceManagementService is not None
    assert DataSourceMetadataError is not None
    assert DataSourceNotFoundError is not None
    assert DataSourceProvider is not None
    assert DataSourceProviderRegistry is not None
    assert DataSourceSummary is not None
    assert DatasetConfigurationResult is not None
    assert DatasetFieldChangeSummary is not None
    assert DatasetNotFoundError is not None
    assert DatasetSummary is not None
    assert DatasetTypeMismatchError is not None
    assert DesignerDataService is DataSourceManagementService
    assert DuplicateOutputColumnError is not None
    assert InvalidDatasetOperationError is not None
    assert MySQLConnectionPolicy is not None
    assert MySQLDataSourceProvider is not None
    assert MetadataAccessPolicy is not None
    assert MissingQueryParameterValueError is not None
    assert MySQLMetadataService is not None
    assert MySQLTypeMapper is not None
    assert QueryExecutionError is not None
    assert QueryExecutionTimeoutError is not None
    assert QueryFieldDiscoveryError is not None
    assert QueryFieldDiscoveryPolicy is not None
    assert QueryFieldDiscoveryResult is not None
    assert QueryFieldDiscoveryService is not None
    assert QueryParameterValueConverter is not None
    assert QueryReturnedNoColumnsError is not None
    assert StaleDiscoveryResultError is not None
    assert TooManyOutputColumnsError is not None
    assert UpdateMySQLDataSourceCommand is not None
    assert ViewNotFoundError is not None
    assert SlimReportDesigner is not None
    assert TemplateProvider is CoreTemplateProvider
    assert FileSystemTemplateProvider is CoreFileSystemTemplateProvider
    assert DBAPITemplateProvider is not None
    assert PyMySQLTemplateProvider is not None
    assert FlaskPyMySQLTemplateProvider is PyMySQLTemplateProvider
    assert FlaskTemplateNotFoundError is TemplateNotFoundError
    assert SQLAlchemyTemplateProvider is not None
    assert TemplateNotFoundError is not None
    assert callable(create_blueprint)


def test_normalize_template_supports_minimal_public_template() -> None:
    template = {
        "metadata": {"name": "Smoke Template"},
        "page": {"width": 300, "height": 200},
        "objects": [
            {
                "id": "title",
                "type": "text",
                "x": 10,
                "y": 10,
                "width": 180,
                "height": 24,
                "text": "Hello {{ patient.name }}",
            }
        ],
        "bands": [],
    }

    normalized = normalize_template(template)
    report = JSONSerializer().load_mapping(template)
    html = render_html(report, {"patient": {"name": "Iris"}})
    pdf = render_pdf(report, {"patient": {"name": "Iris"}})

    assert normalized["version"] == "0.1"
    assert normalized["metadata"]["title"] == "Smoke Template"
    assert normalized["metadata"]["name"] == "Smoke Template"
    assert normalized["page"]["unit"] == "px"
    assert normalized["assets"] == []
    assert "Hello Iris" in html
    assert pdf.startswith(b"%PDF")
    assert "assets" not in template


def test_designer_ui_package_data_is_available_through_resources() -> None:
    static_root = get_designer_static_path()

    assert static_root.is_dir()
    assert static_file("index.html").is_file()
    assert static_file("css/designer.css").is_file()
    assert static_file("js/designer.js").is_file()
    assert "SLIM_REPORT_API_BASE" in static_file("js/api.js").read_text(encoding="utf-8")


def test_flask_designer_serves_packaged_static_assets(tmp_path: Path) -> None:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(tmp_path / "templates")
    designer = SlimReportDesigner(app)

    client = app.test_client()
    designer_response = client.get("/report-designer/designer")
    js_response = client.get("/report-designer/designer-ui/js/designer.js")
    css_response = client.get("/report-designer/designer-ui/css/designer.css")

    assert designer_response.status_code == 200
    assert "SLIM_REPORT_API_BASE" in designer_response.get_data(as_text=True)
    assert js_response.status_code == 200
    assert js_response.mimetype == "application/javascript"
    assert css_response.status_code == 200
    assert css_response.mimetype == "text/css"
    assert designer.app is app
