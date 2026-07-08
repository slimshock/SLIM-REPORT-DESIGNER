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
- `pagination`
- `print`

Pagination settings are optional. Missing settings use the default values below:

```json
{
  "pagination": {
    "enabled": true,
    "repeat_page_header": true,
    "repeat_page_footer": true,
    "respect_margins": true
  }
}
```

Basic pagination is used by HTML preview and PDF export for repeating Detail rows and Detail-band table rows.

Print/export settings are optional:

```json
{
  "print": {
    "show_browser_print_button": true,
    "default_filename": "report.pdf",
    "pdf_title": "Report",
    "pdf_author": "Slim Report Designer",
    "pdf_subject": "",
    "print_background": true
  }
}
```

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
- `group`

Current common band types:

- `page_header`
- `group_header`
- `detail`
- `group_footer`
- `page_footer`

## Band Repeat

Only Detail band repeating is supported.

## Band Group

Group Header and Group Footer bands can carry group settings:

```json
{
  "id": "group_header_results",
  "type": "group_header",
  "group": {
    "id": "results_section",
    "data_path": "results",
    "field": "section",
    "sort": "none"
  }
}
```

Group fields expose bindings such as `group.value`, `group.count`, and `group.sum.numeric_value`.

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
- `conditions`
- `formula`
- `formula_mode`

Supported object types:

- `text`
- `field`
- `line`
- `rectangle`
- `image`
- `barcode`
- `qrcode`
- `table`

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

Set `formula_mode` to `true` and provide `formula` to render a safe computed expression instead of a direct binding. Conditional formatting rules live in `conditions` and can apply style overrides or hide an object.

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

## Barcode Object

Barcode objects can bind to render data or use a literal fallback value:

```json
{
  "id": "order_barcode",
  "type": "barcode",
  "band": "page_header",
  "x": 390,
  "y": 24,
  "width": 160,
  "height": 48,
  "binding": "order.id",
  "value": "ORDER-1001",
  "format": "code128",
  "show_text": true,
  "style": {
    "foreground_color": "#111827",
    "background_color": "#ffffff",
    "font_size": 8
  }
}
```

`binding` is resolved first. If it is missing or empty, renderers use `value`.

Supported fields:

- `binding`
- `value`
- `format`
- `symbology`
- `show_text`
- `foreground_color`
- `background_color`
- `font_size`

## QR Code Object

QR code objects use the same binding-first value resolution:

```json
{
  "id": "order_qr",
  "type": "qrcode",
  "band": "page_header",
  "x": 40,
  "y": 24,
  "width": 80,
  "height": 80,
  "binding": "order.id",
  "value": "ORDER-1001",
  "error_correction": "M",
  "style": {
    "foreground_color": "#111827",
    "background_color": "#ffffff"
  }
}
```

Supported fields:

- `binding`
- `value`
- `error_correction`
- `foreground_color`
- `background_color`

## Table Object

The basic Table object renders simple array-bound tabular data. It is not a full spreadsheet or advanced table engine.

```json
{
  "id": "results_table",
  "type": "table",
  "band": "detail",
  "x": 40,
  "y": 180,
  "width": 515,
  "height": 260,
  "data_path": "results",
  "header": {
    "visible": true,
    "height": 24,
    "background_color": "#e5e7eb",
    "color": "#111827",
    "font_size": 10,
    "bold": true
  },
  "row": {
    "height": 22,
    "background_color": "#ffffff",
    "alternate_background_color": "#f9fafb",
    "color": "#111827",
    "font_size": 10
  },
  "border": {
    "width": 1,
    "color": "#d1d5db"
  },
  "columns": [
    {
      "id": "test",
      "label": "Test",
      "binding": "test",
      "width": 150,
      "align": "left",
      "source_path": "results[].test"
    }
  ]
}
```

Column bindings are row-relative. For a table bound to `results`, `test` resolves against the current row.

When a basic table is placed in the Detail band and has more rows than fit in its configured height, HTML preview and PDF export continue the table on generated pages and repeat the table header when visible.

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
