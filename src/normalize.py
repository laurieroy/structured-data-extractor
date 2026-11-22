import math
import re
from datetime import date, datetime

_DATE_FORMATS = (
    "%d %b, %Y",
    "%d %B, %Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%b %d %Y",
    "%B %d %Y",
    "%m/%d/%Y",
)


def parse_money(value) -> float:
    if isinstance(value, bool):
        raise ValueError(f"unparseable money value: {value!r}")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        cleaned = value.strip()
        cleaned = re.sub(r"(?i)\b(?:usd|eur|gbp)\b", "", cleaned)
        cleaned = re.sub(r"[$€£]", "", cleaned)
        cleaned = cleaned.replace(",", "").strip()
        try:
            result = float(cleaned)
        except ValueError:
            raise ValueError(f"unparseable money value: {value!r}") from None
    else:
        raise ValueError(f"unparseable money value: {value!r}")
    if not math.isfinite(result):
        raise ValueError(f"unparseable money value: {value!r}")
    return result


def parse_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(f"unparseable date value: {value!r}")
    text = value.strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    text = re.sub(r"\bof\b", " ", text)
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unparseable date value: {value!r}")


def normalize_invoice_data(data: dict) -> dict:
    data = dict(data)
    if "invoice_date" in data:
        data["invoice_date"] = parse_date(data["invoice_date"])
    for key in ("subtotal", "tax_amount", "total_amount"):
        if key in data:
            data[key] = parse_money(data[key])
    for item in data.get("line_items") or []:
        if "unit_price" in item:
            item["unit_price"] = parse_money(item["unit_price"])
        if "line_total" in item:
            item["line_total"] = parse_money(item["line_total"])
    return data
