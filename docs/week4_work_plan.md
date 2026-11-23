# Work Plan: Resilient Data Extraction Pipeline

Companion to `week4_assignment.md`. Built with AI agents, gated by human review.

**How to use this file:** work top to bottom. Tick a checkbox only when its *Definition of Done* is met and you have run the tests yourself. Commit after every completed milestone.

---

## Working Rules (apply to every milestone)

1. **One agent task per milestone.** Never ask for the whole system at once.
2. **Spec lives in the repo.** Keep `week4_assignment.md` and an `AGENTS.md` at the root.
3. **Tests first.** Agent writes tests, confirm they fail, then implement until green.
4. **You are the gate.** Run `pytest -v` yourself and skim the diff before moving on.
5. **Commit after each green milestone** with a message saying what changed and why.
6. **Log notable agent behavior** in `ai_prompt_log.md` as you go.

### Suggested `AGENTS.md` non-negotiables
- Python 3.11, Pydantic v2 only (`@field_validator`, `@model_validator`, `.model_dump()`)
- No `@validator`, no `.dict()`
- Mock the LLM client in all tests; no real API calls in `pytest`
- Never return a partial or all-`None` object on failure; use `DLQ_FAILED` with `validated_data=None`
- Retry prompts include only the relevant context snippet plus targeted errors, never the full document
- Secrets only in `.env`; commit `.env.example` only

### Post-milestone verification checklist
- [ ] Tests pass when I run them
- [ ] `grep -rn "@validator\|\.dict(" src/` returns nothing
- [ ] No secrets in the diff
- [ ] Failure cases raise or return explicit errors
- [ ] Committed with a clear message

---

## Progress Tracker

| # | Milestone | Effort | Status |
|---|---|---|---|
| M0 | Setup and decisions | ~5% | ☑ |
| M1 | Data contract (schemas + tests 1-3) | ~15% | ☑ |
| M2 | Baseline AI draft (captured untouched) | ~10% | ☐ |
| M3 | Audit and refactor | ~15% | ☐ |
| M4 | Resilience: reflection, repair, DLQ (tests 4-5) | ~25% | ☐ |
| M5 | Web UI | ~15% | ☐ |
| M6 | Packaging and deployment | ~5% | ☐ |
| M7 | README, video, submission | ~10-15% | ☐ |

---

## M0: Setup and Decisions

**Goal:** a runnable empty project and the key decisions locked in.

**Decisions to make first**
- [x] LLM provider and library (default: OpenAI or Anthropic + `instructor`)
- [x] Extraction domain (default: commercial invoices)
- [x] Reconciliation rule, written down (suggested: `sum(line_total) ≈ subtotal` and `subtotal + tax_amount ≈ total_amount`, tolerance 0.02)
- [x] Max retries and backoff policy (default: 3 retries, exponential backoff)

**Agent task:** scaffold the repo exactly per the assignment structure; run the `uv` setup commands; create `.env.example`, `.gitignore`, `AGENTS.md`.

**Also do (human):** create or collect `samples/invoice_messy.pdf` (include odd formats such as `$1,249.50` and "12th of Oct, 2024") and `samples/vendor_contract.html`. Add an API key to `.env`.

**Definition of Done**
- [x] Folder structure matches the assignment
- [x] `uv run python -c "import pydantic, instructor"` succeeds
- [x] One "hello world" LLM call succeeds
- [x] First commit made

---

## M1: Data Contract (Schemas + Tests 1-3)

**Goal:** a strict, tested schema. Everything else depends on it.

**Agent task:** write `tests/test_extraction.py` (Tests 1-3) first, then `src/schemas.py`.

