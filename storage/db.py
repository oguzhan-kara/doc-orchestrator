import sqlite3
from pathlib import Path
from typing import Optional
from models.schema import DocumentRecord, ExtractionStatus

DB_PATH = Path(__file__).parent.parent / "data" / "documents.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                filename       TEXT    NOT NULL,
                vendor         TEXT,
                amount         TEXT,
                date           TEXT,
                due_date       TEXT,
                category       TEXT,
                invoice_number TEXT,
                min_confidence REAL    NOT NULL,
                status         TEXT    NOT NULL,
                retry_count    INTEGER DEFAULT 0,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def insert_record(record: DocumentRecord) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO documents
                (filename, vendor, amount, date, due_date, category,
                 invoice_number, min_confidence, status, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.filename,
                record.vendor,
                record.amount,
                record.date,
                record.due_date,
                record.category,
                record.invoice_number,
                record.min_confidence,
                record.status.value,
                record.retry_count,
            ),
        )
        return cursor.lastrowid


def get_record(doc_id: int) -> Optional[DocumentRecord]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
    if row is None:
        return None
    return _row_to_record(row)


def list_records(limit: int = 50, offset: int = 0) -> list[DocumentRecord]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_record(r) for r in rows]


def _row_to_record(row: sqlite3.Row) -> DocumentRecord:
    return DocumentRecord(
        id=row["id"],
        filename=row["filename"],
        vendor=row["vendor"],
        amount=row["amount"],
        date=row["date"],
        due_date=row["due_date"],
        category=row["category"],
        invoice_number=row["invoice_number"],
        min_confidence=row["min_confidence"],
        status=ExtractionStatus(row["status"]),
        retry_count=row["retry_count"],
        created_at=row["created_at"],
    )
