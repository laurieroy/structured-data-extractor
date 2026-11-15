# Assignment: Resilient Unstructured Data Extraction & Pydantic Validation Pipelines

**Due:** Sunday, Oct 25, 2026, 11:59 PM

---

## 1. TL;DR

Build a fault-tolerant pipeline that turns messy PDFs/HTML (e.g., invoices) into **strictly validated Pydantic v2 records** using an LLM. When validation fails, the system self-corrects through a reflection loop, then falls back to heuristic repair, then to a dead-letter queue (DLQ). Wrap it in a web UI, test it, deploy it (or containerize it), and record a 5–7 minute video.

You also have to **use an AI assistant to write the first draft, then audit it** for anti-patterns and document the findings.

---

## 2. Deliverables Checklist

- [ ] GitHub repo with the required structure (see §4)
- [ ] `README.md` with all 5 required sections (see §8)
- [ ] `ai_prompt_log.md` (prompt, initial output, audit, fixes)
- [ ] Working web UI (Streamlit, FastAPI + HTML, or Chainlit)
- [ ] Test suite: 5+ passing tests via `pytest -v`
- [ ] Deployment: cloud app **or** `Dockerfile` + `docker-compose.yml`
- [ ] YouTube video (unlisted/public), 5:00–7:00, face visible throughout
- [ ] Submission template filled in and submitted via the LMS (see §9)

---

## 3. The Three-Stage Pipeline

| Stage | What happens | Key detail |
|---|---|---|
| **1. Constrained decoding** | LLM extracts into the Pydantic schema using native structured output (OpenAI Structured Outputs, Anthropic tool use, or `instructor`/`outlines`) | Schema enforced at generation time |
| **2. Reflection loop** | On `ValidationError`, re-prompt with the original context snippet, the previous malformed JSON, and the exact error locations/messages (`err['loc']`, `err['msg']`) | Bounded retries with backoff; don't resend the whole document |
| **3. Heuristic fallback + DLQ** | After max retries, try `json_repair` / partial extraction; if that fails, write the payload to a DLQ file with a failure flag for human review | Must never crash the app or silently return empty objects |

**Result object (`ExtractionResult`):**
- `validated_data`: `Optional[InvoiceExtraction]`
- `attempts_used`: `int`
- `error_log`: `List[str]`
- `execution_status`: `"SUCCESS" | "REPAIRED_VIA_REFLECTION" | "DLQ_FAILED"`

---

## 4. Step-by-Step Breakdown

### Step 1: Environment & Schema Definition

**Setup commands**
```bash
uv init structured-data-extractor
cd structured-data-extractor
uv python pin 3.11
uv add pydantic openai instructor pypdf beautifulsoup4 fastapi uvicorn python-dotenv pytest pytest-asyncio streamlit json-repair
```

**Required project structure**
```
structured-data-extractor/
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── ai_prompt_log.md
├── samples/
│   ├── invoice_messy.pdf
│   └── vendor_contract.html
├── src/
│   ├── __init__.py
│   ├── schemas.py       # Pydantic models
│   ├── extractor.py     # Extraction + validation engine
│   ├── fallback.py      # Reflection re-prompting + heuristic repair
│   └── app.py           # Web UI
└── tests/
    ├── __init__.py
    ├── test_extraction.py
    └── test_fallbacks.py
```

**`schemas.py` must include**
- Nested models (e.g., `LineItem` inside `InvoiceExtraction`)
- Field validators: ISO-8601 dates, positive quantities, clean tax percentages, regex/bounds/enums
- A root `@model_validator(mode="after")` checking that line-item sums match the invoice total within **0.02 tolerance**

**Suggested baseline schema (from the sample prompt)**
- `LineItem`: `description` (str), `quantity` (int > 0), `unit_price` (float > 0), `line_total` (float)
- `InvoiceExtraction`: `invoice_number`, `vendor_name`, `invoice_date` (date), `line_items`, `subtotal`, `tax_amount`, `total_amount`, `currency` (`Literal["USD","EUR","GBP"]`)

### Step 2: Generate the Initial Draft with AI

