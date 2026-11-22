import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

TOLERANCE = 0.02

# Alphanumeric + hyphen invoice IDs, e.g. "INV-2024-0847", "VSA-2024-331"
INVOICE_NUMBER_RE = re.compile(r"^[A-Za-z0-9-]{3,20}$")


class LineItem(BaseModel):
    description: str
    quantity: int
    unit_price: float
    line_total: float

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v):
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v

    @field_validator("unit_price")
    @classmethod
    def unit_price_positive(cls, v):
        if v <= 0:
            raise ValueError("unit_price must be > 0")
        return v

    @field_validator("line_total")
    @classmethod
    def line_total_non_negative(cls, v):
        if v < 0:
            raise ValueError("line_total must be >= 0")
        return v


class InvoiceExtraction(BaseModel):
    invoice_number: str
    vendor_name: str
    invoice_date: date
    line_items: list[LineItem]
    subtotal: float
    tax_amount: float
    total_amount: float
    currency: Literal["USD", "EUR", "GBP"]

    @field_validator("invoice_number")
    @classmethod
    def invoice_number_format(cls, v):
        if not INVOICE_NUMBER_RE.fullmatch(v.strip()):
            raise ValueError("invoice_number must match ^[A-Za-z0-9-]{3,20}$")
        return v

    @field_validator("line_items")
    @classmethod
    def line_items_non_empty(cls, v):
        if not v:
            raise ValueError("line_items must contain at least one item")
        return v

    @field_validator("subtotal", "tax_amount", "total_amount")
    @classmethod
    def amounts_non_negative(cls, v):
        if v < 0:
            raise ValueError("amount must be >= 0")
        return v

    @model_validator(mode="after")
    def reconcile_totals(self):
        lines_sum = round(sum(item.line_total for item in self.line_items), 2)
        if abs(lines_sum - self.subtotal) > TOLERANCE:
            raise ValueError(
                f"subtotal {self.subtotal} does not match sum of line_total "
                f"{lines_sum} (diff {abs(lines_sum - self.subtotal):.4f})"
            )
        expected_total = round(self.subtotal + self.tax_amount, 2)
        if abs(expected_total - self.total_amount) > TOLERANCE:
            raise ValueError(
                f"total_amount {self.total_amount} does not match subtotal + "
                f"tax_amount {expected_total} "
                f"(diff {abs(expected_total - self.total_amount):.4f})"
            )
        return self


class ExtractionResult(BaseModel):
    validated_data: Optional[InvoiceExtraction]
    attempts_used: int
    error_log: list[str]
    execution_status: Literal[
        "SUCCESS", "REPAIRED_VIA_REFLECTION", "DLQ_FAILED"
    ]
