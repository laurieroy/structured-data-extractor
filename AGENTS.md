# structured-data-extractor

Three-stage fault-tolerant pipeline: messy PDF/HTML (e.g. invoices) → constrained LLM
decoding into strict Pydantic v2 records → validation gate → bounded reflection loop with
targeted errors → `json_repair` heuristic → dead-letter queue (DLQ). Streamlit UI.
Spec in `docs/week4_assignment.md`, milestone plan in `docs/week4_work_plan.md`.
Work one milestone at a time: finish the code, give the user the exact test and commit
commands, then stop and wait.

## Stack
Python 3.11, uv, Pydantic v2, LLM provider + structured-output method (see Decisions),
`instructor`, `pypdf`, `beautifulsoup4`, `json-repair`, `python-dotenv`, Streamlit,
pytest, pytest-asyncio.

## Decisions (fill in before M0)
- LLM provider / model: `________` (read from env, e.g. `OPENAI_API_KEY`, `OPENAI_MODEL`)
- Structured-output method: `________` (OpenAI Structured Outputs, Anthropic tool use, or `instructor`)
- Extraction domain: `________` (default: commercial invoices)
- Reconciliation rule: `________` (suggested: `sum(line_total) ≈ subtotal` AND
  `subtotal + tax_amount ≈ total_amount`, both within 0.02 — pick one clear rule and document it)
- Max retries / backoff: `________` (default: 3 retries, exponential backoff)
- UI: `Streamlit` (assignment also allows FastAPI + HTML or Chainlit)
- Deployment: Option A (cloud: Streamlit Community Cloud / Render / Railway / HF Spaces)
  or Option B (`Dockerfile` + `docker-compose.yml`)
- DLQ sink: `dlq/failed_extractions.jsonl` (one JSON object per line: timestamp, raw
  payload, error list, failure flag)

## Commands
- Install: `uv sync`
- Test: `uv run pytest -v`
- UI: `uv run streamlit run src/app.py`

## Models
- Extraction model is set via `EXTRACTOR_MODEL` in `.env` (placeholder in
  `.env.example`); never hard-code a model name in source.
- Model per milestone: M2 baseline generation → Sonnet 5.5; M3 audit →
  Opus 5.5; M7 README → Haiku. Record the model actually used in each
  `ai_prompt_log.md` entry.
- Audit sessions are review-only: report findings, do not modify code.

## Rules
- NEVER read, edit, print, or search `.env` files (or any real secrets), including via
  shell commands like `cat`, `grep`, `head`. Only `.env.example` may be edited, with
  placeholder values.
- Pydantic v2 only: `@field_validator`, `@model_validator(mode="after")`, `.model_dump()`.
  Never `@validator`, never `.dict()`. Verify: `grep -rn "@validator\|\.dict(" src/` returns nothing.
- Config loader reads secrets from environment variables (`.env` locally via
  `python-dotenv`, host secret manager when deployed).
- `ExtractionResult` shape is fixed: `validated_data: Optional[InvoiceExtraction]`,
  `attempts_used: int`, `error_log: List[str]`,
  `execution_status: "SUCCESS" | "REPAIRED_VIA_REFLECTION" | "DLQ_FAILED"`.
- Reflection re-prompts contain only the relevant context snippet, the previous malformed
  JSON, and exact `err['loc']`/`err['msg']` — never the full document.
- `json_repair` output goes back through Pydantic validation; repair never bypasses the gate.
- Failure path returns `validated_data=None` with a populated `error_log`, writes a DLQ
  entry, never crashes. Never return hollow or all-`None` objects.
- Pre-parse messy values (`"$1,249.50"`, `"12th of Oct, 2024"`) before Pydantic sees them.
- Mock the LLM client in all tests; `pytest` must be deterministic and need no API key.
- Keep solutions simple and minimal. Don't add features or fixes beyond the current milestone.

## Working style
- Manual mode always: check with the user before doing anything. Do only what is
  specifically asked, nothing extra.
- Be concise. Keep answers short and not verbose; don't spend extra tokens on long
  explanations, recaps, or unrequested suggestions.
- No hallucination: if unsure, say so or ask. Never invent APIs, flags, file contents,
  or results.
- Never run git commands (init, add, commit, push, etc.) or uv/test commands (`uv init`,
  `uv sync`, `uv add`, `uv run pytest`, etc.). The user runs them. Give the exact command
  to run instead, then wait for the user to paste the output.
