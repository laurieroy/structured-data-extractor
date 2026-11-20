---
name: web-qa
description: Run the course web-project QA checklist (functionality, deployment/cross-browser, Lighthouse, code validation) against a running or deployed app
argument-hint: "<url>"
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - grep
  - webfetch
permissions:
  allow:
    - "mcp__playwright__*"
---

# Web Project QA Checklist

Run the four-phase QA pass from the course "Web Project Testing & Quality
Assurance Guide" against a running app. `<url>` is the target — typically
`http://localhost:8501` for the local Streamlit UI or the deployed URL from M6.

If no URL is provided or the app is not reachable: do NOT start it yourself. Per
this repo's manual-mode rules, hand the user the command and wait:

    uv run streamlit run src/app.py

If the Playwright MCP is unavailable, report the browser-dependent steps as
manual checklist items instead of silently skipping them.

## Phase 1 — Functionality walkthrough

First call `mcp_list_tools` on the `playwright` server to get the exact tool
names, then use the browser tools (typically `browser_navigate`,
`browser_snapshot`, `browser_click`, `browser_type`, etc.):

- Navigate to the URL; snapshot the page and enumerate every interactive
  element (sidebar widgets, buttons, toggles, file uploader, text areas).
- Click each one; verify it does what its label says.
- Empty submission (no file / blank textarea) → expect a clean error, not a
  crash.
- Invalid input (nonsense text) → expect `DLQ_FAILED` handling, not an
  exception.
- Valid input (`samples/invoice_messy.pdf` or equivalent golden text) →
  validated JSON renders side-by-side with the raw document.
- Toggle "Enable reflection" off/on and re-run a submission.
- Click "Simulate Edge Case Failure" → an entry is appended to
  `dlq/failed_extractions.jsonl` and the UI shows a clean failure state.

## Phase 2 — Deployment & cross-browser

- A fresh Playwright context has no cache — equivalent to the guide's
  incognito-window check.
- Watch console errors and failed network requests for broken assets
  (images, fonts, local file paths that leaked into the deploy).
- Resize the viewport to 375, 768, and 1440 px; screenshot each. Check for
  content overlap, cut-off text, horizontal scrolling. Streamlit is fixed-width
  by design — a mobile-width scrollbar is expected; report it, don't "fix" the
  framework.
- Cross-browser: if the connected Playwright server exposes non-Chromium
  browsers, spot-check one; otherwise mark N/A and note which browser was used.

## Phase 3 — Lighthouse audit

Run via `exec` (requires Chrome). The first `npx` run downloads the package,
so it can take a while and may need exec approval — per this repo's manual
mode, if in doubt hand the user the command instead of running it yourself:

```bash
npx -y lighthouse <url> --only-categories=performance,accessibility,seo \
  --output=json --output-path=/tmp/lighthouse-report.json \
  --chrome-flags="--headless"
```

- Parse the three category scores (mobile). Target: 80+ each per the guide.
- If it can't run (no Chrome, no npx), mark the phase manual and move on.
- Streamlit apps typically score lower on SEO/accessibility because markup is
  framework-generated — report the gaps and the top "Opportunities" /
  "Diagnostics" items; do not attempt to patch Streamlit internals.

## Phase 4 — Code validation

- HTML: `webfetch` `https://validator.w3.org/nu/?doc=<url>` and summarize
  errors/warnings.
- CSS: only if the project ships hand-written CSS (check `src/` / `static/`).
  For Streamlit-generated markup and styles, validator warnings are expected —
  document them as framework N/A rather than fixing.

## Report

Finish with a per-phase summary table:

| Phase                     | Result             | Notes |
| ------------------------- | ------------------ | ----- |
| 1 Functionality           | PASS/FAIL          | ...   |
| 2 Deployment & responsive | PASS/FAIL          | ...   |
| 3 Lighthouse              | score vs 80 target | ...   |
| 4 Code validation         | PASS/FAIL/N-A      | ...   |

Then list findings and suggested fixes. Checklist items that don't apply to a
Streamlit app are reported as N/A — never silently skipped.
