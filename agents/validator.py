from typing import Literal
from models.schema import DocumentExtraction

CONFIDENCE_PASS = 0.7
CONFIDENCE_FLAG = 0.4
MAX_RETRIES = 2
MIN_CORE_FIELDS = 2  # at least 2 of (vendor, amount, date) must be extracted

# Fields that must be present for a document to be considered meaningful
_CORE_FIELDS = ["vendor", "amount", "date"]


def route(
    extraction: DocumentExtraction,
    retry_count: int,
) -> Literal["retry", "store_success", "store_flagged"]:
    """
    Decide next action based on field-level confidence.

    retry        → core fields missing or low confidence, retries remaining
    store_flagged → too few core fields extracted, or retries exhausted
    store_success → enough core fields present and all pass confidence threshold
    """
    fields = [
        extraction.vendor,
        extraction.amount,
        extraction.date,
        extraction.due_date,
        extraction.category,
        extraction.invoice_number,
    ]
    present_confidences = [f.confidence for f in fields if f.value is not None]

    if not present_confidences:
        return "store_flagged"

    # Count how many core fields were actually extracted
    core_values = [
        getattr(extraction, name).value
        for name in _CORE_FIELDS
    ]
    extracted_core = sum(1 for v in core_values if v is not None)

    # Flag immediately if the document is too sparse to be useful
    if extracted_core < MIN_CORE_FIELDS:
        if retry_count >= MAX_RETRIES:
            return "store_flagged"
        return "retry"

    min_conf = min(present_confidences)

    if min_conf >= CONFIDENCE_PASS:
        return "store_success"

    if min_conf < CONFIDENCE_FLAG or retry_count >= MAX_RETRIES:
        return "store_flagged"

    return "retry"
