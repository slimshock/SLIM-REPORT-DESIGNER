# LIS Asset Management

Sprint 6.4 gives LIS integrations a clean way to resolve logos and signatures without hardcoding local filesystem paths in templates.

## Recommended Pattern

Store reusable report image assets with stable IDs:

```text
clinic_logo
medtech_signature
pathologist_signature
watermark.default
```

Reference static assets directly from image objects:

```json
{
  "type": "image",
  "assetId": "clinic_logo"
}
```

For Sprint 6.4, `assetId` always means asset provider lookup. Bindings should continue to return actual image sources such as a URL, data URL, or local path already understood by the renderer.

If LIS data contains asset IDs:

```python
{
    "clinic": {"logo_asset_id": "clinic_logo"},
    "signatures": {
        "medtech": "medtech_signature",
        "pathologist": "pathologist_signature",
    },
}
```

Use those values in application logic or template generation, then set `assetId` on the image object. The current renderer does not automatically treat bound strings as asset IDs.

## Filesystem Storage

```python
from slim_report_core.assets import FileSystemAssetProvider
from slim_report_flask import SlimReportDesigner

asset_provider = FileSystemAssetProvider(
    "report_assets",
    base_url="/report-designer/assets",
    allow_save=True,
    max_size_bytes=2_000_000,
)

designer = SlimReportDesigner(
    template_provider=template_provider,
    asset_provider=asset_provider,
    data_provider=data_provider,
    url_prefix="/report-designer",
)
```

Do not store private logos or signatures in the Slim Report Designer repository. Keep production assets in the LIS deployment environment.

## Common LIS Assets

Clinic logo:

```json
{ "id": "clinic_logo", "type": "image", "assetId": "clinic_logo" }
```

Medtech signature:

```json
{ "id": "medtech_signature", "type": "image", "assetId": "medtech_signature" }
```

Pathologist signature:

```json
{ "id": "pathologist_signature", "type": "image", "assetId": "pathologist_signature" }
```

Blank signature slots should use an empty `src` or no source. They render blank in HTML preview and PDF export.

## Database Storage Guidance

Sprint 6.4 ships only the filesystem asset provider. A later database provider can use an app-owned table like:

```sql
CREATE TABLE IF NOT EXISTS report_assets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    asset_id VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    filename VARCHAR(255) NULL,
    content_type VARCHAR(120) NULL,
    content LONGBLOB NULL,
    file_path TEXT NULL,
    category VARCHAR(120) NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    INDEX idx_report_assets_asset_id (asset_id),
    INDEX idx_report_assets_active (is_active)
);
```

The LIS owns migrations, access control, audit trails, and retention rules.

## Patient Portal Safety

Report assets can include signatures. Treat them as protected operational assets:

- Gate designer and asset routes with `auth_required`.
- Use `can_view_asset` and `can_edit_asset` hooks for stricter separation.
- Do not expose `/report-designer/assets/<asset_id>` to patient portal users unless your portal access model explicitly allows it.
- Avoid putting signatures in public static folders.

## Troubleshooting

Missing logo:

- Confirm the template uses `assetId`, not a local `C:\...` path.
- Confirm the file exists under the configured asset folder.
- Confirm the file stem matches the asset ID, such as `clinic_logo.svg` for `clinic_logo`.
- Confirm the provider `base_url` matches the Flask route prefix.

PDF missing image:

- Confirm ReportLab can decode the asset type.
- Try PNG/JPEG if SVG rendering is not supported in your environment.
- Confirm the asset provider can open the file and the file is not zero bytes.

Unexpected blank signature:

- Empty `src`, `null`, `undefined`, and unresolved `{{ ... }}` values intentionally render blank.
- `binding` values are not converted to asset lookups in Sprint 6.4.
