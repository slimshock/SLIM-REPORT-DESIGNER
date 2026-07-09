"""Serve the framework-agnostic designer UI without Flask."""

from __future__ import annotations

import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_PACKAGE = REPO_ROOT / "packages" / "slim_report_designer_ui"

if str(UI_PACKAGE) not in sys.path:
    sys.path.insert(0, str(UI_PACKAGE))

from slim_report_designer_ui import static_root  # noqa: E402


class DesignerStaticHandler(SimpleHTTPRequestHandler):
    """HTTP handler rooted at the designer static package."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(static_root()), **kwargs)


def main() -> int:
    """Run a small local static server."""
    host = "127.0.0.1"
    port = 8008
    server = ThreadingHTTPServer((host, port), DesignerStaticHandler)
    print(f"Serving Slim Report Designer UI at http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping designer UI server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
