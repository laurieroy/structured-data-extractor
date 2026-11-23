import json
import time
from datetime import UTC, datetime
from pathlib import Path

from json_repair import repair_json
from pydantic import ValidationError

from src.normalize import normalize_invoice_data
from src.schemas import ExtractionResult, InvoiceExtraction

DLQ_PATH = Path("dlq/failed_extractions.jsonl")

REFLECTION_PROMPT = """You are repairing an invoice extraction that failed validation.
Fix ONLY the fields named by the errors. Return ONLY a JSON object matching
this JSON schema:
{schema}

Relevant source snippet:
{snippet}

Previous malformed JSON:
{last_raw}

Validation errors (loc -> msg):
{errors}"""


def _context_snippet(raw_text: str, errors: list, window: int = 400) -> str:
    fields = {str(loc) for err in errors for loc in err.get("loc", ())}
    positions = [
        pos
        for pos in (raw_text.lower().find(f.lower()) for f in fields)
        if pos >= 0
    ]
    if not positions:
        return raw_text[:800]
    start = max(min(positions) - window, 0)
    end = min(max(positions) + window, len(raw_text))
    return raw_text[start:end]


def _errors_text(errors: list) -> str:
    return "\n".join(f"- {e.get('loc')}: {e.get('msg')}" for e in errors)


def run_fallback(
    raw_client,
    model,
    raw_text: str,
    *,
    last_raw: str,
    error_log: list[str],
    max_retries: int,
    use_reflection: bool = True,
    prompt_log: list[str] | None = None,
) -> ExtractionResult:
    last_errors: list = []
    attempts_made = 1
    for attempt in range(2, max_retries + 1) if use_reflection else ():
        attempts_made = attempt
        time.sleep(2 ** (attempt - 2))
        errors_text = _errors_text(last_errors) or (
            error_log[-1] if error_log else "no previous errors"
        )
        prompt = REFLECTION_PROMPT.format(
            schema=json.dumps(InvoiceExtraction.model_json_schema()),
            snippet=_context_snippet(raw_text, last_errors),
            last_raw=last_raw,
            errors=errors_text,
        )
        if prompt_log is not None:
            prompt_log.append(prompt)
        try:
            resp = raw_client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            last_raw = "".join(
                getattr(b, "text", "") or "" for b in resp.content
            )
        except Exception as exc:  # noqa: BLE001
            error_log.append(f"attempt {attempt}: API error: {exc}")
            continue
        try:
            invoice = InvoiceExtraction(
                **normalize_invoice_data(json.loads(last_raw))
            )
            return ExtractionResult(
                validated_data=invoice,
                attempts_used=attempt,
                error_log=error_log,
                execution_status="REPAIRED_VIA_REFLECTION",
            )
        except json.JSONDecodeError as exc:
            error_log.append(f"attempt {attempt}: malformed JSON: {exc}")
        except ValidationError as exc:
            last_errors = exc.errors()
            error_log.append(f"attempt {attempt}: {_errors_text(last_errors)}")
        except ValueError as exc:
            error_log.append(f"attempt {attempt}: normalization failed: {exc}")

    try:
        repaired = repair_json(last_raw)
        data = json.loads(repaired) if isinstance(repaired, str) else repaired
        invoice = InvoiceExtraction(**normalize_invoice_data(data))
        return ExtractionResult(
            validated_data=invoice,
            attempts_used=attempts_made,
            error_log=error_log,
            execution_status="REPAIRED_VIA_REFLECTION",
        )
    except Exception as exc:  # noqa: BLE001
        error_log.append(f"json_repair stage: {exc}")

    return dlq_result(raw_text, last_raw, error_log, attempts_used=attempts_made)


def dlq_result(
    raw_text: str, last_raw: str, error_log: list[str], attempts_used: int
) -> ExtractionResult:
    _write_dlq(raw_text, last_raw, error_log)
    return ExtractionResult(
        validated_data=None,
        attempts_used=attempts_used,
        error_log=error_log,
        execution_status="DLQ_FAILED",
    )


def _write_dlq(raw_text: str, last_raw: str, error_log: list[str]) -> None:
    try:
        DLQ_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "raw_payload": last_raw,
            "source_excerpt": raw_text[:500],
            "errors": list(error_log),
            "failed": True,
        }
        with DLQ_PATH.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError as exc:
        error_log.append(f"DLQ write failed: {exc}")
