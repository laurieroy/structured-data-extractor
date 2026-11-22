import json
from datetime import date
from unittest.mock import Mock

import httpx2
import pytest
from anthropic import APIConnectionError, AuthenticationError

from src.extractor import extract_with_retry
from src.fallback import run_fallback
from tests.test_extraction import GOLDEN_PAYLOAD

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
        "test-model",
        "INVOICE\nVendor: Northwind Consulting LLC\nTotal due: $5,184.00",
        last_raw='{"invoice_number": "INV-2024-0847"',
        error_log=error_log if error_log is not None else ["attempt 1: boom"],
        max_retries=3,
    )


def _capture_run_fallback(monkeypatch):
    captured = {}

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return "sentinel"

    monkeypatch.setattr("src.extractor.run_fallback", spy)
    return captured


def _request():
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _failing_instructor_client(last_raw=None):
    exc = RuntimeError("stage 1 validation failed")
    if last_raw is not None:
        completion = Mock()
        completion.model_dump_json.return_value = last_raw
        exc.last_completion = completion
    client = Mock()
    client.messages.create.side_effect = exc
    return client


def _clients_pair(instructor_client, raw_client):
    return (instructor_client, raw_client, "test-model")


def _dlq_entry(dlq_file):
    return json.loads(dlq_file.read_text().strip().splitlines()[-1])


def test_api_error_in_retry_loop_returns_dlq_failed(dlq_file):
    raw_client = Mock()
    raw_client.messages.create.side_effect = RuntimeError("connection lost")

    result = _run_fallback(raw_client)

    assert result.execution_status == "DLQ_FAILED"
    assert result.validated_data is None
    assert any("connection lost" in e for e in result.error_log)
    assert _dlq_entry(dlq_file)["failed"] is True


def test_transient_api_error_then_success_repairs():
    raw_client = Mock()
    raw_client.messages.create.side_effect = [
        RuntimeError("connection lost"),
        _response(json.dumps(GOLDEN_PAYLOAD)),
    ]

    result = _run_fallback(raw_client)

    assert result.execution_status == "REPAIRED_VIA_REFLECTION"
    assert result.validated_data is not None
    assert result.validated_data.invoice_number == "INV-2024-0847"
    assert result.attempts_used == 3
    assert any("connection lost" in e for e in result.error_log)


def test_reflection_normalizes_messy_values():
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


def test_json_repair_normalizes_messy_values():
    fenced = "```json\n" + json.dumps(MESSY_PAYLOAD) + "\n```"
    raw_client = Mock()
    raw_client.messages.create.return_value = _response(fenced)

    result = _run_fallback(raw_client)

    assert result.execution_status == "REPAIRED_VIA_REFLECTION"
    assert result.validated_data is not None
    assert result.validated_data.invoice_date == date(2024, 10, 12)
    assert result.validated_data.total_amount == pytest.approx(13494.60)


def test_stage1_failure_passes_raw_completion_to_fallback(monkeypatch):
    completion = Mock()
    completion.model_dump_json.return_value = '{"invoice_number": "BAD"'
    exc = RuntimeError("validation failed")
    exc.last_completion = completion

    client = Mock()
    client.messages.create.side_effect = exc
    monkeypatch.setattr(
        "src.extractor._clients", lambda: (client, Mock(), "test-model")
    )

    captured = _capture_run_fallback(monkeypatch)
    result = extract_with_retry("INVOICE\nTotal due: $5,184.00")

    assert result == "sentinel"
    assert captured["last_raw"] == '{"invoice_number": "BAD"'


def test_stage1_failure_uses_str_exc_when_no_completion(monkeypatch):
    client = Mock()
    client.messages.create.side_effect = RuntimeError("validation failed")
    monkeypatch.setattr(
        "src.extractor._clients", lambda: (client, Mock(), "test-model")
    )

    captured = _capture_run_fallback(monkeypatch)
    extract_with_retry("INVOICE\nTotal due: $5,184.00")

    assert captured["last_raw"] == "validation failed"


def test_stage1_auth_error_goes_straight_to_dlq(monkeypatch, dlq_file):
    client = Mock()
    client.messages.create.side_effect = AuthenticationError(
        message="invalid x-api-key",
        response=httpx2.Response(401, request=_request()),
        body=None,
    )
    monkeypatch.setattr(
        "src.extractor._clients", lambda: (client, Mock(), "test-model")
    )
    captured = _capture_run_fallback(monkeypatch)

    result = extract_with_retry("INVOICE\nTotal due: $5,184.00")

    assert result.execution_status == "DLQ_FAILED"
    assert result.validated_data is None
    assert result.attempts_used == 1
    assert captured == {}
    assert any("non-retryable" in e for e in result.error_log)
    assert _dlq_entry(dlq_file)["failed"] is True