**Schema checklist**
- [x] `LineItem`: description, quantity (int > 0), unit_price (> 0), line_total
- [x] `InvoiceExtraction`: invoice_number, vendor_name, invoice_date, line_items, subtotal, tax_amount, total_amount, currency (`Literal["USD","EUR","GBP"]`)
- [x] `@field_validator` for ISO-8601 dates, positive quantities, clean tax percentages, regex on invoice number
- [x] `@model_validator(mode="after")` implementing the chosen reconciliation rule within 0.02
- [x] Pre-parsers for currency strings and non-standard dates (decided: live in ingestion — `src/normalize.py`)

**Tests in this milestone**
- [x] Test 1: golden payload validates (the *LLM-driven* attempt-1 check comes in M2)
- [x] Test 2: quantity ≤ 0 and negative totals are rejected
- [x] Test 3: mismatched sums are rejected

**Definition of Done**
- [x] Tests 2 and 3 pass; Test 1 passes against a hand-built golden payload
- [x] No v1 syntax
- [x] Committed

---

## M2: Baseline AI Draft (Capture Untouched)

**Goal:** the "before" snapshot your audit needs.

**Agent task:** run the sample prompt from the assignment (adapted to your decisions) to generate `extractor.py` and `fallback.py`. **Do not let the agent refine or self-correct.**

**Human steps**
- [x] Copy the exact prompt into `ai_prompt_log.md`
- [x] Save the raw generated code (commit it as its own commit: `baseline: unmodified AI output`)
- [x] Get Stage 1 working on `invoice_messy.pdf` just enough to confirm it runs; note any failures but don't fix yet

**Definition of Done**
- [x] Prompt and raw output logged
- [x] Baseline committed separately
- [x] Golden PDF extracts (or failures are noted)

---

## M3: Audit and Refactor

**Goal:** documented, real fixes. Needs at least two; aim for four.

**Agent task:** use a **fresh session** with a reviewer prompt: *"Review this code for the four anti-patterns below. Find and explain problems; do not rewrite."*

**Audit checklist (log finding, evidence, fix, before/after for each)**
- [x] Pydantic v1/v2 collisions (`@validator`, `.dict()`)
- [x] Context stuffing and token bloat in the retry loop
- [x] Silent swallowing of errors / half-empty objects returned
- [x] Date and type coercion fragility
- [x] Anything else found (security gaps, hard-coded keys, unbounded retries, no timeouts)

**Human steps**
- [x] Verify each finding is real before fixing it
- [x] Apply each fix as a separate commit

**Definition of Done**
- [x] `ai_prompt_log.md` has prompt, initial output, audit, and fixes
- [x] 2+ fixes committed separately
- [x] Tests still pass

---

## M4: Resilience (Reflection, Repair, DLQ, Tests 4-5)

**Goal:** the three-stage pipeline works and never crashes. This carries the most weight.

**Agent task:** write `tests/test_fallbacks.py` (Tests 4-5) with a mocked LLM client first, then implement.

**Build checklist**
- [x] `ExtractionResult`: `validated_data`, `attempts_used`, `error_log`, `execution_status`
- [x] Stage 1: constrained structured decoding
- [x] Stage 2: reflection loop re-prompts with context snippet + previous JSON + `err['loc']`/`err['msg']`
- [x] Bounded retries with backoff
- [x] Stage 3: `json_repair` attempt, then validate the repaired output (repair does not bypass validation)
- [x] DLQ writer (JSONL file with timestamp, payload, errors, failure flag)
- [x] Reflection on/off switch (needed by the UI)
- [x] Simulated-failure hook (needed by the UI button)

**Tests**
- [x] Test 4: malformed mock response self-heals on Attempt 2 (`REPAIRED_VIA_REFLECTION`)
- [x] Test 5: nonsense input → `DLQ_FAILED` after 3 retries, DLQ entry written, no exception

**Definition of Done**
- [x] All 5+ tests pass via `pytest -v`
- [x] Failure path returns `validated_data=None`, never a hollow object
- [x] Retry prompts verified not to contain the full document
- [x] Committed

---

## M5: Web UI

**Goal:** a thin view over `ExtractionResult`.

**Agent task:** build `src/app.py` (Streamlit is the fastest option).

