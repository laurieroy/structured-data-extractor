import json
from datetime import date
from unittest.mock import Mock

import pytest

from src.fallback import run_fallback

VALID_PAYLOAD = {
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
    ],
    "subtotal": 4800.00,
    "tax_amount": 384.00,
    "total_amount": 5184.00,
    "currency": "USD",
}


MESSY_PAYLOAD = {
    "invoice_number": "INV-2024-0847",
    "vendor_name": "Northwind Consulting LLC",
    "invoice_date": "12th of Oct, 2024",
    "line_items": [
        {
            "description": "Consulting services",
            "quantity": 10,
            "unit_price": "$1,249.50",
            "line_total": "USD 12,495.00",
        },
    ],
    "subtotal": "$12,495.00",
    "tax_amount": "999.60",
    "total_amount": "$13,494.60",
    "currency": "USD",
}


def _response(text):
    resp = Mock()
    resp.content = [Mock(text=text)]
    return resp


def _run_fallback(raw_client, error_log=None):
    return run_fallback(
        raw_client,
        Mock(),
        "test-model",
        "INVOICE\nVendor: Northwind Consulting LLC\nTotal due: $5,184.00",
        last_raw='{"invoice_number": "INV-2024-0847"',
        error_log=error_log if error_log is not None else ["attempt 1: boom"],
        max_retries=3,
    )


def test_api_error_in_retry_loop_returns_dlq_failed(monkeypatch, tmp_path):
    monkeypatch.setattr("src.fallback.time.sleep", lambda *_: None)
    dlq_file = tmp_path / "dlq" / "failed_extractions.jsonl"
    monkeypatch.setattr("src.fallback.DLQ_PATH", dlq_file)

    raw_client = Mock()
    raw_client.messages.create.side_effect = RuntimeError("connection lost")

    result = _run_fallback(raw_client)

    assert result.execution_status == "DLQ_FAILED"
    assert result.validated_data is None
    assert any("connection lost" in e for e in result.error_log)
    entry = json.loads(dlq_file.read_text().strip().splitlines()[-1])
    assert entry["failed"] is True


def test_transient_api_error_then_success_repairs(monkeypatch, tmp_path):
    monkeypatch.setattr("src.fallback.time.sleep", lambda *_: None)
    monkeypatch.setattr(
        "src.fallback.DLQ_PATH", tmp_path / "dlq" / "failed_extractions.jsonl"
    )

    raw_client = Mock()
    raw_client.messages.create.side_effect = [
        RuntimeError("connection lost"),
        _response(json.dumps(VALID_PAYLOAD)),
    ]

    result = _run_fallback(raw_client)

    assert result.execution_status == "REPAIRED_VIA_REFLECTION"
    assert result.validated_data is not None
    assert result.validated_data.invoice_number == "INV-2024-0847"
    assert result.attempts_used == 3
    assert any("connection lost" in e for e in result.error_log)


def test_reflection_normalizes_messy_values(monkeypatch, tmp_path):
    monkeypatch.setattr("src.fallback.time.sleep", lambda *_: None)
    monkeypatch.setattr(
        "src.fallback.DLQ_PATH", tmp_path / "dlq" / "failed_extractions.jsonl"
    )

    raw_client = Mock()
    raw_client.messages.create.return_value = _response(
        json.dumps(MESSY_PAYLOAD)
    )

    result = _run_fallback(raw_client)

    assert result.execution_status == "REPAIRED_VIA_REFLECTION"
    assert result.validated_data is not None
    assert result.validated_data.invoice_date == date(2024, 10, 12)
    assert result.validated_data.line_items[0].unit_price == pytest.approx(
        1249.50
    )
    assert result.validated_data.subtotal == pytest.approx(12495.00)
    assert result.attempts_used == 2


def test_json_repair_normalizes_messy_values(monkeypatch, tmp_path):
    monkeypatch.setattr("src.fallback.time.sleep", lambda *_: None)
    monkeypatch.setattr(
        "src.fallback.DLQ_PATH", tmp_path / "dlq" / "failed_extractions.jsonl"
    )

    fenced = "```json\n" + json.dumps(MESSY_PAYLOAD) + "\n```"
    raw_client = Mock()
    raw_client.messages.create.return_value = _response(fenced)

    result = _run_fallback(raw_client)

    assert result.execution_status == "REPAIRED_VIA_REFLECTION"
    assert result.validated_data is not None
    assert result.validated_data.invoice_date == date(2024, 10, 12)
    assert result.validated_data.total_amount == pytest.approx(13494.60)
