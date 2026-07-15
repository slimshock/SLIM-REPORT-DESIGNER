# Designer MySQL Dataset Manager

The SLIM REPORT DESIGNER toolbar includes **Datasets** beside **Data Sources**. The
Dataset Manager configures MySQL reporting-view datasets and custom read-only query
datasets on the active report. It discovers field metadata only; it does not display
database rows or execute complete report datasets.

## Reporting View Datasets

Choose **Add Dataset**, then **Reporting View**. Select a configured MySQL data source,
search the approved view list, and select a view to inspect its ordered columns. Only
views returned by the metadata policy are shown. Base tables and system schemas are not
available through this form.

The field list shows the MySQL type, normalized report type, nullability, and column
comment where available. Saving creates the dataset and imports the inspected fields
atomically. Existing view datasets can be renamed, changed to another approved view, or
refreshed. A refresh reports added, removed, and type-changed fields without changing
report objects.

## Read-Only Query Datasets

Choose **Custom SELECT Query** and enter SQL in the query editor. Only a single read-only
SELECT or WITH...SELECT query is permitted. Use named parameters in `:name` form.

**Validate Query** runs the SQL security engine without opening a database connection.
It detects parameters in first-appearance order. Add definitions for every detected
parameter and configure its type, required state, optional default, and display label.
Supported parameter types are string, integer, float, decimal, boolean, date, time, and
datetime.

Temporary discovery values are separate from defaults. They exist only while the form is
open and are excluded from the report template, browser storage, undo history, responses,
and logs. Query parameter values are sent through driver binding and are never inserted
into SQL text.

**Discover Fields** executes the validated SELECT using the restricted read-only MySQL
provider. Only a very small number of rows are fetched, and row values are not returned to
the Designer. Editing SQL or parameter definitions invalidates validation and discovery.
The current query must be validated and discovered again before it can be saved.

For an unchanged existing query, **Apply Fields** explicitly rediscovers and applies field
metadata as one history operation. When SQL or parameter definitions change, **Save
Dataset** performs authoritative server-side discovery again before returning the atomic
report update. This prevents stale or client-modified field metadata from being saved.

## Editing, Removal, And Report State

Dataset summaries show the name, source, data-source label, field count, and parameter
count. Full SQL, credentials, defaults, and temporary values are not shown in summaries.
The **Fields** action reads stored template metadata and does not connect to MySQL.

Successful create, update, refresh, apply, and delete operations replace the active report,
mark it modified, and create one undo entry. Listing views, inspecting a draft, validating,
and discovering fields do not mark the report modified. The normal Designer **Save** action
persists datasets, and reopening the report restores IDs, source references, SQL,
definitions, and fields. Deleting a dataset does not remove its parent data source.

## Security

The query editor rejects write statements, multiple statements, MySQL user and system
variables, assignment syntax, file access, dangerous functions, and locking clauses. SQL
is sent only in POST or PUT request bodies. The JavaScript and Flask adapter do not import
PyMySQL, construct driver options, query `information_schema`, or interpret cursor metadata.

Production MySQL connections must use dedicated accounts with minimum SELECT privileges,
preferably limited to approved reporting views.

Application SQL validation and read-only session configuration provide defense in depth
but do not replace database permissions. Use HTTPS in production because temporary query
parameter values are sent to the server for discovery.

Sprint 7 remains MySQL-only. Dataset row previews, report execution, field drag-and-drop,
canvas bindings, and database-driven rendering are outside this workflow.
