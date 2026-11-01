"""Plan validation. Everything the executor runs must pass here first."""
from __future__ import annotations

from datetime import date


class QueryError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


MAX_MONTHS = 24


def _parse_day(value: str) -> date:
    return date.fromisoformat(value)


def validate(plan: dict, metric_codes: set[str]) -> dict:
    code = plan.get("metric")
    if not code:
        raise QueryError("E_NO_METRIC", "没有识别出指标，请换个说法或从候选指标中选择")
    if code not in metric_codes:
        raise QueryError("E_NO_METRIC", f"指标未定义：{code}")

    try:
        date_from = _parse_day(plan["from"])
        date_to = _parse_day(plan["to"])
    except (KeyError, ValueError):
        raise QueryError("E_BAD_PERIOD", "时间范围无法解析")

    if date_from > date_to:
        raise QueryError("E_BAD_PERIOD", "开始时间晚于结束时间")

    months = (date_to.year - date_from.year) * 12 + (date_to.month - date_from.month) + 1
    if months > MAX_MONTHS:
        raise QueryError("E_BAD_PERIOD", f"时间跨度 {months} 个月，超过 {MAX_MONTHS} 个月上限")

    return {**plan, "months": months}
