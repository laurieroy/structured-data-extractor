import json
import time
from datetime import datetime, timezone
from pathlib import Path

from json_repair import repair_json
from pydantic import ValidationError

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
    client,
    model,
    raw_text: str,
    *,
    last_raw: str,
    error_log: list[str],
    max_retries: int,
) -> ExtractionResult:
    last_errors: list = []
    for attempt in range(2, max_retries + 1):
        time.sleep(2 ** (attempt - 2))
        errors_text = _errors_text(last_errors) or error_log[-1]
        prompt = REFLECTION_PROMPT.format(
            schema=json.dumps(InvoiceExtraction.model_json_schema()),
            snippet=_context_snippet(raw_text, last_errors),
            last_raw=last_raw,
            errors=errors_text,
        )
        try:
            resp = raw_client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            last_raw = resp.content[0].text
        except Exception as exc:
            error_log.append(f"attempt {attempt}: API error: {exc}")
            continue
        try:
            invoice = InvoiceExtraction(**json.loads(last_raw))
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

    repaired = repair_json(last_raw)
    try:
        data = json.loads(repaired) if isinstance(repaired, str) else repaired
        invoice = InvoiceExtraction(**data)
        return ExtractionResult(
            validated_data=invoice,
            attempts_used=max_retries,
            error_log=error_log,
            execution_status="REPAIRED_VIA_REFLECTION",
        )
    except (ValidationError, json.JSONDecodeError, TypeError) as exc:
        error_log.append(f"json_repair stage: {exc}")

    _write_dlq(raw_text, last_raw, error_log)
    return ExtractionResult(
        validated_data=None,
        attempts_used=max_retries,
        error_log=error_log,
        execution_status="DLQ_FAILED",
    )


def _write_dlq(raw_text: str, last_raw: str, error_log: list[str]) -> None:
    DLQ_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw_payload": last_raw,
        "source_excerpt": raw_text[:500],
        "errors": list(error_log),
        "failed": True,
    }
    with DLQ_PATH.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
