# Querying Reports

`Report` includes developer-friendly object query helpers.

`report.objects` remains a list-like collection, so existing code can still index, append, and iterate it. It is also callable:

```python
all_objects = report.objects()
large_objects = report.objects(lambda obj: obj.width > 300)
```

## Find One Object

Find by id:

```python
title = report.find("title")
```

Find by predicate:

```python
first_text = report.find(lambda obj: obj.type == "text")
```

Find by object name:

```python
header = report.find_by_name("Header")
```

`find_by_name()` reads the object `properties["name"]` value.

## Type Helpers

```python
texts = report.text_objects()
fields = report.fields()
images = report.images()
tables = report.tables()
```

Each type helper accepts an optional predicate:

```python
primary_text = report.text_objects(lambda obj: obj.properties.get("role") == "primary")
visible_fields = report.fields(lambda obj: obj.visible)
```

These helpers return lists. Missing matches return an empty list, while `find()` and `find_by_name()` return `None`.