- Use Cursor, Claude Code, ChatGPT, or Copilot.
- Adapt the provided sample prompt ("Staff AI Systems Engineer..."). It asks for `schemas.py`, `extractor.py`, and `fallback.py`, plus `extract_with_retry(raw_text, max_retries=3) -> ExtractionResult`.
- **Save the exact prompt and the raw output** in `ai_prompt_log.md`.

### Step 3: Audit the AI Output

Record findings in `ai_prompt_log.md`. Check for:

1. **Pydantic v1 vs v2 collisions:** `@validator` instead of `@field_validator`/`@model_validator`; `.dict()` instead of `.model_dump()`.
2. **Context stuffing / token bloat:** Is the whole document re-sent on every retry? Fix by truncating to the relevant window and passing targeted errors.
3. **Lost deterministic enforcement:** Does the fallback silently swallow errors and return half-empty/all-`None` objects?
4. **Date and type coercion fragility:** Are non-standard dates (e.g., "12th of Oct, 2024") and values like "$1,249.50" handled with a pre-parser before Pydantic runs?

**Minimum requirement:** concretely identify and fix **at least two** real bugs/anti-patterns.

### Step 4: Build the Web UI

The UI must let the user:
- Upload a PDF **or** paste raw HTML/text
- Toggle the **Reflection Self-Correction Loop** on/off
- View, in real time:
  - Side-by-side: raw document vs. validated JSON
  - A **reconciliation badge** (do line items match the grand total?)
  - A step-by-step **audit log**: retry counts, raw validation error traces, exact corrective prompts sent
- Click a **"Simulate Edge Case Failure"** button to exercise the DLQ path

### Step 5: QA Test Suite

| Test | File | What it verifies |
|---|---|---|
| 1. Golden document | `test_extraction.py` | Well-formed sample parses on **Attempt 1** with zero validation errors |
| 2. Schema constraints | `test_extraction.py` | Quantity ≤ 0 or negative totals raise validation errors |
| 3. Cross-field reconciliation | `test_extraction.py` | Line items not summing to `total_amount` fail validation |
| 4. Reflection success | `test_fallbacks.py` | Mock malformed response (missing currency / bad date) self-heals on **Attempt 2** |
| 5. DLQ routing | `test_fallbacks.py` | Nonsense input → after `max_retries=3`, status is `DLQ_FAILED`, payload logged to DLQ/disk cache, **no crash** |

All must pass with `pytest -v`.

### Step 6: Deployment

Choose one:
- **Cloud:** Streamlit Community Cloud, Render, Railway, or Hugging Face Spaces, with secrets in the host's secret manager (never in the repo)
- **Local container fallback:** clean `Dockerfile` + `docker-compose.yml`, and show end-to-end containerized execution in the video

---

## 5. Video Requirements (5:00–7:00, strictly timed)

- Screen share **plus webcam overlay**, face visible the whole time
- Upload to YouTube as Unlisted or Public
- Under 5:00 lacks depth; **over 7:00 gets an automatic timing penalty**

| Segment | Time | Content |
|---|---|---|
| 1. Architecture & schema | ~1:00 | State your name; walk through folder layout; show Pydantic v2 schemas and custom validators in `schemas.py` |
| 2. AI code audit | ~1:30 | Open `ai_prompt_log.md`; show the prompt; highlight 2+ bugs/bad assumptions and the fixes |
| 3. Live extraction & UI demo | ~1:30 | Upload a messy PDF/HTML; run the extractor; show real-time structured output |
| 4. Reflection loop & DLQ | ~1:30 | Trigger a validation error (calculation mismatch or malformed date); show the UI capturing the error, building the reflection prompt, and self-healing; then show DLQ recording on an irrecoverable input |
| 5. Test run | ~0:30 | Run `pytest -v` showing all 5+ tests passing |

Total target: about 6:00, leaving a buffer under the 7:00 cap.

---

## 6. Grading Rubric (100 pts)

