#!/usr/bin/env python3
"""
RandomFlix Local Server (http://localhost:8765)
Serves `docs/` AND provides local `/api/save-local` and `/api/sync-livechart` endpoints
so clicking "💾 Save & Enrich Locally" or "📥 Sync LiveChart" in the browser writes
`data/shows_source.json` and runs `scripts/enrich_catalog.py` directly on your Mac
without needing GitHub Actions.
"""

from __future__ import annotations

import http.server
import importlib
import json
import pathlib
import sys
from typing import Any

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT_DIR / "docs"
SOURCE_PATH = ROOT_DIR / "data" / "shows_source.json"

sys.path.insert(0, str(ROOT_DIR / "scripts"))
import enrich_catalog  # noqa: E402
import manage_shows  # noqa: E402


class ReusableThreadingHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


class RandomFlixLocalHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(DOCS_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        try:
            super().log_message(format, *args)
        except Exception:
            pass

    def do_GET(self) -> None:
        if self.path.split("?")[0] == "/api/ping":
            self._send_json(200, {"ok": True, "mode": "local"})
            return
        super().do_GET()

    def do_POST(self) -> None:
        route = self.path.split("?")[0]
        if route == "/api/save-local":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw_body)
                if not isinstance(payload, dict) or "shows" not in payload:
                    self._send_json(400, {"ok": False, "error": "Invalid payload: missing 'shows' list."})
                    return

                SOURCE_PATH.parent.mkdir(parents=True, exist_ok=True)
                SOURCE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

                importlib.reload(enrich_catalog)
                catalog = enrich_catalog.enrich_all(force_refresh=False)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "totalShows": catalog.get("totalShows", 0),
                        "totalInList": catalog.get("totalInList", 0),
                        "disabledShows": catalog.get("disabledShows", 0),
                        "countsByCategory": catalog.get("countsByCategory", {}),
                    },
                )
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if route == "/api/sync-livechart":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 0:
                    raw_body = self.rfile.read(length).decode("utf-8")
                    payload = json.loads(raw_body) if raw_body.strip() else {}
                    if isinstance(payload, dict) and isinstance(payload.get("shows"), list):
                        SOURCE_PATH.parent.mkdir(parents=True, exist_ok=True)
                        SOURCE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

                importlib.reload(manage_shows)
                lc_stats = manage_shows.import_livechart()

                importlib.reload(enrich_catalog)
                catalog = enrich_catalog.enrich_all(force_refresh=False)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "totalShows": catalog.get("totalShows", 0),
                        "totalInList": catalog.get("totalInList", 0),
                        "disabledShows": catalog.get("disabledShows", 0),
                        "countsByCategory": catalog.get("countsByCategory", {}),
                        "livechart": lc_stats,
                    },
                )
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ReusableThreadingHTTPServer(("127.0.0.1", port), RandomFlixLocalHandler)
    print(f"RandomFlix local server running at http://localhost:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
