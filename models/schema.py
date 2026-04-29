from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


class ExtractionStatus(str, Enum):
    SUCCESS = "success"
    FLAGGED = "flagged"
    FAILED = "failed"


class FieldExtraction(BaseModel):
    value: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence 0.0–1.0")


class DocumentExtraction(BaseModel):
    """Structured output returned by the LLM for a single document."""
    vendor: FieldExtraction
    amount: FieldExtraction
    date: FieldExtraction
    due_date: FieldExtraction
    category: FieldExtraction
    invoice_number: FieldExtraction

    def min_confidence(self) -> float:
        fields = [self.vendor, self.amount, self.date,
                  self.due_date, self.category, self.invoice_number]
        present = [f.confidence for f in fields if f.value is not None]
        return min(present) if present else 0.0


class DocumentRecord(BaseModel):
    """Row stored in SQLite after orchestration completes."""
    id: Optional[int] = None
    filename: str
    vendor: Optional[str] = None
    amount: Optional[str] = None
    date: Optional[str] = None
    due_date: Optional[str] = None
    category: Optional[str] = None
    invoice_number: Optional[str] = None
    min_confidence: float
    status: ExtractionStatus
    retry_count: int = 0
    created_at: Optional[str] = None


class TextIngestRequest(BaseModel):
    text: str
    filename: str = "inline.txt"
