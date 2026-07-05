# Documentation

Project documentation, architecture decisions, and design notes live here.

Start with:

- `principles.md`
- `manifesto.md`
- `decisions/`

Current implementation notes:

- Rendering lives in `slim_report_core.rendering`.
- Flask routes call core rendering functions and do not duplicate HTML or PDF rendering logic.
- Core import boundaries are enforced by tests.
