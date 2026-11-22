from datetime import date

import pytest
from pydantic import ValidationError

from src.normalize import parse_date, parse_money
from src.schemas import InvoiceExtraction

GOLDEN_PAYLOAD = {
    "invoice_number": "INV-2024-0847",
    "vendor_name": "Northwind Consulting LLC",
    "invoice_date": "2024-10-12",
    "line_items": [
        {
            "description": "Cloud hosting & maintenance",
            "quantity": 1,
            "unit_price": 4800.00,
            "line_total": 4800.00,
        },
        {
            "description": "Priority support retainer",
            "quantity": 2,
            "unit_price": 375.25,
            "line_total": 750.50,
        },
        {
            "description": "Consulting services",
            "quantity": 12,
            "unit_price": 124.95,
            "line_total": 1499.40,
        },
    ],
    "subtotal": 7049.90,
    "tax_amount": 563.99,
    "total_amount": 7613.89,
    "currency": "USD",
}


def _payload(**overrides):
    payload = {
        **GOLDEN_PAYLOAD,
        "line_items": [dict(item) for item in GOLDEN_PAYLOAD["line_items"]],
    }
    return {**payload, **overrides}


def test_golden_payload_validates():
    invoice = InvoiceExtraction(**GOLDEN_PAYLOAD)

    assert invoice.invoice_number == "INV-2024-0847"
    assert invoice.currency in ("USD", "EUR", "GBP")
    assert len(invoice.line_items) == 3
    for item in invoice.line_items:
        assert item.description
        assert item.quantity > 0
        assert item.unit_price > 0
        assert item.line_total > 0


def test_schema_rejects_bad_constraints():
    payload = _payload()
    payload["line_items"][0]["quantity"] = 0
    with pytest.raises(ValidationError):
        InvoiceExtraction(**payload)

    with pytest.raises(ValidationError):
        InvoiceExtraction(**_payload(total_amount=-7613.89))


def test_reconciliation_rejects_mismatched_sums():
    # sum(line_total) drifts 0.05 from subtotal — beyond the 0.02 tolerance
    payload = _payload()
    payload["line_items"][0]["line_total"] = 4800.05
    with pytest.raises(ValidationError):
        InvoiceExtraction(**payload)

    # subtotal + tax_amount drifts 1.00 from total_amount
    with pytest.raises(ValidationError):
        InvoiceExtraction(
            **_payload(tax_amount=GOLDEN_PAYLOAD["tax_amount"] + 1.00)
        )


def test_normalize_parsers():
    assert parse_money("$1,249.50") == pytest.approx(1249.50)
    assert parse_money("1249.50") == pytest.approx(1249.50)
    assert parse_money(1249) == pytest.approx(1249.0)

    assert parse_date("2024-10-12") == date(2024, 10, 12)
    assert parse_date("12th of Oct, 2024") == date(2024, 10, 12)
    assert parse_date(date(2024, 10, 12)) == date(2024, 10, 12)

    with pytest.raises(ValueError):
        parse_money("not-a-price")
    with pytest.raises(ValueError):
        parse_date("not a date")