def test_stage1_transient_api_error_enters_fallback(monkeypatch):
    client = Mock()
    client.messages.create.side_effect = APIConnectionError(
        message="connection lost", request=_request()
    )
    monkeypatch.setattr(
        "src.extractor._clients", lambda: (client, Mock(), "test-model")
    )
    captured = _capture_run_fallback(monkeypatch)

    extract_with_retry("INVOICE\nTotal due: $5,184.00")

    assert captured["error_log"][-1].startswith("attempt 1: API error")


def test_reflection_success_self_heals_on_attempt_2(monkeypatch):
    """Test 4: malformed stage-1 output self-heals on attempt 2."""
    malformed = json.dumps({**GOLDEN_PAYLOAD, "currency": "YEN"})
    instructor_client = _failing_instructor_client(last_raw=malformed)
    raw_client = Mock()
    raw_client.messages.create.return_value = _response(
        json.dumps(GOLDEN_PAYLOAD)
    )
    monkeypatch.setattr(
        "src.extractor._clients",
        lambda: _clients_pair(instructor_client, raw_client),
    )

    result = extract_with_retry("INVOICE\nTotal due: $5,184.00")

    assert result.execution_status == "REPAIRED_VIA_REFLECTION"
    assert result.attempts_used == 2
    assert result.validated_data is not None
    assert result.validated_data.currency == "USD"
    raw_client.messages.create.assert_called_once()


def test_dlq_routing_after_max_retries(monkeypatch, dlq_file):
    """Test 5: nonsense input -> DLQ_FAILED after max_retries, no crash."""
    instructor_client = _failing_instructor_client()
    raw_client = Mock()
    raw_client.messages.create.return_value = _response("not json at all")
    monkeypatch.setattr(
        "src.extractor._clients",
        lambda: _clients_pair(instructor_client, raw_client),
    )

    result = extract_with_retry("nonsense gibberish not an invoice")

    assert result.execution_status == "DLQ_FAILED"
    assert result.validated_data is None
    assert result.attempts_used == 3
    assert result.error_log
    assert raw_client.messages.create.call_count == 2
    entry = _dlq_entry(dlq_file)
    assert entry["failed"] is True
    assert entry["errors"]


def test_reflection_disabled_skips_retry_loop(monkeypatch, dlq_file):
    instructor_client = _failing_instructor_client()
    raw_client = Mock()
    monkeypatch.setattr(
        "src.extractor._clients",
        lambda: _clients_pair(instructor_client, raw_client),
    )

    result = extract_with_retry(
        "nonsense gibberish not an invoice", use_reflection=False
    )

    assert result.execution_status == "DLQ_FAILED"
    assert result.attempts_used == 1
    raw_client.messages.create.assert_not_called()
    assert _dlq_entry(dlq_file)["failed"] is True


def test_reflection_disabled_still_uses_json_repair(monkeypatch):
    fenced = "```json\n" + json.dumps(GOLDEN_PAYLOAD) + "\n```"
    instructor_client = _failing_instructor_client(last_raw=fenced)
    raw_client = Mock()
    monkeypatch.setattr(
        "src.extractor._clients",
        lambda: _clients_pair(instructor_client, raw_client),
    )

    result = extract_with_retry(
        "INVOICE\nTotal due: $5,184.00", use_reflection=False
    )

    assert result.execution_status == "REPAIRED_VIA_REFLECTION"
    assert result.attempts_used == 1
    assert result.validated_data is not None
    raw_client.messages.create.assert_not_called()


def test_simulate_failure_routes_to_dlq(monkeypatch, dlq_file):
    clients = Mock()
    monkeypatch.setattr("src.extractor._clients", clients)

    result = extract_with_retry("anything", simulate_failure=True)

    assert result.execution_status == "DLQ_FAILED"
    assert result.validated_data is None
    assert result.attempts_used == 0
    assert result.error_log
    clients.assert_not_called()
    assert _dlq_entry(dlq_file)["failed"] is True


def test_empty_error_log_does_not_crash():
    raw_client = Mock()
    raw_client.messages.create.return_value = _response(
        json.dumps(GOLDEN_PAYLOAD)
    )

    result = _run_fallback(raw_client, error_log=[])

    assert result.execution_status == "REPAIRED_VIA_REFLECTION"
    assert result.validated_data is not None


def test_repair_json_failure_returns_dlq(monkeypatch, dlq_file):
    monkeypatch.setattr(
        "src.fallback.repair_json",
        Mock(side_effect=RuntimeError("repair exploded")),
    )

    raw_client = Mock()
    raw_client.messages.create.return_value = _response("not json at all")

    result = _run_fallback(raw_client)

    assert result.execution_status == "DLQ_FAILED"
    assert result.validated_data is None
    assert any("repair" in e.lower() for e in result.error_log)


def test_dlq_write_failure_still_returns_result(monkeypatch, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    monkeypatch.setattr(
        "src.fallback.DLQ_PATH",
        blocker / "dlq" / "failed_extractions.jsonl",
    )

    raw_client = Mock()
    raw_client.messages.create.return_value = _response("not json at all")

    result = _run_fallback(raw_client)

    assert result.execution_status == "DLQ_FAILED"
    assert result.validated_data is None
    assert any("DLQ" in e for e in result.error_log)
