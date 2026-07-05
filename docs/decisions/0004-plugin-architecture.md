# ADR-0004: Plugin-First Architecture

**Status:** Accepted

**Date:** 2026-07-05

## Context

Reporting systems naturally grow over time.

New widgets, exporters, storage providers, rendering engines, and integrations will continually be requested.

Hard-coding these features into the core would eventually produce a monolithic system that is difficult to maintain.

## Decision

Slim Report Designer will adopt a plugin-first architecture.

The following components will be extensible:

* Widgets
* Exporters
* Data Providers
* Storage Providers
* Framework Adapters
* Expression Functions
* Future Designer Extensions

The core engine will expose registries for each extension point.

Example:

```python
WidgetRegistry.register(TextWidget())
ExporterRegistry.register(PDFExporter())
StorageRegistry.register(FileStorage())
```

## Why

A plugin-first design encourages:

* Separation of concerns.
* Community contributions.
* Easier testing.
* Easier maintenance.
* Cleaner architecture.

Users should be able to extend the platform without modifying the core.

## Consequences

The core should define interfaces and contracts rather than concrete implementations whenever practical.

Public extension APIs must remain stable.

Breaking plugin APIs should be treated as major version changes.
