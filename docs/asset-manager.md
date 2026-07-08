# Asset Manager

Sprint 6.4 adds a framework-agnostic asset provider foundation for report images.

The core package does not know about Flask routes or application databases. Renderers receive an optional asset provider and use it to resolve image objects that declare `assetId`.

## Public API

```python
from slim_report_core.assets import FileSystemAssetProvider
from slim_report_core import render_html, render_pdf

asset_provider = FileSystemAssetProvider(
    "report_assets",
    base_url="/report-designer/assets",
)

html = render_html(report, data, asset_provider=asset_provider)
pdf = render_pdf(report, data, asset_provider=asset_provider)
```

Image objects can reference a reusable asset:

```json
{
  "id": "logo",
  "type": "image",
  "assetId": "clinic_logo",
  "x": 40,
  "y": 24,
  "width": 140,
  "height": 48
}
```

`assetId` is the canonical key. The resolver also accepts `asset` and `asset_id` as compatibility aliases.

Existing direct image sources still work:

```json
{ "type": "image", "src": "/static/images/logo.png" }
```

Bindings remain data-driven:

```json
{ "type": "image", "binding": "clinic.logo_url" }
```

Bindings are not treated as asset IDs in Sprint 6.4. If a binding returns `clinic_logo`, the renderer treats it as a normal image source string, not a provider lookup.

## Asset IDs

Asset IDs are validated with:

```text
^[A-Za-z0-9_.-]+$
```

Allowed examples: `clinic_logo`, `medtech_signature`, `pathologist_signature`, `header-logo-v1`, `watermark.default`.

Rejected examples: `../secret`, `../../app.py`, `C:\secret`, `folder/image`, `image.png/other`, and empty strings.

## FileSystemAssetProvider

```python
from slim_report_core.assets import FileSystemAssetProvider

assets = FileSystemAssetProvider(
    "report_assets",
    base_url="/report-designer/assets",
    allow_save=False,
    allow_delete=False,
    max_size_bytes=2_000_000,
)
```

Default allowed extensions are `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, and `.svg`.

Save and delete are disabled by default. The provider prevents path traversal, rejects unsupported extensions, and never serves files outside the configured asset folder.

## Rendering

HTML:

- Direct URLs render as `<img src="...">`.
- Data URLs render as-is.
- `assetId` uses `get_asset_url(asset_id)` when a URL is configured.
- If no URL is configured, provider bytes are embedded as a data URL.
- Empty, `null`, `undefined`, and unresolved `{{ ... }}` image values render blank.

PDF:

- Data URLs are decoded when ReportLab supports the image.
- Direct local paths are passed to ReportLab as before.
- Remote `http://` and `https://` URLs are not fetched server-side.
- `assetId` reads bytes with `asset_provider.open_asset(asset_id)`.
- Missing or unsupported images are skipped without crashing.

## Flask Routes

When `SlimReportDesigner(asset_provider=...)` is configured, Flask exposes:

```text
GET    /report-designer/api/assets
GET    /report-designer/api/assets/<asset_id>
POST   /report-designer/api/assets/<asset_id>
DELETE /report-designer/api/assets/<asset_id>
GET    /report-designer/assets/<asset_id>
```

The route prefix is configurable. With `url_prefix="/admin/reports"`, use `/admin/reports/api/assets` and `/admin/reports/assets/<asset_id>`.

Asset errors use:

```json
{
  "ok": false,
  "error": {
    "code": "asset_not_found",
    "message": "Asset not found: clinic_logo"
  }
}
```

## Permissions

Asset routes honor `auth_required`.

Optional hooks:

```python
SlimReportDesigner(
    asset_provider=asset_provider,
    can_view_asset=lambda asset_id: current_user.can_view_reports,
    can_edit_asset=lambda asset_id: current_user.can_manage_report_assets,
)
```

If no asset hooks are supplied, authenticated designer users can view assets and provider flags still control save/delete.

## Security Notes

Assets are user-controlled files. Production apps should keep upload/save disabled unless needed, restrict asset folders to report images only, reject executable file types, avoid trusting uploaded filenames, avoid local absolute paths in templates, and avoid server-side remote URL fetching.

SVG is supported by default for convenience. Stricter environments may disable it with `allowed_extensions={".png", ".jpg", ".jpeg", ".webp"}`.

## Limitations

Sprint 6.4 is not a full media library. There is no advanced asset browser, tagging workflow, thumbnail generation, database asset provider, or drag/drop upload manager yet.
