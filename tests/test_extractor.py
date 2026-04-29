import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from models.schema import DocumentExtraction, FieldExtraction, ExtractionStatus
from agents.validator import route, CONFIDENCE_PASS, CONFIDENCE_FLAG, MAX_RETRIES
from agents.ingestion import ingest_text
from orchestrator.graph import run


SAMPLE_INVOICE = """
INVOICE

Vendor: Acme Corp
Invoice #: INV-2024-001
Date: 2024-03-15
Due Date: 2024-04-15

Description: Software consulting services
Total Amount: $4,500.00
"""


def _make_extraction(confidence: float) -> DocumentExtraction:
    f = lambda v: FieldExtraction(value=v, confidence=confidence)
    return DocumentExtraction(
        vendor=f("Acme Corp"),
        amount=f("$4,500.00"),
        date=f("2024-03-15"),
        due_date=f("2024-04-15"),
        category=f("invoice"),
        invoice_number=f("INV-2024-001"),
    )


class TestValidator:
    def test_high_confidence_returns_success(self):
        ext = _make_extraction(0.9)
        assert route(ext, retry_count=0) == "store_success"

    def test_medium_confidence_triggers_retry(self):
        ext = _make_extraction(0.6)
        assert route(ext, retry_count=0) == "retry"

    def test_retry_exhausted_returns_flagged(self):
        ext = _make_extraction(0.6)
        assert route(ext, retry_count=MAX_RETRIES) == "store_flagged"

    def test_very_low_confidence_returns_flagged_immediately(self):
        ext = _make_extraction(CONFIDENCE_FLAG - 0.01)
        assert route(ext, retry_count=0) == "store_flagged"

    def test_empty_extraction_returns_flagged(self):
        ext = DocumentExtraction(
            vendor=FieldExtraction(value=None, confidence=0.0),
            amount=FieldExtraction(value=None, confidence=0.0),
            date=FieldExtraction(value=None, confidence=0.0),
            due_date=FieldExtraction(value=None, confidence=0.0),
            category=FieldExtraction(value=None, confidence=0.0),
            invoice_number=FieldExtraction(value=None, confidence=0.0),
        )
        assert route(ext, retry_count=0) == "store_flagged"


class TestIngestion:
    def test_ingest_text_strips_whitespace(self):
        result = ingest_text("  hello world  ")
        assert result == "hello world"

    def test_ingest_text_passthrough(self):
        result = ingest_text(SAMPLE_INVOICE)
        assert "Acme Corp" in result


class TestPipeline:
    @patch("agents.extractor.extract")
    @patch("storage.db.insert_record", return_value=1)
    @patch("storage.db.init_db")
    def test_pipeline_success_path(self, mock_init, mock_insert, mock_extract):
        mock_extract.return_value = _make_extraction(0.9)
        state = run(filename="test.txt", raw_text=SAMPLE_INVOICE)
        assert state["record_id"] == 1
        assert state["status"] == "store_success"
        assert state["retry_count"] == 0

    @patch("agents.extractor.extract")
    @patch("storage.db.insert_record", return_value=2)
    @patch("storage.db.init_db")
    def test_pipeline_retry_then_flag(self, mock_init, mock_insert, mock_extract):
        # Always returns low confidence → retries → flags
        mock_extract.return_value = _make_extraction(0.5)
        state = run(filename="test.txt", raw_text=SAMPLE_INVOICE)
        assert state["record_id"] == 2
        assert state["status"] == "store_flagged"
        assert state["retry_count"] == MAX_RETRIES
