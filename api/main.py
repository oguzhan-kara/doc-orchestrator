import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from models.schema import TextIngestRequest, DocumentRecord
from orchestrator.graph import run
from storage import db
from agents.ingestion import ingest_file

_UI_PATH = Path(__file__).parent.parent / "ui" / "index.html"

app = FastAPI(
    title="Document AI Orchestrator",
    description="Ingests invoices and contracts, extracts structured data via Claude.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db.init_db()


@app.get("/", include_in_schema=False)
def ui():
    return FileResponse(_UI_PATH)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest/file", response_model=DocumentRecord)
async def ingest_file_endpoint(file: UploadFile = File(...)):
    """Accept a PDF or plain-text file and run the extraction pipeline."""
    content = await file.read()
    raw_text = ingest_file(content, file.filename)

    if not raw_text:
        raise HTTPException(status_code=422, detail="Could not extract text from file.")

    state = run(filename=file.filename, raw_text=raw_text)
    return _state_to_response(state)


@app.post("/ingest/text", response_model=DocumentRecord)
def ingest_text_endpoint(body: TextIngestRequest):
    """Accept raw text and run the extraction pipeline."""
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="Text body is empty.")

    state = run(filename=body.filename, raw_text=body.text)
    return _state_to_response(state)


@app.get("/results/{doc_id}", response_model=DocumentRecord)
def get_result(doc_id: int):
    record = db.get_record(doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return record


@app.get("/results", response_model=list[DocumentRecord])
def list_results(limit: int = 50, offset: int = 0):
    return db.list_records(limit=limit, offset=offset)


def _state_to_response(state: dict) -> DocumentRecord:
    if state.get("error") and state.get("record_id") is None:
        raise HTTPException(status_code=500, detail=state["error"])
    record = db.get_record(state["record_id"])
    if record is None:
        raise HTTPException(status_code=500, detail="Storage write failed.")
    return record