- Before telling the user to commit, recheck every file that will be committed for
  sensitive information (API keys, tokens, passwords, emails, personal data, local paths)
  and report what was found, or that nothing was found.
- Tests first: write tests, confirm they fail, then implement until green.
- One branch per milestone, named `mN-<one word>`: `m1-schemas`, `m2-baseline`,
  `m3-audit`, `m4-resilience`, `m5-ui`, `m6-packaging`, `m7-submission` (no
  branch for m0 — it stays on main). Branch creation is the FIRST step of each
  milestone: give the user `git switch -c mN-<word>` to run before any code
  changes (you never run git yourself). All milestone commits happen on that
  branch; the user merges when done.

## Prompt log
- `ai_prompt_log.md` is a graded deliverable: it must contain the exact generation prompt,
  the raw AI output, the audit findings, and the fixes.
- When a milestone is finished, append an entry to `ai_prompt_log.md` (pre-authorized
  exception to manual mode). Create the file if missing (it already exists, empty).
- Entry format: milestone name, model used, the prompt used, what was generated,
  bugs/issues found, fixes made. Keep it short. "Model used" = the LLM/agent that
  produced the output, as self-reported (e.g. `devin/swe-2-high`,
  `claude-sonnet-4.5`, `gpt-4o`). For generations made outside this session, the
  user supplies the model name.
- The M2 baseline prompt and raw output are captured verbatim and committed
  untouched — no refinement or self-correction.
- Log every real bug as it happens (failing test, wrong output, bad AI suggestion), with
  the commit where it was fixed. This log feeds the M3 audit and the video segment.
- Log only what actually happened. Never invent bugs or results. Write "none found" if so.

## Protecting secrets (agent setup, M0)
Do this first, before any other file is created. Ask the user to confirm, then:
1. Extend `.gitignore` (already covers `__pycache__/`, `.venv/`) to include at least:
   `.env`, `.env.*` (with `!.env.example`), `.pytest_cache/`, `dlq/`,
   `.streamlit/secrets.toml`, `.devin/config.local.json`.
2. Create `.devin/config.json` denying read/write/shell access to real env files and
   secrets (deny rules always win and can't exempt `.env.example`, so variants are
   listed by name):
```json
{
  "permissions": {
    "deny": [
      "Read(.env)",
      "Read(.env.local)",
      "Read(.env.development)",
      "Read(.env.production)",
      "Read(.env.test)",
      "Read(.env.*.local)",
      "Read(.streamlit/secrets.toml)",
      "Write(.env)",
      "Write(.env.local)",
      "Write(.env.development)",
      "Write(.env.production)",
      "Write(.env.test)",
      "Write(.env.*.local)",
      "Write(.streamlit/secrets.toml)",
      "Exec(cat .env)",
      "Exec(cat .env.local)",
      "Exec(cat .streamlit/secrets.toml)"
    ]
  }
}
```
   Note: `Exec` rules are command-prefix matched and only cover the obvious `cat`
   invocations — the `Read`/`Write` denies are the real guard. Devin's Smart mode also
   never auto-approves reads/writes of dotenv files, key material, or agent config.
3. Only `.env.example` (placeholders only, e.g. `OPENAI_API_KEY=your-key-here`, or
   `ANTHROPIC_API_KEY` per the provider decision) may be created or edited.
4. Tell the user to verify with `git status` that `.env` is not tracked before the
   first commit.

## Tests
Confirm names and exact criteria against `docs/week4_assignment.md` §5 before writing.
All LLM calls are mocked. NOTE: repo stubs are currently named
`test_schemas.py`/`test_extractor.py`/`test_fallback.py`/`test_app.py`; align to the
assignment's `test_extraction.py` + `test_fallbacks.py` when writing them.
- Test 1 (M1 as schema-level golden; pipeline attempt-1 check in M4): golden
  document validates; pipeline version asserts Attempt 1 with zero validation errors.
- Test 2 (M1): schema constraints — quantity ≤ 0 or negative totals raise
  validation errors.
- Test 3 (M1): cross-field reconciliation — line items not matching `total_amount`
  per the chosen rule fail validation.
- Test 4 (M4): reflection success — mocked malformed response (missing currency /
  bad date) self-heals on Attempt 2 → `REPAIRED_VIA_REFLECTION`.
- Test 5 (M4): DLQ routing — nonsense input → `DLQ_FAILED` after max retries, DLQ
  entry written to disk, no exception raised.
