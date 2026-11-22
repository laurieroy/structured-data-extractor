# Decisions

The major choices I made for this build, and why.

- **Extraction domain:** commercial invoices — it seemed like a more interesting problem to solve. Messy totals, currencies, and odd date formats give the validators real work to do.
- **LLM provider:** Anthropic (Claude). Key via `ANTHROPIC_API_KEY`, model via `EXTRACTOR_MODEL` — I listed both providers in `.env.example` to keep options open.
- **Structured-output method:** `instructor` — I went with it to learn a new process rather than the more familiar structured-outputs route.
- **Reconciliation rule:** `sum(line_total) ≈ subtotal` AND `subtotal + tax_amount ≈ total_amount`, both within 0.02 — the assignment's math was ambiguous, so I picked one clear, checkable rule.
- **Max retries / backoff:** 3 retries with exponential backoff — bounded, so real failures route to the DLQ instead of looping forever.
- **UI:** Streamlit — fastest path to the required upload, toggle, and side-by-side views.
- **Deployment:** Option A, cloud — secrets live in the host's secret manager. Host picked in M6.
- **DLQ sink:** `dlq/failed_extractions.jsonl` — one JSON object per line (timestamp, raw payload, error list, failure flag). Simple to inspect and easy to replay.
- **Extractor model:** `claude-haiku-5-5` default — cheapest, and extraction is its stated use case; bump `EXTRACTOR_MODEL` to `claude-sonnet-5-5` if it struggles on the messy samples.
- **M2 baseline:** generated in-session (devin/swe-2-high) with a fully specified prompt including all AGENTS.md constraints — preferred a clean starting point over a deliberately loose spec.
