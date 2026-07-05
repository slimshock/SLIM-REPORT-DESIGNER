# Validation API

Validation is owned by the `Report` domain model.

JSON serializers load templates into `Report`. After that, callers validate the report itself:

```python
from slim_report_core.serialization import JSONSerializer

report = JSONSerializer().load("template.json")
result = report.validate()

if not result.is_valid:
    for error in result.errors:
        print(error.path, error.code, error.message)
```

`Report.validate()` does not raise exceptions for normal validation failures. It returns a `ReportValidationResult`.

## Result Shape

```python
{
    "valid": False,
    "errors": [
        {
            "code": "binding.required",
            "path": "objects[0].binding",
            "message": "Field objects require a binding expression.",
            "severity": "error",
        }
    ],
}
```

## Current Checks

Validation checks:

- at least one page exists
- page size, unit, orientation, dimensions, and margins
- object ids, types, dimensions, band references, and layer references
- unique ids within pages, objects, bands, layers, and assets
- field bindings and text expressions
- named and inline style values
- asset ids, types, sources, and metadata

Parsing malformed JSON can still raise serialization errors. Domain validation starts after a `Report` object exists.