| Category | Pts | What earns the points |
|---|---|---|
| **1. Schema architecture & Pydantic validation** | 20 | Nested v2 models; regex/bounds/enum validators; cross-field `@model_validator`; clean handling of dates, currencies, float precision |
| **2. Extraction engine & constrained decoding** | 20 | Proper structured-output/tool-schema usage (Instructor/OpenAI/Anthropic); correct ingestion from messy PDF/HTML with text pre-processing |
| **3. Resilient reflection & fallback engineering** | 20 | Reflection loop re-prompts with precise error diffs; deterministic retry limits; `json_repair` fallback; safe DLQ routing with no crashes |
| **4. AI audit log & human verification** | 15 | Complete `ai_prompt_log.md` (prompt, initial output, technical audit); 2+ legitimate bugs/anti-patterns found and refactored |
| **5. QA test suite** | 10 | 5+ passing tests covering golden extraction, schema rejection, reflection recovery, DLQ handling |
| **6. Web UI, video & professionalism** | 15 | Responsive UI with side-by-side view, retry logs, reconciliation status; 5–7 min video with webcam showing all failure simulations and tests |

---

## 7. Suggested Work Plan

1. **Setup & schemas:** init repo, define models and validators, write Tests 1-3 early (they're pure Pydantic, no API calls).
2. **AI draft:** run the sample prompt, save prompt and output verbatim to `ai_prompt_log.md`.
3. **Audit & refactor:** go through the four anti-pattern checks, fix, and log before/after.
4. **Fallbacks & tests:** finish reflection loop, `json_repair`, DLQ writer; mock the LLM client for Tests 4-5 so they're deterministic and need no API key.
5. **UI:** build upload/paste, toggle, side-by-side view, reconciliation badge, audit log, and failure-simulation button.
6. **Deploy/containerize.**
7. **README** with Mermaid diagram.
8. **Record the video** (do a dry run to check timing), then submit.

---

## 8. README.md Requirements

1. **Architecture & data-flow diagram (Mermaid):** Document Ingestion → Text Extraction → Constrained LLM Decoding → Pydantic Validation Gate → (Pass → UI/Downstream) or (Fail → Reflection Loop → DLQ)
2. **Installation & setup guide** using `uv` or `poetry`, Python 3.11+
3. **Schema specification:** fields, types, and custom cross-field rules
4. **Execution commands:** exact commands to run the web app and `pytest -v`
5. **AI audit log summary:** initial generation, prompt revisions, syntax corrections, architectural improvements

---

## 9. Submission Template

```markdown
### Week 2 Hands-On Assignment Submission

* **Student Name:** [Your Name]
* **GitHub Repository URL:** https://github.com/[your-username]/structured-data-extractor
* **Live Deployment URL (if applicable):** https://[your-app].streamlit.app (or Docker demo note)
* **YouTube Video Link:** https://youtu.be/[your-video-id] (Duration: MM:SS)
* **Extraction Domain Implemented:** [e.g., Commercial Invoices / Medical Trial Disclosures / Vendor Agreements]
* **Validation Strategy:** Pydantic v2 + Instructor / OpenAI Structured Outputs + Reflection Self-Correction
```

---

## 10. Pitfalls and Ambiguities to Watch

- **Validator math is inconsistent in the prompt.** The schema section says line-item sub-totals should match the total, but the sample prompt checks `sum(line_total) + tax_amount == total_amount`, and the schema also has a `subtotal` field. Pick one clear rule (e.g., sum of lines ≈ `subtotal` and `subtotal + tax_amount` ≈ `total_amount`, both within 0.02), and document it.
- **Mock the LLM in tests.** Tests 4 and 5 should use a fake client so they're deterministic and don't burn API credits.
- **Never let the fallback return an empty object quietly.** `DLQ_FAILED` should have `validated_data=None` and a populated `error_log`.
- **Keep secrets out of git.** Only `.env.example` gets committed; set real keys in the host's secret manager.
- **Pre-parse messy values** (`"$1,249.50"`, `"12th of Oct, 2024"`) before Pydantic sees them.
- **The template says "Week 2"** while this file is named week 4; use whatever wording your LMS expects.

Converted from the course assignment brief by Claude (Sonnet 5.5), with minimal human input.