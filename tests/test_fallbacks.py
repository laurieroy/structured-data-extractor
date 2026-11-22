import json
from unittest.mock import Mock

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
