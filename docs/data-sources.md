# Data Sources

Sprint 7.1 adds framework-agnostic metadata for MySQL-backed report data sources and datasets.
These models live in `slim_report_core` and do not connect to MySQL or execute SQL.

## Programmatic Example

```python
from slim_report_core import (
    DatasetSourceType,
    MySQLConnectionConfig,
    Report,
    ReportDataSource,
    ReportDataset,
)

report = Report("Patient Results")

connection = MySQLConnectionConfig(
    host="localhost",
    port=3306,
    database="lis",
    username="report_user",
    password_ref="SLIM_REPORT_MYSQL_PASSWORD",
)

data_source = ReportDataSource(
    id="main_mysql",
    name="Main MySQL",
    type="mysql",
    connection=connection,
)

dataset = ReportDataset(
    id="patient_results",
    name="Patient Results",
    data_source_id="main_mysql",
    source_type=DatasetSourceType.VIEW,
    view_name="report_patient_results",
)

report.add_data_source(data_source)
report.add_dataset(dataset)
```

## Resulting JSON

Normal serialization stores `passwordRef`, not a runtime password:

```json
{
  "version": "1.0",
  "metadata": {
    "title": "Patient Results",
    "description": null,
    "author": null,
    "tags": [],
    "custom": {}
  },
  "page": {
    "width": 8.5,
    "height": 11.0,
    "unit": "in",
    "orientation": "portrait",
    "margin_top": 0.5,
    "margin_right": 0.5,
    "margin_bottom": 0.5,
    "margin_left": 0.5,
    "background_color": "#ffffff",
    "transparent": false
  },
  "objects": [],
  "bands": [],
  "assets": [],
  "dataSources": [
    {
      "id": "main_mysql",
      "name": "Main MySQL",
      "type": "mysql",
      "connection": {
        "type": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "lis",
        "username": "report_user",
        "charset": "utf8mb4",
        "connectTimeout": 10,
        "queryTimeout": 30,
        "passwordRef": "SLIM_REPORT_MYSQL_PASSWORD"
      }
    }
  ],
  "datasets": [
    {
      "id": "patient_results",
      "name": "Patient Results",
      "dataSourceId": "main_mysql",
      "sourceType": "view",
      "fields": [],
      "parameters": [],
      "viewName": "report_patient_results"
    }
  ]
}
```

## Supported Metadata

- Data-source type: `mysql`
- Dataset source types: `view`, `query`
- Field data types: `string`, `integer`, `float`, `decimal`, `boolean`, `date`, `time`, `datetime`, `binary`, `unknown`
- Parameter data types: `string`, `integer`, `float`, `decimal`, `boolean`, `date`, `time`, `datetime`

Query parameters are metadata only. Parameter values must not be interpolated into SQL strings.

## Credential Resolution

Use `password_ref` for report JSON and resolve it at runtime:

```python
password = connection.resolve_password()
```

Resolution checks a runtime password first, then a supplied resolver, then environment variables.
The resolved password is not serialized by default.

For secure connection creation, testing, read-only session enforcement, and provider registration,
see [MySQL Data-Source Provider](mysql-data-source-provider.md).
