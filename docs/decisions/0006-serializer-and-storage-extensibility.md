# ADR-0006: Serializer and Storage Extensibility

**Status:** Accepted

**Date:** 2026-07-05

## Context

Sprint 4 moved Slim Report Designer to a `Report`-first architecture. JSON remains the first built-in persistence format, but the system must support future YAML, database, REST, binary, and plugin-provided formats without changing rendering or the public domain model.

The same pressure applies to storage. Flask currently uses JSON files, but production applications may want database-backed templates, object storage, versioned APIs, or custom repositories.

## Decision

Serialization and storage are boundary concerns.

Serializers convert external formats to and from `Report`:

```text
external format -> Serializer -> Report
Report ---------> Serializer -> external format
```

Storage providers may use serializers internally, but storage must still return `Report` to framework adapters and tools.

```text
File storage ----+
Database storage +----> Storage provider ----> Report
Object storage --+              |
REST storage ----+              v
                         Serializer when needed
```

JSON remains a built-in serializer. YAML can be added as another serializer. XML should be allowed as a plugin serializer. Database storage can store serialized documents, relational rows, or custom records, as long as loading returns `Report`.

Database storage has three valid implementation shapes:

- Store serializer output as a document column and deserialize to `Report` on load.
- Decompose `Report` into relational tables and rehydrate the domain model on load.
- Use a custom serializer/storage pair for application-specific persistence.

## Consequences

Renderers, validators, object factories, and the `Report` model must not depend on JSON, YAML, XML, database libraries, Flask, or storage details.

Adapters may choose a serializer or storage provider, then operate on `Report`.

Serializer plugins must preserve the same domain invariants as `JSONSerializer`: concrete objects are created through `ObjectFactory`, validation runs on `Report`, and renderers receive `Report`.

This makes JSON optional for applications that create reports directly in Python or load them from another persistence mechanism.
