# Flask Database and MySQL Report Demo

This browser example combines the existing SQLite/SQLAlchemy report-template storage demo with the
Sprint 7.3 and Sprint 7.4 MySQL services:

- verified read-only MySQL connection testing;
- approved reporting-view discovery;
- column metadata inspection and report-type normalization;
- the existing visual report designer and SQLite template storage.

The home page explores approved metadata. The embedded Report Designer provides the complete 0.7.0
workflow: data-source testing, view and query datasets, named parameters, field discovery, bindings,
safe persistence, reopen, and bounded live HTML preview.

## Setup

From the repository root in Git Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e "packages/slim_report_core[mysql,sqlalchemy]"
python -m pip install -e packages/slim_report_designer_ui
python -m pip install -e packages/slim_report_flask
python -m pip install -r examples/flask_database_app/requirements.txt
```

The editable core install provides the optional PyMySQL driver through the `mysql` extra. The
requirements file also lists it explicitly so the example's runtime needs are visible.

## Environment

The example automatically loads `examples/flask_database_app/.env` with `python-dotenv`. Copy the
provided template, replace the password placeholder, and keep the resulting `.env` file local:

```bash
cp examples/flask_database_app/.env.example examples/flask_database_app/.env
```

Values already exported by the shell take precedence over `.env`. You can therefore configure the
same values without a file when preferred:

```bash
export SLIM_REPORT_MYSQL_HOST=localhost
export SLIM_REPORT_MYSQL_PORT=3306
export SLIM_REPORT_MYSQL_DATABASE=slim_report_demo
export SLIM_REPORT_MYSQL_USERNAME=slim_report_reader
export SLIM_REPORT_MYSQL_PASSWORD='TestPassword123!'
export SLIM_REPORT_ALLOWED_VIEW_PREFIXES=report_
export SLIM_REPORT_ALLOWED_VIEW_NAMES=
export SLIM_REPORT_ALLOW_CROSS_SCHEMA=false
export SLIM_REPORT_ALLOWED_SCHEMAS=
export SLIM_REPORT_EXAMPLE_DEBUG=false
```

Database, username, and password variables are required. Host defaults to `localhost`; port defaults
to `3306`. Comma-separated exact-name, prefix, and schema allowlists are trimmed safely. Boolean
configuration accepts `true`, `false`, `1`, `0`, `yes`, `no`, `on`, or `off`.

The password remains in the environment. The application stores only the reference
`SLIM_REPORT_MYSQL_PASSWORD` in `MySQLConnectionConfig`; it never displays, logs, or serializes the
resolved value.

## Run

```bash
.\examples\flask_database_app\run_demo.ps1
```

On POSIX systems use `./examples/flask_database_app/run_demo.sh`. The launcher creates an isolated
environment, installs all coordinated distributions through normal package metadata, and starts the
app without `PYTHONPATH` or source injection. Copy `.env.example` to `.env` before launch.

Open <http://127.0.0.1:5000>. The browser workflow is:

```text
Home
  -> Test Connection
  -> Browse Reporting Views
  -> Select report_patient_results
  -> Inspect column metadata
  -> Return to view list
```

The designer is available at
<http://127.0.0.1:5000/report-designer/designer?template=view_laboratory_results>.
It stores templates in the ignored local file `report_templates.db` and seeds the two reports in
`reports/`. Loopback-only safe diagnostics are available at <http://127.0.0.1:5000/diagnostics>.

Inside the Designer, open **Data Sources** to configure a report-owned MySQL connection, then open
**Datasets** to import an approved reporting view or validate and discover fields for a custom
read-only SELECT query. See the [Dataset Manager documentation](../../docs/designer-dataset-manager.md)
for parameter and security behavior.

## Demo Database

Run the scripts in order using a MySQL administrator account, not the restricted report account:

```bash
mysql -u root -p < examples/flask_database_app/sql/sample_schema.sql
mysql -u root -p < examples/flask_database_app/sql/sample_data.sql
mysql -u root -p < examples/flask_database_app/sql/reporting_views.sql
mysql -u root -p < examples/flask_database_app/sql/restricted_user.sql
```

Set `SLIM_REPORT_MYSQL_PASSWORD` to the reader password after replacing the placeholder. The Flask
application must run as `slim_report_reader`, not as the administrator that created the schema.
Saved reports contain only `passwordRef: "SLIM_REPORT_MYSQL_PASSWORD"`. The example injects
`EnvironmentCredentialResolver` into `SlimReportDesigner`; the environment value is resolved only
for connection, discovery, and live preview and is never returned in template JSON. Stop and restart
the process without the variable to verify that the report reopens for editing with an unresolved
credential warning, then restore the variable to reconnect without editing the template.

Depending on MySQL or MariaDB metadata visibility rules, the account may need narrowly scoped
permission to see the approved view's `information_schema` records. Do not grant broad privileges
merely to make discovery convenient.

## What the Example Executes

All MySQL operations use public core APIs:

- read-only session configuration and verification;
- `SELECT 1` connection health check;
- `SELECT DATABASE()` safe connection metadata;
- parameterized reads from `information_schema.VIEWS`;
- parameterized reads from `information_schema.COLUMNS`.
- one validated, parameter-bound SELECT for field discovery;
- bounded, unbuffered SELECT execution for live preview.

The home-page explorer has no SQL editor. The Designer query editor accepts only a single validated
read-only SELECT and the runtime binds values through PyMySQL. Preview rows are streamed, escaped,
bounded, returned with `no-store`, and never copied into the saved report.

## Manual Acceptance Check

1. Start the app with the restricted account environment.
2. Confirm the home page shows database, username, provider, and allowlists—but no password.
3. Run **Test Connection** and confirm read-only verification succeeds.
4. Open **Reporting Views** and confirm both `report_` views appear while base tables do not.
5. Inspect `report_laboratory_results` and confirm decimal, boolean, date, and datetime fields map correctly.
6. Open `/views/report_view%3B` and confirm the invalid identifier is rejected safely.
7. Confirm no page displays report rows or credentials.

## Security

The example's read-only session and SQL safeguards are defense in depth.

The configured MySQL account must still have only the minimum required `SELECT` privileges,
preferably limited to approved reporting views. Application metadata policies and read-only session
settings do not replace MySQL permission controls.

Do not enable Flask debug mode outside local development. Even with
`SLIM_REPORT_EXAMPLE_DEBUG=true`, this example never deliberately renders passwords, resolved
credentials, connection dictionaries, or raw driver exceptions.

### Import troubleshooting

If another application imports an older installed core, reinstall the checkout:

```bash
python -m pip uninstall -y slim-report-core
python -m pip install -e "packages/slim_report_core[mysql,sqlalchemy]"
```

The app intentionally contains no checkout path injection. Verify imports resolve from the launcher's
isolated environment when troubleshooting.
