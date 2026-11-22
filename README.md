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

**Stack:** Python 3.11 · uv · Pydantic v2 · Anthropic (Claude) via `instructor`
· `pypdf` · `beautifulsoup4` · `json-repair` · Streamlit · pytest

## Setup

Requires Python 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # then add your ANTHROPIC_API_KEY and set EXTRACTOR_MODEL
```

`.env` is gitignored; only `.env.example` (with placeholder values) is
committed. Never commit real API keys.

The default extractor is `claude-haiku-5-5` (cheapest; extraction is its stated
use case). If it struggles on the messy samples, upgrade `EXTRACTOR_MODEL` to
e.g. `claude-sonnet-5-5`.

## Commands

```bash
uv run pytest -v                    # run the test suite
uv run streamlit run src/app.py     # start the web UI
```

## Project structure

```
structured-data-extractor/
├── pyproject.toml
├── .python-version         # Python 3.11 pin
├── .env.example            # placeholder env vars — copy to .env and fill in
├── .gitignore
├── README.md
├── ai_prompt_log.md        # AI generation prompts, raw output, audit findings
├── .devin/
│   └── skills/web-qa/      # /web-qa project QA checklist (manual trigger)
├── docs/
│   ├── week4_assignment.md # assignment spec
│   ├── week4_work_plan.md  # milestone plan M0–M7
│   └── agent_setup.md      # M0 secrets/permissions setup procedure
├── samples/
│   ├── invoice_messy.pdf
│   └── vendor_contract.html
├── src/
│   ├── __init__.py
│   ├── schemas.py          # Pydantic v2 models
│   ├── extractor.py        # extraction + validation engine
│   ├── fallback.py         # reflection re-prompting + heuristic repair
│   └── app.py              # Streamlit UI
└── tests/
    ├── __init__.py
    ├── test_extraction.py  # Tests 1–3: schema + golden extraction
    └── test_fallbacks.py   # Tests 4–5: reflection + DLQ
```
