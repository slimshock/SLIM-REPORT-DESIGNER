# ADR-0003: Framework-Agnostic Core

**Status:** Accepted

**Date:** 2026-07-05

## Context

Many libraries become tightly coupled to a single framework.

This limits reuse in desktop applications, command-line tools, scheduled jobs, and other Python environments.

## Decision

The reporting engine will be completely independent of Flask, Django, FastAPI, SQLAlchemy, or any other framework.

The core package will only depend on the Python standard library and carefully selected optional dependencies.

Framework support will be provided through adapters.

Example:

```
slim_report_core
        ▲
        │
 ┌──────┼────────────┐
 │      │            │
Flask Django FastAPI CLI
```

## Why

This architecture allows the same report engine to be reused everywhere.

Frameworks become integrations rather than dependencies.

## Consequences

The core package must never import framework-specific modules.

Adapters are responsible for:

* Authentication
* Routing
* Database integration
* Storage
* Permissions
* Framework-specific configuration

This rule should be enforced during code reviews.
