# structured-data-extractor

A fault-tolerant pipeline that turns messy PDFs and HTML documents (commercial
invoices) into strictly validated Pydantic v2 records using LLM structured
output. When validation fails, the pipeline self-corrects through a bounded
reflection loop, falls back to `json_repair` heuristics, and finally routes
unrecoverable payloads to a dead-letter queue (DLQ). A Streamlit UI provides
upload, side-by-side output, and audit logging.

> **Status: work in progress.** This project is being built milestone by
> milestone per `docs/week4_work_plan.md` (spec in
> `docs/week4_assignment.md`). Only the repository scaffold exists so far —
> the extraction pipeline, UI, and tests are not yet implemented.

## Setup

Requires Python 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # then add your LLM API key to .env
```

`.env` is gitignored; only `.env.example` (with placeholder values) is
committed. Never commit real API keys.

## Project structure

```
structured-data-extractor/
├── pyproject.toml
├── .env.example          # placeholder env vars — copy to .env and fill in
├── .gitignore
├── README.md
├── ai_prompt_log.md      # AI generation prompts, raw output, audit findings
├── docs/
│   ├── week4_assignment.md
│   └── week4_work_plan.md
├── samples/
│   ├── invoice_messy.pdf
│   └── vendor_contract.html
├── src/
│   ├── __init__.py
│   ├── schemas.py        # Pydantic v2 models
│   ├── extractor.py      # extraction + validation engine
│   ├── fallback.py       # reflection re-prompting + heuristic repair
│   └── app.py            # Streamlit UI
└── tests/
    ├── __init__.py
    ├── test_schemas.py
    ├── test_extractor.py
    ├── test_fallback.py
    └── test_app.py
```
