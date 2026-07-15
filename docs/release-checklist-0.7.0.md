# Release Checklist: 0.7.0

## Functionality

- [ ] New Report, Data Sources, Datasets, Fields, bindings, Save, reopen, static preview, live preview,
      and PDF export pass manual acceptance.
- [ ] Empty, limit, timeout, cancellation, offline recovery, and stale-schema repair paths pass.

## Security

- [ ] SQL, fuzz, secret-leak, runtime-value, HTML, identifier, cleanup, and memory tests pass.
- [ ] Restricted user has view-level SELECT only; no secret or runtime output is packaged or logged.

## Compatibility

- [ ] Supported Python CI passes, including Python 3.11.
- [ ] Optional live MySQL and browser checks are run where configured or recorded as skipped.

## Packaging

- [ ] All wheels/sdists build, metadata checks pass, wheel contents pass, and clean installs pass.
- [ ] Core imports without Flask or PyMySQL; installed Designer assets and Flask demo start correctly.

## Documentation

- [ ] README, developer guide, MySQL security/TLS, migration, release notes, limitations, public API,
      and manual acceptance documents are current.
- [ ] Version is synchronized at 0.7.0 and no publishing step has run automatically.
