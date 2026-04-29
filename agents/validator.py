from typing import Literal
from models.schema import DocumentExtraction

CONFIDENCE_PASS = 0.7
CONFIDENCE_FLAG = 0.4
MAX_RETRIES = 2


def route(
    extraction: DocumentExtraction,
    retry_count: int,
) -> Literal["retry", "store_success", "store_flagged"]:
    """
    Decide next action based on field-level confidence.

    retry        → at least one field is below PASS threshold and we have retries left
    store_flagged → below FLAG threshold or retries exhausted
    store_success → all present fields meet the PASS threshold
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

    min_conf = min(present_confidences)

    if min_conf >= CONFIDENCE_PASS:
        return "store_success"

    if min_conf < CONFIDENCE_FLAG or retry_count >= MAX_RETRIES:
        return "store_flagged"

    return "retry"
