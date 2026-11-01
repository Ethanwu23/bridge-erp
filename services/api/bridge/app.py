"""HTTP API (FastAPI).

Run locally:
    pip install -r requirements.txt
    uvicorn bridge.app:app --reload --port 8000

Env:
    BRIDGE_MODE       mock | http (default mock)
    ERP_BASE_URL      http://localhost:8080
    ERP_API_KEY       per-user api key
    ERP_API_SECRET    per-user api secret
    DEEPSEEK_API_KEY  optional, enables LLM parsing
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from bridge.adapter.http_client import ERPError, HttpERPClient
from bridge.adapter.mock import MockERPClient
from bridge.metrics.engine import load_metrics
from bridge.query.validator import QueryError
from bridge.service import answer

METRICS_DIR = Path(os.environ.get("BRIDGE_METRICS_DIR", Path(__file__).resolve().parents[3] / "config" / "metrics"))

app = FastAPI(title="数桥 Bridge", version="0.1.0")
_metrics = load_metrics(METRICS_DIR)


def _client():
    mode = os.environ.get("BRIDGE_MODE", "mock").lower()
    if mode == "mock":
        return MockERPClient()
    return HttpERPClient(
        os.environ.get("ERP_BASE_URL", "http://localhost:8080"),
        os.environ.get("ERP_API_KEY", ""),
        os.environ.get("ERP_API_SECRET", ""),
    )


class QueryRequest(BaseModel):
    question: str
    prefer_llm: bool = False


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "mode": os.environ.get("BRIDGE_MODE", "mock"),
        "metrics": len(_metrics),
    }


@app.get("/api/v1/metrics")
def metrics() -> list[dict]:
    return [{"code": m["code"], "name": m["name"], "unit": m["unit"]} for m in _metrics]


@app.post("/api/v1/query")
def query(req: QueryRequest) -> dict:
    try:
        return answer(_client(), req.question, _metrics, date.today(), prefer_llm=req.prefer_llm)
    except QueryError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message})
    except ERPError as exc:
        raise HTTPException(status_code=502, detail={"code": "E_ERP", "message": str(exc)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("bridge.app:app", host="0.0.0.0", port=8000, reload=True)
