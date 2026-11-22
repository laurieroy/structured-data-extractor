# structured-data-extractor

Three-stage fault-tolerant pipeline: messy PDF/HTML (e.g. invoices) → constrained LLM
decoding into strict Pydantic v2 records → validation gate → bounded reflection loop with
targeted errors → `json_repair` heuristic → dead-letter queue (DLQ). Streamlit UI.
Work one milestone at a time: finish the code, give the user the exact test and commit
commands, then stop and wait.

## References (read on demand, don't duplicate here)
- `docs/week4_assignment.md` — full spec; test names/criteria §4 Step 5, README §8,
  submission template §9
- `docs/week4_work_plan.md` — per-milestone checklists, Definition of Done, demo script,
  rubric cross-check
- `docs/agent_setup.md` — M0 secrets/`.devin/config.json` setup procedure

## Stack
Python 3.11, uv, Pydantic v2, Anthropic via `instructor`, `pypdf`, `beautifulsoup4`,
`json-repair`, `python-dotenv`, Streamlit, pytest, pytest-asyncio.

## Decisions
- LLM provider: Anthropic (Claude). Key via `ANTHROPIC_API_KEY`, model via
  `EXTRACTOR_MODEL` env var — never hard-coded in source.
- Structured-output method: `instructor`
- Extraction domain: commercial invoices
- Reconciliation rule: `sum(line_total) ≈ subtotal` AND
  `subtotal + tax_amount ≈ total_amount`, both within 0.02
- Max retries / backoff: 3 retries, exponential backoff
- UI: `Streamlit`
- Deployment: Option A — cloud (Streamlit Community Cloud / Render / Railway / HF
  Spaces; pick the host in M6), secrets in the host's secret manager
- DLQ sink: `dlq/failed_extractions.jsonl` (one JSON object per line: timestamp, raw
  payload, error list, failure flag)
- `DECISIONS.md` is the running decision log: whenever direction or tradeoffs are
  discussed, ask the user if they'd like to log it; on yes, append one short line
  (decision + why, in the user's voice). Keep it brief.

## Commands
- Install: `uv sync`
- Test: `uv run pytest -v`
- UI: `uv run streamlit run src/app.py`

## Models
- Extraction model is set via `EXTRACTOR_MODEL` in `.env`; never hard-code a model name
  in source.
- Model per milestone: M2 baseline → Sonnet 5.5; M3 audit → Opus 5.5; M7 README → Haiku.
  Record the model actually used in each `ai_prompt_log.md` entry.
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
- Test files per assignment §4 Step 5: `test_extraction.py` (Tests 1–3) + `test_fallbacks.py`
  (Tests 4–5). Older stubs (`test_schemas.py`/`test_extractor.py`/`test_fallback.py`/
  `test_app.py`) get renamed or removed, not kept alongside.
- Keep solutions simple and minimal. Don't add features or fixes beyond the current milestone.

## Working style
- Manual mode always: check with the user before doing anything. Do only what is
  specifically asked, nothing extra.
- Be concise. Short answers; no long explanations, recaps, or unrequested suggestions.
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
  changes. All milestone commits happen on that branch; the user merges when done.
- QA gate before merge: user merges only after `uv run pytest -v` is green (user runs
  it), plus `/web-qa <url>` (`.devin/skills/web-qa/SKILL.md`) against the running app
  once the UI exists (M5 onward). The agent runs /web-qa; the user runs tests and
  starts the app.
- Each milestone ends with: test command for the user (where relevant), prompt log
  entry, sensitive-info recheck, commit command, stop.

## Prompt log
- `ai_prompt_log.md` is a graded deliverable: exact generation prompt, raw AI output,
  audit findings, fixes.
- When a milestone is finished, append an entry to `ai_prompt_log.md` (pre-authorized
  exception to manual mode). Create the file if missing.
- Entry format: milestone name, model used, the prompt used, what was generated,
  bugs/issues found, fixes made. Keep it short. "Model used" = the LLM/agent that
  produced the output, as self-reported (e.g. `devin/swe-2-high`). For generations made
  outside this session, the user supplies the model name.
- The M2 baseline prompt and raw output are captured verbatim and committed
  untouched — no refinement or self-correction.
- Log every real bug as it happens (failing test, wrong output, bad AI suggestion), with
  the commit where it was fixed. Feeds the M3 audit and the video segment.
- Log only what actually happened. Never invent bugs or results. Write "none found" if so.
