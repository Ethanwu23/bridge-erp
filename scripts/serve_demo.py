#!/usr/bin/env python3
"""Zero-dependency demo server (stdlib only).

Same contract as the FastAPI app, for machines where pip deps are unavailable
(or for a 30-second smoke test). FastAPI remains the production target.

    python scripts/serve_demo.py --port 8000
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from bridge.adapter.mock import MockERPClient  # noqa: E402
from bridge.metrics.engine import load_metrics  # noqa: E402
from bridge.query.validator import QueryError  # noqa: E402
from bridge.service import answer  # noqa: E402

METRICS = load_metrics(ROOT / "config" / "metrics")
CLIENT = MockERPClient()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self._send(200, {"status": "ok", "mode": "mock", "metrics": len(METRICS)})
        elif self.path == "/api/v1/metrics":
            self._send(200, [{"code": m["code"], "name": m["name"], "unit": m["unit"]} for m in METRICS])
        else:
            self._send(404, {"detail": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/api/v1/query":
            self._send(404, {"detail": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            question = payload.get("question", "")
            result = answer(CLIENT, question, METRICS, date.today(), prefer_llm=False)
            self._send(200, result)
        except QueryError as exc:
            self._send(400, {"detail": {"code": exc.code, "message": exc.message}})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"detail": str(exc)})

    def log_message(self, *args):
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"demo server on http://127.0.0.1:{args.port}")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
