# ADR-0001: Project Vision

**Status:** Accepted

**Date:** 2026-07-05

## Context

Python has excellent web frameworks such as Flask, Django, and FastAPI, but there is no widely adopted, framework-native reporting platform comparable to JasperReports or Crystal Reports.

Developers often rely on external Java applications, proprietary software, or manually coded PDF generation. These solutions frequently introduce unnecessary complexity, framework coupling, or licensing concerns.

## Decision

Slim Report Designer will be developed as an open-source reporting platform for Python.

The project will focus on:

* A framework-agnostic reporting engine.
* A Report-first Python domain model.
* JSON as the first built-in persistence format.
* Browser-based visual report designer.
* Extensible plugin architecture.
* Multiple rendering engines.
* Multiple framework adapters.

Flask will be the first supported framework, but not the only target.

## Why

We believe reporting should be a first-class citizen in the Python ecosystem.

Developers should be able to design, preview, render, and export reports without leaving Python.

## Consequences

The project will prioritize long-term architecture over short-term feature development.

Features that compromise extensibility or framework independence will be rejected, even if they simplify early implementation.

The vision is to build infrastructure that other developers can rely on for years.

## 2026-07-05 Architecture Update

Sprint 4 clarified that `Report` is the domain model and JSON is a serializer boundary. The project
still ships JSON support, but future YAML, XML plugin, database, REST, or binary persistence formats
should convert to and from `Report` rather than changing the renderer or public domain model.
