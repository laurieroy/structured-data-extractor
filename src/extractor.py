import io
import os
from pathlib import Path

import instructor
from anthropic import Anthropic
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pypdf import PdfReader

from src.fallback import run_fallback
from src.normalize import normalize_invoice_data
from src.schemas import ExtractionResult, InvoiceExtraction

load_dotenv()

EXTRACTION_PROMPT = """Extract the invoice data from the document below.

Return an invoice with these fields:
- invoice_number (alphanumeric with optional hyphens, 3-20 chars)
- vendor_name
- invoice_date
- line_items: list of {{description, quantity, unit_price, line_total}}
- subtotal, tax_amount, total_amount
- currency (USD, EUR, or GBP)

Document:
{raw_text}"""


def extract_text(source) -> str:
    """Pull plain text out of a PDF, an HTML file, or a raw string."""
    if isinstance(source, bytes):
        reader = PdfReader(io.BytesIO(source))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if isinstance(source, (str, Path)):
        try:
            is_path = Path(source).exists()
        except (OSError, ValueError):
            is_path = False
        if is_path:
            path = Path(source)
            if path.suffix.lower() == ".pdf":
                reader = PdfReader(str(path))
                return "\n".join(
                    page.extract_text() or "" for page in reader.pages
                )
            if path.suffix.lower() in (".html", ".htm"):
                soup = BeautifulSoup(path.read_text(), "html.parser")
                return soup.get_text(" ", strip=True)
            return path.read_text()
    text = str(source)
    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "html.parser")
        if soup.find():
            return soup.get_text(" ", strip=True)
    return text


def _clients():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    model = os.environ.get("EXTRACTOR_MODEL")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    if not model:
        raise RuntimeError("EXTRACTOR_MODEL is not set")
    raw_client = Anthropic(api_key=api_key)
    return instructor.from_anthropic(raw_client), raw_client, model


def extract_with_retry(raw_text: str, max_retries: int = 3) -> ExtractionResult:
    client, raw_client, model = _clients()
    error_log: list[str] = []
    try:
        invoice = client.messages.create(
            model=model,
            max_tokens=2048,
            response_model=InvoiceExtraction,
            messages=[
                {"role": "user", "content": EXTRACTION_PROMPT.format(raw_text=raw_text)}
            ],
        )
        invoice = InvoiceExtraction(
            **normalize_invoice_data(invoice.model_dump())
        )
        return ExtractionResult(
            validated_data=invoice,
            attempts_used=1,
            error_log=error_log,
            execution_status="SUCCESS",
        )
    except Exception as exc:
        error_log.append(f"attempt 1: {exc}")
        return run_fallback(
            raw_client,
            client,
            model,
            raw_text,
            last_raw=getattr(exc, "raw_output", None) or str(exc),
            error_log=error_log,
            max_retries=max_retries,
        )


if __name__ == "__main__":
    result = extract_with_retry(extract_text("samples/invoice_messy.pdf"))
    print(result.model_dump_json(indent=2))
