# Flask Database and MySQL Metadata Example

This browser example combines the existing SQLite/SQLAlchemy report-template storage demo with the
Sprint 7.3 and Sprint 7.4 MySQL services:

- verified read-only MySQL connection testing;
- approved reporting-view discovery;
- column metadata inspection and report-type normalization;
- the existing visual report designer and SQLite template storage.

The MySQL portion reads metadata only. It does not execute reporting views, fetch report rows, or
accept custom SQL.

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
export SLIM_REPORT_MYSQL_DATABASE=slim_report_test
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
python examples/flask_database_app/app.py
```

Direct execution prefers the package sources in this checkout, so an older globally installed
`slim_report_core` cannot shadow the Sprint 7 APIs. Editable installation is still recommended so
the optional driver and all example dependencies are available.

Open <http://127.0.0.1:5000>. The browser workflow is:

```text
Home
  -> Test Connection
  -> Browse Reporting Views
  -> Select report_patient_results
  -> Inspect column metadata
  -> Return to view list
```

The existing designer remains available at
<http://127.0.0.1:5000/report-designer/designer?template=complete_sprint5_lab_report>.
It stores templates in the ignored local file `report_templates.db` and seeds examples from the
repository's sample-template directories.

## Optional Test Database

Run this setup using a MySQL administrator account, not the restricted report account:

```sql
CREATE DATABASE slim_report_test;

USE slim_report_test;

CREATE TABLE patients (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_no VARCHAR(30) NOT NULL,
    patient_name VARCHAR(150) NOT NULL,
    birthdate DATE NULL,
    balance DECIMAL(12,2) NOT NULL DEFAULT 0,
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE VIEW report_patient_results AS
SELECT
    id,
    patient_no,
    patient_name,
    birthdate,
    balance,
    active,
    created_at
FROM patients;

CREATE USER 'slim_report_reader'@'localhost'
IDENTIFIED BY 'replace-this-password';

GRANT SELECT ON slim_report_test.report_patient_results
TO 'slim_report_reader'@'localhost';

FLUSH PRIVILEGES;
```

Set `SLIM_REPORT_MYSQL_PASSWORD` to the reader password after replacing the placeholder. The Flask
application must run as `slim_report_reader`, not as the administrator that created the schema.

Depending on MySQL or MariaDB metadata visibility rules, the account may need narrowly scoped
permission to see the approved view's `information_schema` records. Do not grant broad privileges
merely to make discovery convenient.

## What the Example Executes

The only MySQL operations are those implemented by the public core APIs:

- read-only session configuration and verification;
- `SELECT 1` connection health check;
- `SELECT DATABASE()` safe connection metadata;
- parameterized reads from `information_schema.VIEWS`;
- parameterized reads from `information_schema.COLUMNS`.

There is no SQL text area, query editor, row preview, export, custom query route, or report-data
execution path.

## Manual Acceptance Check

1. Start the app with the restricted account environment.
2. Confirm the home page shows database, username, provider, and allowlists—but no password.
3. Run **Test Connection** and confirm read-only verification succeeds.
4. Open **Reporting Views** and confirm `report_patient_results` appears while `patients` does not.
5. Inspect the view and confirm `decimal(12,2)` maps to `decimal` and `tinyint(1)` maps to `boolean`.
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

The direct example command above bootstraps local source paths itself, but other Python entry points
continue to follow the active environment's normal package resolution.
