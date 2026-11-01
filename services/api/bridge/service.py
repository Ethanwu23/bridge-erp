"""Query orchestration: parse -> validate -> execute -> explain."""
from __future__ import annotations

import uuid
from datetime import date

from bridge.metrics.engine import compute_metric
from bridge.query.parser import parse, parse_with_llm
from bridge.query.validator import validate


def answer(
    client,
    question: str,
    metrics: list[dict],
    today: date | None = None,
    prefer_llm: bool = False,
) -> dict:
    today = today or date.today()
    codes = [m["code"] for m in metrics]

    plan = parse_with_llm(question, codes, today) if prefer_llm else None
    if plan is None:
        plan = parse(question, today)
    plan = validate(plan, set(codes))

    metric = next(m for m in metrics if m["code"] == plan["metric"])
    result = compute_metric(client, metric, plan["from"], plan["to"], today.isoformat())

    return {
        "trace_id": uuid.uuid4().hex,
        "metric": result["code"],
        "name": result["name"],
        "value": result["value"],
        "unit": result["unit"],
        "period": {"from": plan["from"], "to": plan["to"]},
        "explanation": f"{metric['name']}：{metric['description']}（{plan['from']} ~ {plan['to']}）",
        "details": result["details"],
        "source": plan["source"],
    }
