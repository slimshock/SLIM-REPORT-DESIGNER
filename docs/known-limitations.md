# Known Limitations

- MySQL is the only database runtime provider; no database-agnostic provider layer is promised.
- Reporting views and least-privilege users must be provisioned by the host application or DBA.
- TLS options require an application-controlled connection factory.
- Live preview supports the bounded primary-dataset Detail-band workflow, not joins between report
  datasets, subreports, nested groups, or arbitrary scripting.
- Browser and live-MySQL compatibility depend on environment-specific optional tests.
- Django and FastAPI packages remain placeholders; Flask is the completed integration.
- Template storage schema migrations remain application-owned.
- Large reports are intentionally truncated or rejected by configured row/page/output limits.
