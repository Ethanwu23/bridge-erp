"""Adapter tests: HTTP client contract + pagination in the metric engine."""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from bridge.adapter.http_client import HttpERPClient  # noqa: E402
from bridge.adapter.mock import MockERPClient  # noqa: E402
from bridge.metrics.engine import _query_all  # noqa: E402

SEEN = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        SEEN["auth"] = self.headers.get("Authorization")
        SEEN["path"] = parsed.path
        SEEN["query"] = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        body = json.dumps({"message": "pong"}).encode() if parsed.path.endswith("/ping") else json.dumps(
            {"data": [{"name": "INV-001", "base_grand_total": 100}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_http_client_sends_token_and_filters():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    client = HttpERPClient(base, "key123", "secret456")
    assert client.ping() is True
    assert SEEN["auth"] == "token key123:secret456"

    rows = client.list_resource(
        "Sales Invoice",
        [["docstatus", "=", 1], ["posting_date", ">=", "2026-10-01"]],
        ["name", "base_grand_total"],
        0,
        100,
    )
    assert rows[0]["name"] == "INV-001"
    assert SEEN["path"] == "/api/resource/Sales%20Invoice"
    assert json.loads(SEEN["query"]["filters"])[0] == ["docstatus", "=", 1]
    assert json.loads(SEEN["query"]["fields"]) == ["name", "base_grand_total"]
    assert SEEN["query"]["limit_page_length"] == "100"

    server.shutdown()
    print("ok  http client: token header / url encoding / filters")


def test_pagination_collects_all_pages():
    docs = {"Sales Invoice": [{"name": f"INV-{i:04d}", "docstatus": 1} for i in range(250)]}
    rows = _query_all(MockERPClient(docs), "Sales Invoice", [["docstatus", "=", 1]], ["name"])
    assert len(rows) == 250, len(rows)
    print("ok  pagination: 250 rows over 3 pages")


if __name__ == "__main__":
    test_http_client_sends_token_and_filters()
    test_pagination_collects_all_pages()
    print("all adapter tests passed")
