"""Question -> plan (metric + period).

Two modes:
  * rule: keyword matching, always available, used as the fallback
  * llm:  DeepSeek JSON output, used when DEEPSEEK_API_KEY is set

Both return the same plan shape, so the executor never knows which one ran.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import date

# Longer, more specific keywords first: 回款率 must win over 回款.
METRIC_KEYWORDS: list[tuple[str, list[str]]] = [
    ("collection_rate", ["回款率", "回款比例", "回款占比", "收款率", "比例"]),
    ("overdue_receivable", ["逾期应收", "逾期账款", "逾期金额", "逾期", "超期"]),
    ("collection_amount", ["回款额", "回款金额", "收款额", "收款金额", "回款", "收款", "收到", "收了"]),
    ("order_count", ["订单数", "订单量", "单量", "多少单", "几单", "成交单"]),
    ("sales_amount", ["销售额", "销售金额", "营收", "收入", "业绩", "卖了"]),
]


class ParseError(ValueError):
    pass


def _month_range(year: int, month: int) -> tuple[str, str]:
    first = date(year, month, 1)
    last = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return first.isoformat(), date.fromordinal(last.toordinal() - 1).isoformat()


def parse_period(text: str, today: date) -> tuple[str, str]:
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月", text)
    if m:
        return _month_range(int(m.group(1)), int(m.group(2)))

    m = re.search(r"(\d{4})-(\d{1,2})(?!\d)", text)
    if m:
        return _month_range(int(m.group(1)), int(m.group(2)))

    if "上月" in text or "上个月" in text:
        year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        return _month_range(year, month)

    if "去年" in text:
        return f"{today.year - 1}-01-01", f"{today.year - 1}-12-31"

    if "今年" in text or "本年" in text:
        return f"{today.year}-01-01", today.isoformat()

    m = re.search(r"(?<!\d)(\d{1,2})\s*月", text)
    if m:
        month = int(m.group(1))
        year = today.year if month <= today.month else today.year - 1
        return _month_range(year, month)

    return _month_range(today.year, today.month)


def match_metric(text: str) -> str | None:
    best: tuple[int, str] | None = None
    for code, keywords in METRIC_KEYWORDS:
        for kw in keywords:
            if kw in text:
                if best is None or len(kw) > best[0]:
                    best = (len(kw), code)
    return best[1] if best else None


def parse(question: str, today: date | None = None) -> dict:
    today = today or date.today()
    text = question.strip()
    if not text:
        raise ParseError("问题为空")

    metric = match_metric(text)
    date_from, date_to = parse_period(text, today)
    return {
        "metric": metric,
        "from": date_from,
        "to": date_to,
        "filters": {},
        "source": "rule",
    }


LLM_SYSTEM = (
    "你是 ERP 指标解析器。只输出 JSON，不要解释。"
    '字段：{"metric": "<指标代码或 null>", "from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}。'
    "只能从给定指标代码中选择，不确定时 metric 输出 null。"
)


def parse_with_llm(question: str, metric_codes: list[str], today: date, timeout: float = 15.0) -> dict | None:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return None
    payload = {
        "model": "deepseek-flash",
        "messages": [
            {"role": "system", "content": LLM_SYSTEM + "可用代码：" + ", ".join(metric_codes)},
            {"role": "user", "content": f"今天是 {today.isoformat()}。问题：{question}"},
        ],
        "temperature": 0,
        "max_tokens": 200,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
        plan = json.loads(body["choices"][0]["message"]["content"])
    except Exception:
        return None
    if not isinstance(plan, dict) or plan.get("metric") not in metric_codes:
        return None
    return {
        "metric": plan["metric"],
        "from": plan.get("from", ""),
        "to": plan.get("to", ""),
        "filters": {},
        "source": "llm",
    }
