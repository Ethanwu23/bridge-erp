"""Parser tests: metric matching and period extraction."""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from bridge.query.parser import parse  # noqa: E402

TODAY = date(2026, 11, 1)

CASES = [
    ("本月销售额", "sales_amount", "2026-11-01", "2026-11-30"),
    ("上月回款率", "collection_rate", "2026-10-01", "2026-10-31"),
    ("2026年10月订单数", "order_count", "2026-10-01", "2026-10-31"),
    ("9月的逾期应收", "overdue_receivable", "2026-09-01", "2026-09-30"),
    ("今年回款额", "collection_amount", "2026-01-01", "2026-11-01"),
    ("去年销售额", "sales_amount", "2025-01-01", "2025-12-31"),
    ("2026-10 回款", "collection_amount", "2026-10-01", "2026-10-31"),
]


def test_cases():
    for question, metric, date_from, date_to in CASES:
        plan = parse(question, TODAY)
        assert plan["metric"] == metric, f"{question}: metric={plan['metric']}"
        assert plan["from"] == date_from, f"{question}: from={plan['from']}"
        assert plan["to"] == date_to, f"{question}: to={plan['to']}"
        print(f"ok  {question:<18} {metric:<20} {date_from} ~ {date_to}")


def test_rate_wins_over_amount():
    assert parse("本月回款率", TODAY)["metric"] == "collection_rate"
    assert parse("本月回款", TODAY)["metric"] == "collection_amount"
    print("ok  回款率 / 回款 区分正确")


def test_unknown_returns_none():
    assert parse("今天天气怎么样", TODAY)["metric"] is None
    print("ok  无关键词时返回 None（由校验层拒答）")


if __name__ == "__main__":
    test_cases()
    test_rate_wins_over_amount()
    test_unknown_returns_none()
    print("all parser tests passed")
