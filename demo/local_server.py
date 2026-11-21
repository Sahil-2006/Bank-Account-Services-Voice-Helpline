"""Local browser demo server with SQLite storage for fictional demo IDs only."""
import json
import re
import sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / ".local" / "desk.sqlite3"
HOST = "127.0.0.1"
PORT = 8765
PUBLIC_FILES = {
    "index.html",
    "helpline/__init__.py",
    "helpline/desk.py",
    "helpline/policy.py",
    "helpline/tools.py",
    "helpline/speech.py",
    "helpline/fixtures.json",
    "helpline/uk-bank-holidays-cache.json",
    "evaluation/__init__.py",
    "evaluation/run.py",
    "evaluation/catalog.py",
    "studio/packages/HarbourTrust-V1.zip",
    "studio/packages/HarbourTrust-V2.zip",
    "submission/Capstone10_Report.pdf",
}


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _local_origin(self):
        host = self.headers.get("Host", "").lower()
        if host not in {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin.lower() in {
            f"http://{host}",
            f"http://127.0.0.1:{PORT}",
            f"http://localhost:{PORT}",
        }

    def do_GET(self):
        if not self._local_origin():
            self.send_error(403, "Local demo requests only")
            return
        super().do_GET()

    def do_HEAD(self):
        if not self._local_origin():
            self.send_error(403, "Local demo requests only")
            return
        super().do_HEAD()

    def do_POST(self):
        host = self.headers.get("Host", "").lower()
        origin = self.headers.get("Origin", "").lower()
        if not self._local_origin() or origin != f"http://{host}":
            self.send_error(403, "Local demo requests only")
            return
        if self.path != "/api/demo-account":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 1024:
                self._json(400, {"error": "Invalid request"})
                return
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "Invalid request"})
            return

        customer_id = str(body.get("customerId", "")).strip().upper() if isinstance(body, dict) else ""
        if not re.fullmatch(r"HTD-[A-F0-9]{12}", customer_id):
            self._json(400, {"error": "Invalid demo customer ID"})
            return

        DATABASE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(DATABASE) as connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS demo_account_openings (
                        customer_id TEXT PRIMARY KEY CHECK(length(customer_id)=16 AND substr(customer_id,1,4)='HTD-'),
                        status TEXT NOT NULL CHECK(status='demo_created'),
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                connection.execute(
                    "INSERT OR IGNORE INTO demo_account_openings (customer_id,status) VALUES (?,?)",
                    (customer_id, "demo_created")
                )
            self._json(200, {"saved": True, "storage": "local-sqlite"})
        except sqlite3.Error:
            self._json(500, {"error": "Local demo storage is unavailable"})

    def _json(self, status, value):
        encoded = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def translate_path(self, path):
        """Serve only the demo's public assets, never repository or Git files."""
        requested = urlsplit(path).path
        if requested == "/":
            return str(ROOT)

        candidate = Path(super().translate_path(path)).resolve()
        try:
            relative = candidate.relative_to(ROOT).as_posix()
        except ValueError:
            return str(ROOT / "__not_found__")

        if relative in PUBLIC_FILES or relative.startswith("demo/browser/"):
            return str(candidate)
        return str(ROOT / "__not_found__")

    def list_directory(self, path):
        self.send_error(404, "Not found")
        return None

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    print(f"Harbour Trust local demo: http://{HOST}:{PORT}/")
    print("SQLite stores demo IDs and status only; identity fields are never stored.")
    ThreadingHTTPServer((HOST, PORT), DemoHandler).serve_forever()
