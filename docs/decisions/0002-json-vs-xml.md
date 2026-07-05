# ADR-0002: JSON as the First Built-In Persistence Format

**Status:** Accepted

**Date:** 2026-07-05

## Context

Many existing reporting systems store templates using XML.

Although XML is expressive, it is often verbose, difficult to merge in version control, and less approachable for modern Python developers.

## Decision

Slim Report Designer will ship JSON as the first built-in persistence format.

JSON is a persistence format, not the core domain model. JSON templates are converted to and from `Report` by serializers.

Example:

```json
{
  "page": {
    "size": "A4"
  },
  "objects": []
}
```

## Why

JSON provides several advantages:

* Native support in Python.
* Easy serialization and deserialization.
* Friendly with REST APIs.
* Easier Git diffs.
* Easier merging.
* Human-readable.
* Simple generation from code.
* Simple generation by AI.

JSON also aligns naturally with JavaScript, which will power the browser-based designer.

## Consequences

The JSON schema becomes a public persistence API.

Future versions must preserve backwards compatibility whenever possible.

Breaking schema changes require migration tools and versioned schemas.

The renderer and `Report` domain model must not depend on JSON-specific APIs.

YAML may be added later as another serializer. XML may be implemented as a plugin serializer. These
formats should not require changes to `Report` or renderers.
