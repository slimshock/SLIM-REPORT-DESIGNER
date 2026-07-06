# JSON Template Schema

The JSON template format is early alpha. This page documents the practical shape used by the current designer, examples, serializer, preview, and PDF export. Do not treat this as a frozen public schema yet.

## Top-Level Shape

```json
{
  "version": "0.1",
  "metadata": {},
  "page": {},
  "bands": [],
  "objects": [],
  "assets": [],
  "data": {}
}
```

Common top-level keys:

- `version`
- `metadata`
- `page`
- `bands`
- `objects`
- `assets`
- `data`

Optional keys such as `pages`, `layers`, and `styles` may appear when the domain model contains them.

## Page

Page settings describe the canvas and exported page:

- `size`
- `orientation`
- `unit`
- `width`
- `height`
- `margin_top`
- `margin_right`
- `margin_bottom`
- `margin_left`
- `background_color`
- `transparent`

## Bands

Bands group objects into report regions:

- `id`
- `type`
- `name`
- `y`
- `height`
- `background_color`
- `visible`
- `locked`
- `repeat`

Current common band types:

- `page_header`
- `detail`
- `page_footer`

## Band Repeat

Only Detail band repeating is supported in this sprint.

```json
{
  "enabled": true,
  "data_path": "results",
  "row_height": 24,
  "preview_rows": 20,
  "empty_message": "No records"
}
```

Repeat fields:

- `enabled`
- `data_path`
- `row_height`
- `preview_rows`
- `empty_message`

## Objects

Objects are drawable report elements:

- `id`
- `type`
- `band`
- `x`
- `y`
- `width`
- `height`
- `locked`
- `style`

Supported object types:

- `text`
- `field`
- `line`
- `rectangle`
- `image`

## Field Object

Field objects bind to render data:

```json
{
  "id": "patient_name",
  "type": "field",
  "band": "page_header",
  "x": 40,
  "y": 80,
  "width": 240,
  "height": 18,
  "binding": "patient.name",
  "source_path": "patient.name"
}
```

`source_path` is optional metadata used by designer workflows.

## Image Object

Image objects can use these fields and style values:

- `src`
- `source`
- `alt`
- `object_fit`
- `opacity`
- `border_radius`
- `border_width`
- `border_color`
- `background_color`

Example:

```json
{
  "id": "logo",
  "type": "image",
  "x": 40,
  "y": 24,
  "width": 120,
  "height": 60,
  "src": "data:image/png;base64,...",
  "alt": "Lab logo",
  "style": {
    "object_fit": "contain",
    "opacity": 1,
    "border_radius": 0
  }
}
```

## Data

`data` is optional. Old templates without `data` still work.

Common keys:

- `data.sample`: sample render data for preview/export
- `data.fields`: field metadata used by the designer

## Minimal Example

```json
{
  "version": "0.1",
  "metadata": {
    "title": "Simple Report"
  },
  "page": {
    "size": "A4",
    "orientation": "portrait",
    "unit": "px",
    "width": 595,
    "height": 842
  },
  "bands": [],
  "objects": [
    {
      "id": "title",
      "type": "text",
      "x": 40,
      "y": 40,
      "width": 300,
      "height": 28,
      "text": "Simple Report"
    }
  ],
  "assets": []
}
```

## Repeating Detail Example

```json
{
  "bands": [
    {
      "id": "detail",
      "type": "detail",
      "name": "Detail",
      "y": 150,
      "height": 620,
      "repeat": {
        "enabled": true,
        "data_path": "results",
        "row_height": 24,
        "preview_rows": 20,
        "empty_message": "No records"
      }
    }
  ],
  "objects": [
    {
      "id": "result_test",
      "type": "field",
      "band": "detail",
      "x": 48,
      "y": 188,
      "width": 130,
      "height": 18,
      "binding": "test",
      "source_path": "results[].test"
    }
  ],
  "data": {
    "sample": {
      "results": [
        {"test": "WBC", "value": "7.1"}
      ]
    }
  }
}
```
