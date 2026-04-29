# Document AI Orchestrator — Claude Context

## Project purpose
Extract structured fields (vendor, amount, dates, category) from invoice/contract documents using Claude as the LLM backbone, LangGraph for orchestration, and FastAPI as the API layer.

## Folder rules
- `agents/` — single-responsibility modules (ingest, extract, validate). No cross-imports between agents.
- `orchestrator/` — LangGraph state machine only. No business logic here; delegate to agents.
- `prompts/` — all LLM prompts live as Markdown files. Never hardcode prompts inside Python.
- `models/` — Pydantic schemas shared across layers. No DB or HTTP logic here.
- `storage/` — SQLite access only. No LLM or orchestration logic here.
- `api/` — HTTP layer only. No direct DB or LLM calls; delegate to orchestrator or storage.

## Confidence thresholds (agents/validator.py)
- >= 0.7 → SUCCESS
- 0.4–0.69 → retry (max 2 retries, then FLAGGED)
- < 0.4 → FLAGGED immediately

## Running
```bash
cp .env.example .env   # add ANTHROPIC_API_KEY
pip install -r requirements.txt
uvicorn api.main:app --reload
```

## Testing
```bash
pytest tests/
```

## API
- POST /ingest/file  — upload PDF or text file
- POST /ingest/text  — send raw text as JSON
- GET  /results/{id} — fetch one record
- GET  /results       — list all records
- GET  /health        — health check
