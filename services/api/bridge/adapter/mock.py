"""In-memory ERP fake used by D1 checks and tests.

Mirrors the subset of ERPNext list semantics the metrics rely on:
equality / comparison filters and paging.
"""
from __future__ import annotations

from typing import Iterable

DOCS: dict[str, list[dict]] = {
    "Sales Invoice": [
        # name, customer, posting_date, due_date, amount, paid, return flag
        {"name": "INV-001", "customer": "C1", "posting_date": "2026-10-05", "due_date": "2026-11-04", "base_grand_total": 100000, "base_outstanding_amount": 0, "is_return": 0, "docstatus": 1},
        {"name": "INV-002", "customer": "C1", "posting_date": "2026-10-12", "due_date": "2026-11-11", "base_grand_total": 50000, "base_outstanding_amount": 50000, "is_return": 0, "docstatus": 1},
        {"name": "INV-003", "customer": "C2", "posting_date": "2026-10-08", "due_date": "2026-10-20", "base_grand_total": 80000, "base_outstanding_amount": 50000, "is_return": 0, "docstatus": 1},
        {"name": "INV-004", "customer": "C2", "posting_date": "2026-10-25", "due_date": "2026-11-24", "base_grand_total": 20000, "base_outstanding_amount": 0, "is_return": 0, "docstatus": 1},
        {"name": "INV-005", "customer": "C3", "posting_date": "2026-10-30", "due_date": "2026-11-29", "base_grand_total": 30000, "base_outstanding_amount": 30000, "is_return": 0, "docstatus": 1},
        {"name": "INV-006", "customer": "C3", "posting_date": "2026-09-20", "due_date": "2026-10-19", "base_grand_total": 40000, "base_outstanding_amount": 30000, "is_return": 0, "docstatus": 1},
        {"name": "CN-001", "customer": "C1", "posting_date": "2026-10-28", "due_date": None, "base_grand_total": -5000, "base_outstanding_amount": 0, "is_return": 1, "docstatus": 1},
    ],
    "Payment Entry": [
        {"name": "PE-001", "party": "C1", "posting_date": "2026-10-06", "base_paid_amount": 100000, "payment_type": "Receive", "docstatus": 1},
        {"name": "PE-002", "party": "C2", "posting_date": "2026-10-16", "base_paid_amount": 30000, "payment_type": "Receive", "docstatus": 1},
        {"name": "PE-003", "party": "C2", "posting_date": "2026-10-27", "base_paid_amount": 20000, "payment_type": "Receive", "docstatus": 1},
        {"name": "PE-004", "party": "C3", "posting_date": "2026-10-31", "base_paid_amount": 10000, "payment_type": "Receive", "docstatus": 1},
    ],
    "Sales Order": [
        {"name": f"SO-00{i}", "customer": c, "transaction_date": d, "docstatus": 1}
        for i, (c, d) in enumerate(
            [
                ("C1", "2026-10-03"),
                ("C1", "2026-10-11"),
                ("C2", "2026-10-15"),
                ("C2", "2026-10-22"),
                ("C3", "2026-10-29"),
            ],
            start=1,
        )
    ],
}

OPS = {
    "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
}


class MockERPClient:
    def __init__(self, docs: dict[str, list[dict]] | None = None):
        self.docs = docs or DOCS

    def ping(self) -> bool:
        return True

    def list_resource(self, doctype, filters=(), fields=("name",), limit_start=0, limit_page_length=100):
        rows = [d for d in self.docs.get(doctype, []) if self._match(d, filters)]
        return [dict(r) for r in rows[limit_start : limit_start + limit_page_length]]

    @staticmethod
    def _match(doc: dict, filters: Iterable[list]) -> bool:
        for field, op, value in filters:
            actual = doc.get(field)
            if actual is None:
                return False
            if op not in OPS:
                raise ValueError(f"unsupported operator {op}")
            try:
                if not OPS[op](actual, value):
                    return False
            except TypeError:
                return False
        return True
