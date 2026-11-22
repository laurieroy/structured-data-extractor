"""Streamlit UI over the invoice-extraction pipeline.

Run from the repo root:  uv run streamlit run src/app.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src.extractor import extract_text, extract_with_retry
from src.fallback import DLQ_PATH
from src.schemas import TOLERANCE, ExtractionResult

st.set_page_config(page_title="Invoice Extractor", layout="wide")
st.title("Invoice Extraction Pipeline")
st.caption(
    "PDF/HTML/text → constrained decoding → validation gate → "
    "reflection self-correction → dead-letter queue"
)

STATUS_COLORS = {
    "SUCCESS": "green",
    "REPAIRED_VIA_REFLECTION": "orange",
    "DLQ_FAILED": "red",
}


def _source_text() -> str | None:
    """Resolve the current input to raw text, or None if nothing was given."""
    if uploaded is not None:
        return extract_text(uploaded.getvalue())
    if pasted.strip():
        return extract_text(pasted)
    return None


def _last_dlq_entry() -> str | None:
    try:
        lines = [
            ln for ln in DLQ_PATH.read_text().splitlines() if ln.strip()
        ]
    except OSError:
        return None
    return lines[-1] if lines else None


def _reconciliation_badges(inv) -> None:
    """Recompute the reconciliation rule and show match/mismatch + diff."""
    checks = [
        (
            "Σ line_total vs subtotal",
            round(sum(i.line_total for i in inv.line_items), 2),
            inv.subtotal,
        ),
        (
            "subtotal + tax_amount vs total_amount",
            round(inv.subtotal + inv.tax_amount, 2),
            inv.total_amount,
        ),
    ]
    for label, computed, declared in checks:
        diff = abs(computed - declared)
        if diff <= TOLERANCE:
            st.badge(f"{label}: match (diff {diff:.4f})", color="green")
        else:
            st.badge(f"{label}: MISMATCH (diff {diff:.4f})", color="red")


# --- Inputs -----------------------------------------------------------------

uploaded = st.file_uploader("Upload a PDF invoice", type=["pdf"])
pasted = st.text_area(
    "...or paste invoice HTML / plain text",
    height=160,
    placeholder="Paste raw invoice text or an HTML invoice here",
)
use_reflection = st.toggle("Reflection self-correction loop", value=True)

btn_extract, btn_simulate = st.columns(2)
extract_clicked = btn_extract.button(
    "Extract", type="primary", width="stretch"
)
simulate_clicked = btn_simulate.button(
    "Simulate Edge Case Failure", width="stretch"
)

if extract_clicked or simulate_clicked:
    st.session_state["result"] = None
    raw_text = None
    try:
        raw_text = _source_text()
    except Exception:
        st.error(
            "Couldn't read that document. Try a different PDF or paste the "
            "text directly."
        )
    if raw_text is not None:
        if not raw_text.strip():
            st.warning("Upload a PDF or paste some text first.")
        else:
            prompt_log: list[str] = []
            try:
                with st.spinner("Extracting invoice data..."):
                    result = extract_with_retry(
                        raw_text,
                        use_reflection=use_reflection,
                        simulate_failure=simulate_clicked,
                        prompt_log=prompt_log,
                    )
            except Exception:
                st.error(
                    "Extraction failed unexpectedly. Check the API key and "
                    "connection, then try again."
                )
            else:
                st.session_state.update(
                    raw_text=raw_text,
                    result=result,
                    prompt_log=prompt_log,
                )

# --- Results ----------------------------------------------------------------

result: ExtractionResult | None = st.session_state.get("result")
if result is not None:
    st.divider()
    st.badge(
        result.execution_status.replace("_", " "),
        color=STATUS_COLORS.get(result.execution_status, "gray"),
    )

    inv = result.validated_data
    if inv is not None:
        st.caption(f"Reconciliation (tolerance ±{TOLERANCE})")
        _reconciliation_badges(inv)

    left, right = st.columns(2)
    with left:
        st.subheader("Extracted raw text")
        st.text_area(
            "raw text",
            value=st.session_state.get("raw_text", ""),
            height=400,
            disabled=True,
            label_visibility="collapsed",
        )
    with right:
        st.subheader("Validated invoice")
        if inv is not None:
            st.json(inv.model_dump(mode="json"))
        else:
            st.error(
                "Validation failed — no invoice data. This extraction was "
                "routed to the dead-letter queue."
            )

    with st.expander("Audit log", expanded=True):
        st.write(f"**Attempts used:** {result.attempts_used}")
        st.write("**Error log:**")
        if result.error_log:
            for entry in result.error_log:
                st.markdown(f"- `{entry}`")
        else:
            st.write("No errors logged.")
        st.write("**Reflection prompts:**")
        prompts = st.session_state.get("prompt_log") or []
        if prompts:
            for i, prompt in enumerate(prompts, start=2):
                st.markdown(f"*Attempt {i} corrective prompt:*")
                st.code(prompt, language="text")
        else:
            st.write("No reflection prompts were sent.")

    if result.execution_status == "DLQ_FAILED":
        st.subheader("Dead-letter queue entry")
        last = _last_dlq_entry()
        if last is None:
            st.warning("DLQ file is missing or empty.")
        else:
            try:
                st.json(json.loads(last))
            except json.JSONDecodeError:
                st.code(last, language="text")
