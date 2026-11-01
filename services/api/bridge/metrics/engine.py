"""Deterministic metric execution.

The LLM never writes queries: it only picks a metric and fills parameters.
This module turns a metric definition + parameters into API calls and a number.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

PAGE_SIZE = 100


def load_metrics(metrics_dir: Path) -> list[dict]:
    metrics = []
    for path in sorted(Path(metrics_dir).glob("*.json")):
        metrics.append(json.loads(path.read_text(encoding="utf-8")))
    return metrics


def _query_all(client, doctype: str, filters: list, fields: list) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        batch = client.list_resource(doctype, filters, fields, start, PAGE_SIZE)
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def _numeric(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal(0)
    return Decimal(str(value))


def compute_metric(
    client,
    metric: dict,
    date_from: str,
    date_to: str,
    as_of: str,
) -> dict:
    parts: dict[str, Decimal] = {}
    details: dict[str, int] = {}

    for source in metric["sources"]:
        filters = [list(f) for f in source.get("filters", [])]
        if source.get("date_field"):
            filters.append([source["date_field"], ">=", date_from])
            filters.append([source["date_field"], "<=", date_to])
        if source.get("as_of_field"):
            filters.append([source["as_of_field"], "<", as_of])

        fields = ["name", source["value_field"]] if source.get("value_field") else ["name"]
        rows = _query_all(client, source["doctype"], filters, fields)
        details[source["id"]] = len(rows)

        if source.get("op") == "count":
            parts[source["id"]] = Decimal(len(rows))
        else:
            parts[source["id"]] = sum(
                (_numeric(r.get(source["value_field"])) for r in rows), Decimal(0)
            )

    formula = metric["formula"]
    args = [parts[a] for a in formula["args"]]
    if formula["op"] == "sum":
        value = sum(args, Decimal(0))
    elif formula["op"] == "divide":
        value = (args[0] / args[1]) if args[1] else None
    else:
        raise ValueError(f"unsupported formula op {formula['op']}")

    return {
        "code": metric["code"],
        "name": metric["name"],
        "unit": metric["unit"],
        "value": None if value is None else float(value),
        "raw": value,
        "details": details,
    }
