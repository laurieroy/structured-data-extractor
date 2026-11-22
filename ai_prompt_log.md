# AI Prompt Log

## M1 — Data contract (schemas + tests 1–3)

- **Model used:** devin/swe-2-high (self-reported)
- **Date:** 2026-11-21

### Prompt (verbatim)

```text
You are a Staff AI Systems Engineer. Build the data-contract layer for a
fault-tolerant pipeline that extracts commercial-invoice data from messy
PDFs/HTML into strictly validated Pydantic v2 records.

Produce exactly three files. Do NOT write LLM, extraction, or retry logic —
only the contract, its validators, tests, and two small normalization helpers.

### src/normalize.py
Pre-parsers that convert messy raw strings into clean Python values BEFORE
Pydantic sees them:
- parse_money(value) -> float — accepts "$1,249.50", "1249.50", 1249.5, 1249;
  raises ValueError on anything unparseable
- parse_date(value) -> date — accepts date objects, ISO-8601 strings, and
  non-standard forms like "12th of Oct, 2024"; raises ValueError on
  unparseable input

### src/schemas.py  (Pydantic v2 ONLY)
- LineItem: description: str, quantity: int, unit_price: float,
  line_total: float
- InvoiceExtraction: invoice_number: str, vendor_name: str,
  invoice_date: date, line_items: list[LineItem] (at least one item),
  subtotal: float, tax_amount: float, total_amount: float,
  currency: Literal["USD", "EUR", "GBP"]
- @field_validators enforcing: quantity > 0, unit_price > 0,
  line_total/subtotal/tax_amount/total_amount >= 0, and invoice_number
  matching a documented regex (e.g. ^[A-Za-z0-9-]{3,20}$)
- @model_validator(mode="after") enforcing the reconciliation rule:
  sum(line_total) ≈ subtotal AND subtotal + tax_amount ≈ total_amount,
  each within 0.02 absolute tolerance; on failure raise ValueError naming
  the field and showing the computed difference
- ExtractionResult: validated_data: Optional[InvoiceExtraction],
  attempts_used: int, error_log: list[str],
  execution_status: Literal["SUCCESS", "REPAIRED_VIA_REFLECTION",
  "DLQ_FAILED"]

Hard constraints:
- Pydantic v2 API only: @field_validator, @model_validator(mode="after"),
  .model_dump(). Never @validator, never .dict().
- Failures raise — never return partial or all-None objects.

### tests/test_extraction.py
Deterministic pytest tests; no LLM calls:
1. test_golden_payload_validates — hand-built clean payload validates;
   every LineItem populated; currency in {USD, EUR, GBP}
2. test_schema_rejects_bad_constraints — quantity = 0 and negative
   total_amount each raise ValidationError
3. test_reconciliation_rejects_mismatched_sums — sum(line_total) off from
   subtotal by > 0.02, and subtotal + tax_amount off from total_amount,
   each raise ValidationError
4. test_normalize_parsers — parse_money("$1,249.50") == 1249.50;
   parse_date("12th of Oct, 2024") == date(2024, 10, 12)
```

### What was generated

- `tests/test_extraction.py` — 4 tests (golden payload, constraint rejection, reconciliation rejection, normalize parsers)
- `src/schemas.py` — `LineItem`, `InvoiceExtraction`, `ExtractionResult`
- `src/normalize.py` — `parse_money`, `parse_date`

### Bugs / issues found

None found — generated code passed all 4 tests on first run (`uv run pytest -v`, 4 passed).

### Fixes made

None. Raw output committed as-is on `m1-schemas`. Empty M0 stubs removed
(`tests/test_schemas.py`, `test_extractor.py`, `test_fallback.py`, `test_app.py`).
