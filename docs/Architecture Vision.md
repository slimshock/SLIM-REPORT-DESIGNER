# Architecture Vision

This document records the current architecture vision after the Sprint 4 review. The detailed
implementation rules live in `docs/architecture.md`; ADR-0007 records the accepted decision.

## Repository Shape

```text
slim-report-designer/
  packages/
    slim_report_core/
    slim_report_flask/
    slim_report_django/
    slim_report_fastapi/
    slim_report_cli/
  examples/
    pure_python/
    flask_app/
    django_app/
    fastapi_app/
    lis_demo/
    pos_demo/
  docs/
    decisions/
  tests/
  scripts/
```

## Core Principle

`slim_report_core` must remain pure Python.

It must not import Flask, Django, FastAPI, SQLAlchemy, or any web framework. Frameworks, databases,
HTTP, authentication, and host-application concerns belong in adapters or plugins.

## Report-First Architecture

```text
                           +------------------+
Beginner Python API ------>|                  |
Builder API -------------->|                  |
AI generated code -------->|                  |       +----------------+
Designer ----------------->|      Report      |------>| HTML renderer  |
Flask adapter ------------>|  domain model    |       +----------------+
CLI ---------------------->|                  |       +----------------+
Serializer plugins ------->|                  |------>| PDF renderer   |
                           +------------------+
                                  |
                                  v
                           Report.validate()
```

The central model is `Report`, not JSON. JSON remains the first built-in persistence format, but it
is not required for direct Python report creation, AI-generated report code, framework adapters, CLI
commands, or future designer state.

## Persistence Vision

```text
JSON file/dict ----> JSONSerializer --------+
YAML file/dict ----> YAMLSerializer --------+
XML plugin -------> XMLSerializer plugin ---+----> Report
Database rows ----> Storage/Serializer -----+
REST payload -----> RESTSerializer ---------+
Binary package ---> PackageSerializer ------+

Report ------------------------------------------> Serializer/Storage ---> external format
```

Serializers and storage providers are boundary layers. They may use files, databases, object
storage, REST APIs, or plugin formats internally, but they should return `Report` to the rest of the
system.

## Sprint Direction

```text
Developer Preview
  Sprint 1 - Foundation                    done
  Sprint 2 - Core breathing room           done
  Sprint 3 - Report model                  done
  Sprint 4 - Developer experience          done
  Sprint 5 - Persistence                   next
  Sprint 6 - Canvas designer

Alpha
  Widgets, export quality, bands, pagination, tables

Beta
  Assets, barcode/QR, expressions, variables, marketplace

Stable
  Community, performance, plugins, documentation
```

Sprint 5 should add persistence without moving storage concerns into `Report`. Sprint 6 should build
the designer against `Report`, `Page`, concrete `ReportObject` classes, and `ObjectFactory`.

## Review Answers

- A beginner should be able to build a report with `Report`, `page()`, and page helper methods before reading the JSON schema.
- AI can generate reports by targeting the same public Python API or serializer input at the boundary.
- The Designer can manipulate `Report` directly; JSON editing is temporary.
- Flask can use `Report` directly after storage/serializer loading.
- CLI can use `Report` directly after loading input files.
- JSON can become optional because renderers and validation depend on `Report`.
- YAML can be added later as another serializer.
- XML can become a serializer plugin.
- Database storage can serialize or decompose `Report`, but loading must return `Report`.
