# Decisions

The major choices I made for this build, and why.

- **Extraction domain:** commercial invoices — it seemed like a more interesting problem to solve. Messy totals, currencies, and odd date formats give the validators real work to do.
- **LLM provider:** Anthropic (Claude). Key via `ANTHROPIC_API_KEY`, model via `EXTRACTOR_MODEL` — env-configured, never hard-coded.
- **Structured-output method:** `instructor` — chose it to learn the library; it also wraps tool-schema generation and validation retries in one provider-agnostic call instead of hand-rolling Anthropic tool use.
- **Reconciliation rule:** `sum(line_total) ≈ subtotal` AND `subtotal + tax_amount ≈ total_amount`, both within 0.02 — the assignment's math was ambiguous, so I picked one clear, checkable rule.
- **Max retries / backoff:** 3 retries with exponential backoff — bounded, so real failures route to the DLQ instead of looping forever.
- **UI:** Streamlit — fastest path to the required upload, toggle, and side-by-side views.
- **Deployment:** local Docker — switched from the cloud plan in M6. A `Dockerfile` + `docker-compose.yml` runs it from a clean clone with no hosted secrets, and keeps a public app from spending my API key on strangers' uploads.
- **DLQ sink:** `dlq/failed_extractions.jsonl` — one JSON object per line (timestamp, raw payload, error list, failure flag). Simple to inspect; the format is replay-friendly for later.
- **Extractor model:** `claude-haiku-5-5` in `.env.example` — cheapest, and extraction is its stated use case; bump to `claude-sonnet-5-5` if it struggles on the messy samples.
- **M2 baseline:** generated in-session (devin/swe-2-high) with a fully specified prompt including all AGENTS.md constraints — preferred a clean starting point over a deliberately loose spec.
- **Dependencies:** runtime list trimmed to what's actually imported — dropped `fastapi`/`uvicorn`/`openai`, moved `pytest` to a dev group. Keeps the dep list honest.