- Extra (M4, not graded): reflection re-prompt does not contain the full document;
  `json_repair` output is re-validated.

## Milestones
Each milestone ends with: test command for the user (where relevant), prompt log entry,
sensitive-info recheck, commit command, stop. Aligned to M0–M7 in
`docs/week4_work_plan.md`.

- **M0 — Setup and decisions**: secrets setup above (`.gitignore`, `.devin/config.json`,
  `.env.example`); deps already in `pyproject.toml`, Python 3.11 pinned,
  `src/`/`tests/`/`samples/` layout exists. Remaining: give the user `uv sync`; verify a
  "hello world" LLM call; user creates real `samples/invoice_messy.pdf` (with odd
  formats like `$1,249.50` and "12th of Oct, 2024") and `samples/vendor_contract.html`
  (current files are empty placeholders).
- **M1 — Data contract (schemas + tests 1–3)**: `tests/test_extraction.py` (Tests 1–3)
  first, then `src/schemas.py` — `LineItem` nested in `InvoiceExtraction`; field
  validators for ISO-8601 dates, positive quantities, clean tax, regex invoice number,
  currency `Literal["USD","EUR","GBP"]`; `@model_validator(mode="after")` implementing
  the chosen reconciliation rule within 0.02; pre-parsers for messy values.
- **M2 — Baseline AI draft (captured untouched)**: run the assignment's sample prompt to
  generate `extractor.py` + `fallback.py` incl. `extract_with_retry(raw_text,
  max_retries=3) -> ExtractionResult`. No refinement. Log prompt + raw output verbatim;
  user commits separately as `baseline: unmodified AI output`; get Stage 1 running on
  the golden PDF just enough to note failures.
- **M3 — Audit and refactor**: fresh-session reviewer pass over the four anti-patterns —
  Pydantic v1/v2 collisions, context stuffing, silent error swallowing, date/type
  coercion fragility — plus anything else found (hard-coded keys, unbounded retries, no
  timeouts). Verify each finding is real; each fix is its own commit; minimum 2 real
  fixes, aim for 4.
- **M4 — Resilience (reflection, repair, DLQ)**: `ExtractionResult`; reflection loop
  (snippet-only re-prompt with `err['loc']`/`err['msg']`, bounded retries + backoff);
  `json_repair` attempt + re-validation; JSONL DLQ writer; reflection on/off switch;
  simulated-failure hook. `tests/test_fallbacks.py` (Tests 4–5) written first with a
  mocked client.
- **M5 — Web UI**: `src/app.py` (Streamlit) — upload PDF or paste HTML/text; reflection
  toggle; side-by-side raw doc vs validated JSON; reconciliation badge (match/mismatch
  + difference); audit-log panel (attempts, raw validation errors, exact corrective
  prompts); "Simulate Edge Case Failure" button → DLQ; clean error display. The full
  demo script must run UI-only.
- **M6 — Packaging and deployment**: `Dockerfile` + `docker-compose.yml` (`docker
  compose up` works; key via env, not baked in) or cloud deploy with host secret
  manager. Verified from a fresh clone.
- **M7 — README, video, submission**: README with Mermaid data-flow diagram (Ingestion
  → Text Extraction → Constrained Decoding → Validation Gate → Pass → UI / Fail →
  Reflection → DLQ), `uv` install guide, schema spec table, execution commands, AI
  audit summary — verify every command. Video 5:00–7:00, webcam visible throughout
  (target ~6:00): ~1:00 architecture/schema (state name), ~1:30 `ai_prompt_log.md`
  audit walkthrough, ~1:30 live extraction in the UI, ~1:30 reflection self-heal then
  DLQ demo, ~0:30 `pytest -v` all green. Upload unlisted/public, test the link logged
  out, fill the submission template, submit via LMS.

## Submission checklist
- [ ] Repo public (or accessible to the grader), no secrets in history
- [ ] `uv run pytest -v` — all 5+ tests pass
- [ ] `ai_prompt_log.md` has exact prompt, raw output, audit with 2+ real bugs + fixes
- [ ] Live URL or `docker compose up` demo works
- [ ] Video 5:00–7:00, webcam visible, all failure simulations + test run shown
- [ ] README has all 5 required sections
- [ ] Submission template submitted via LMS
- [ ] Due Oct 25, 2026, 11:59 PM per `week4_assignment.md` (verify actual LMS deadline —
      that date is already past as of writing)