**Feature checklist**
- [x] Upload PDF or paste HTML/text
- [x] Toggle: reflection loop on/off
- [x] Side-by-side: raw document vs. validated JSON
- [x] Reconciliation badge (match / mismatch with the difference shown)
- [x] Audit log panel: attempts, raw validation errors, exact corrective prompts
- [x] "Simulate Edge Case Failure" button routing to the DLQ
- [x] Clear error display (no stack traces shown to the user)

**Definition of Done**
- [x] The full demo script (below) runs from the UI with no terminal use
- [x] Works with reflection on and off
- [x] Committed

---

## M6: Packaging and Deployment

**Goal:** someone else can run it from a clean clone.

**Agent task:** write `Dockerfile` and `docker-compose.yml`; optionally deploy to Streamlit Community Cloud / Render / Railway / HF Spaces.

**Checklist**
- [ ] `docker compose up` starts the app
- [ ] API key passed via environment variable, not baked into the image
- [ ] If deploying: secrets set in the host's secret manager
- [ ] Tested from a fresh clone

**Definition of Done**
- [ ] Container runs end to end, or a live URL works
- [ ] Committed

---

## M7: README, Video, and Submission

**Goal:** a polished, submit-ready package.

**README checklist**
- [ ] Mermaid diagram: Ingestion → Text Extraction → Constrained Decoding → Validation Gate → (Pass → UI) / (Fail → Reflection → DLQ)
- [ ] Installation and setup (`uv`, Python 3.11+)
- [ ] Schema specification table (fields, types, cross-field rules)
- [ ] Execution commands (run app, `pytest -v`)
- [ ] AI audit log summary
- [ ] Every command verified to work

**Video (5:00-7:00, face visible throughout)**
- [ ] ~1:00 Architecture and schema walkthrough (state your name)
- [ ] ~1:30 `ai_prompt_log.md`: prompt, 2+ bugs, fixes
- [ ] ~1:30 Live extraction in the UI
- [ ] ~1:30 Reflection loop self-heal, then DLQ demo
- [ ] ~0:30 `pytest -v` all green
- [ ] Rehearsed once; final length checked (target ~6:00)
- [ ] Uploaded to YouTube (unlisted/public); link tested logged out

**Submission**
- [ ] `pyproject.toml` dependency cleanup — remove anything unused (likely candidates:
      `fastapi`/`uvicorn` if Streamlit-only, `openai` if Anthropic-only), then `uv sync`
      and re-run `uv run pytest -v`
- [ ] Repo is public (or accessible to the grader) and pushed
- [ ] Submission template filled in and submitted in the LMS

---

## Demo Script (build this up from M2 onward)

Add each failure case you discover here as you go.

1. Upload `invoice_messy.pdf` → clean extraction, reconciliation badge green
2. Input with a line-item total mismatch → validation error captured, reflection prompt shown, self-heals on attempt 2
3. Input with a malformed date → same flow
4. Reflection toggled off → shows the failure without self-correction
5. "Simulate Edge Case Failure" / nonsense input → `DLQ_FAILED`, DLQ entry shown
6. Terminal: `pytest -v` → all pass

---

## Scope Cuts (only if time runs short, in this order)

1. UI polish
2. Cloud deploy (use Docker instead)
3. Second sample document (HTML)

**Never cut:** audit log, tests, fallback logic, schema validators. These carry the most points.

---

## Rubric Cross-Check (before submitting)

| Category | Pts | Where it is satisfied |
|---|---|---|
| Schema & validation | 20 | M1 |
| Extraction & constrained decoding | 20 | M2, M3 |
| Reflection & fallback | 20 | M4 |
| AI audit log | 15 | M2, M3 |
| QA test suite | 10 | M1, M4 |
| UI, video, professionalism | 15 | M5, M7 |

Generated by Claude Code (Sonnet 5.5) and Devin (SWE-2) with Laurie directing.
