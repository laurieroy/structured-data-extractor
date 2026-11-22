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
