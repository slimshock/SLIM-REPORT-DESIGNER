# Data-Source and Dataset Management

`DataSourceManagementService` is the framework-agnostic application service for Designer and
backend integrations that need to configure report data sources and datasets. It coordinates the
report model, provider registry, SQL validator, MySQL metadata service, and query field discovery
service without importing Flask, Django, FastAPI, SQLAlchemy, or UI code.

Use this service when an application needs safe commands for:

- creating, listing, updating, testing, and removing MySQL data sources
- listing and inspecting approved MySQL reporting views
- creating and refreshing view-backed datasets
- creating, validating, updating, discovering, and applying fields for query-backed datasets
- replacing, adding, updating, and removing query parameters
- removing datasets or data sources with explicit dependency checks

## Setup

```python
from slim_report_core import (
    DataSourceManagementService,
    DataSourceProviderRegistry,
    MySQLDataSourceProvider,
    MySQLDialect,
    QueryFieldDiscoveryService,
    SQLValidator,
)

registry = DataSourceProviderRegistry()
registry.register(MySQLDataSourceProvider())
validator = SQLValidator(MySQLDialect())
discovery = QueryFieldDiscoveryService(registry, validator)

service = DataSourceManagementService(
    provider_registry=registry,
    sql_validator=validator,
    query_discovery_service=discovery,
)
```

`DesignerDataService` is an alias for the same class when that name reads better in application
code.

## Data Sources

Commands are immutable dataclasses. A backend can map request data into a command, call the service,
then serialize the returned report through its existing template storage boundary.

```python
from slim_report_core import CreateMySQLDataSourceCommand

data_source = service.create_mysql_data_source(
    report,
    CreateMySQLDataSourceCommand(
        name="Main LIS MySQL",
        host="db.internal",
        port=3306,
        database="lis",
        username="report_user",
        password_ref="LIS_REPORT_PASSWORD",
    ),
)
```

`list_data_sources()` returns `DataSourceSummary` objects. Summaries expose safe connection
descriptors such as host, port, database, username, and password-configured flags. They do not expose
runtime passwords or password reference values.

Connection testing is explicit:

```python
result = service.test_data_source_connection(report, data_source.id)
```

Removing a data source that still owns datasets raises `DataSourceInUseError` unless the caller
passes `cascade=True`.

## View Datasets

View workflows use `MySQLMetadataService` internally. They inspect `information_schema` metadata for
approved views and columns, not report rows.

```python
from slim_report_core import CreateViewDatasetCommand

views = service.list_available_views(report, data_source.id)
schema = service.inspect_view(report, data_source.id, "report_patient_results")

result = service.create_view_dataset(
    report,
    CreateViewDatasetCommand(
        name="Patient Results",
        data_source_id=data_source.id,
        view_name="report_patient_results",
    ),
)
```

`refresh_view_dataset_fields()` reinspects the view and atomically replaces the dataset fields. If
metadata lookup fails, the existing dataset remains unchanged.

## Query Datasets

Query workflows validate SELECT-only SQL before saving or opening a database connection.

```python
from slim_report_core import CreateQueryDatasetCommand, QueryParameter

result = service.create_query_dataset(
    report,
    CreateQueryDatasetCommand(
        name="Orders",
        data_source_id=data_source.id,
        query="SELECT orderid FROM report_orders WHERE orderdate >= :date_from",
        parameters=(QueryParameter("date_from", "date", required=True),),
    ),
)
```

Field discovery is explicit and does not mutate the dataset until applied:

```python
discovery = service.discover_query_fields(
    report,
    result.dataset.id,
    parameter_values={"date_from": date_from},
)
applied = service.apply_discovered_fields(report, result.dataset.id, discovery)
```

Discovery results include the dataset id. Applying a result to a different dataset raises
`StaleDiscoveryResultError`.

## Atomic Updates

Update methods construct and validate replacement models before mutating the report. This keeps
failed validation, metadata, and discovery operations from partially modifying existing
configuration.

Query text changes clear existing fields because the previous field list may no longer describe the
query output. Parameter-only changes revalidate the query dataset and preserve fields.

## Security Boundary

The service does not fetch live report rows, render reports, define HTTP routes, or serialize
credentials. It relies on:

- `SQLValidator` for read-only query validation
- provider-level read-only connection policy for MySQL sessions
- `MySQLMetadataService` for approved view metadata only
- explicit credential handling through runtime passwords or password references owned by the host
  application

Host applications remain responsible for authentication, authorization, persistence, encryption,
audit logging, and request/response shaping.
