# Document AI Orchestrator

Ingests unstructured documents (invoices, contracts) and extracts structured data using Claude as the LLM, LangGraph as the orchestration layer, and FastAPI as the API surface.

## Architecture

```
POST /ingest
      │
  [Ingestion]          pdfplumber or plain text decode
      │
  [Extraction]         Claude (claude-sonnet-4-6) via instructor → guaranteed Pydantic schema
      │
  [Validation]         field-level confidence scoring
      │
   ┌──┴──┐
retry?   store
  │        │
[Extract]  SQLite → response
(strict mode)
```

### Orchestration — LangGraph

The pipeline is a compiled LangGraph state machine with five nodes:

| Node | Responsibility |
|------|----------------|
| `ingest` | Parse raw bytes or text into clean document string |
| `extract` | Call Claude via `instructor`, return `DocumentExtraction` |
| `validate` | Score field-level confidence, decide next action |
| `retry` | Increment retry counter, route back to `extract` with strict prompt |
| `store` | Persist result to SQLite, return `record_id` |

For this scope a plain `Pipeline` class would also work. LangGraph was chosen to make the routing logic explicit and to show how this system extends naturally to parallel extraction, multiple document types, or human-in-the-loop checkpoints.

### Why `instructor`

Raw LLM responses require JSON parsing that can fail on malformed output. `instructor` wraps the Anthropic SDK and enforces the Pydantic schema at the call site — no try/except JSON parsing, no hallucinated field names.

### Confidence scoring

Confidence is **field-level**, not document-level. A document with a clear vendor but an ambiguous amount gets a targeted retry, not a full re-extraction.

| Min field confidence | Action |
|---------------------|--------|
| ≥ 0.7 | `SUCCESS` — store and return |
| 0.4–0.69 | `retry` with strict prompt (max 2 retries) |
| < 0.4 | `FLAGGED` — store with flag, no further retry |

### Foldering approach

Every layer has a single responsibility and no cross-layer imports. Prompts live in `prompts/*.md` — never hardcoded in Python — so they can be iterated without touching logic. `CLAUDE.md` documents the folder rules so any AI tool (Claude Code, Cursor) can navigate the project without hallucinating structure. This is the same discipline I apply to all projects: structure is partly for the developer, partly for the AI.

### What I used AI for vs what I wrote manually

| AI-assisted | Written manually |
|-------------|-----------------|
| Prompt engineering (`prompts/*.md`) | Orchestration logic (`orchestrator/graph.py`) |
| Initial scaffold structure | Validation routing (`agents/validator.py`) |
| | Storage layer (`storage/db.py`) |
| | Confidence threshold decisions |
| | All tests |

## Folder structure

```
doc-orchestrator/
├── api/
│   └── main.py            FastAPI endpoints + UI serving
├── orchestrator/
│   └── graph.py           LangGraph state machine
├── agents/
│   ├── ingestion.py       PDF/text parser
│   ├── extractor.py       Claude + instructor
│   └── validator.py       Confidence routing
├── prompts/
│   ├── extract.md         Default system prompt
│   └── extract_strict.md  Strict-mode prompt (used on retry)
├── storage/
│   └── db.py              SQLite handler
├── models/
│   └── schema.py          Pydantic models
├── ui/
│   └── index.html         Single-page UI (no framework, no build step)
├── tests/
│   └── test_extractor.py
├── data/                  SQLite DB (git-ignored)
├── .env.example
├── CLAUDE.md
└── README.md
```

## Setup

Requires Python 3.11+.

```bash
# 1. Clone and enter the project
git clone https://github.com/oguzhan-kara/doc-orchestrator.git
cd doc-orchestrator

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
cp .env.example .env
# Open .env and set ANTHROPIC_API_KEY=sk-ant-...

# 5. Start the server
uvicorn api.main:app --reload --port 8000
```

Open `http://localhost:8000` — the UI loads automatically.

## Usage

### Web UI

- **Paste Text** tab — paste invoice or contract text, click Extract
- **Upload File** tab — upload a PDF or `.txt` file
- Results appear with field-level breakdown and a status badge (`success` / `flagged`)
- **Recent Documents** table shows all processed records

### REST API

#### POST `/ingest/file`
Upload a PDF or `.txt` file.

```bash
curl -X POST http://localhost:8000/ingest/file \
  -F "file=@invoice.pdf"
```

#### POST `/ingest/text`
Send raw document text as JSON.

```bash
curl -X POST http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Invoice from Acme Corp...", "filename": "acme.txt"}'
```

#### GET `/results/{doc_id}`
Fetch a single extracted record.

#### GET `/results`
List all records (`?limit=50&offset=0`).

#### GET `/health`
Health check.

Swagger UI available at `http://localhost:8000/docs`.

## Running tests

```bash
pytest tests/ -v
```

Tests mock the LLM and DB layers — no API key required.

---

## Sample inputs

Use these to manually test the UI or API.

### Case 1 — Clean invoice (expects `status: success`)

```
INVOICE

Vendor:         Acme Software Ltd
Invoice #:      INV-2024-0042
Invoice Date:   2024-03-15
Due Date:       2024-04-15

Bill To:
  Zaigo.ai Inc
  123 Market Street, San Francisco, CA 94105

Description:
  AI consulting services — March 2024        $8,000.00
  Infrastructure setup (one-time)            $1,200.00

Subtotal:   $9,200.00
Tax (18%):  $1,656.00
Total Due:  $10,856.00

Payment terms: Net 30
Bank: Chase — Routing 021000021 — Account 4892736510
```

Expected output:
| Field | Value |
|-------|-------|
| vendor | Acme Software Ltd |
| amount | $10,856.00 |
| date | 2024-03-15 |
| due_date | 2024-04-15 |
| category | invoice |
| invoice_number | INV-2024-0042 |

---

### Case 2 — Ambiguous contract (expects `status: flagged` or retry)

```
SERVICE AGREEMENT

This agreement is entered into between the parties as of the first Monday
of the upcoming quarter. The service provider will deliver consulting work
related to data infrastructure. Compensation will be discussed and finalized
upon project scoping. Payment schedules are subject to negotiation.

Both parties agree to maintain confidentiality throughout the engagement.
```

Expected behaviour: low confidence on `amount`, `date`, `due_date`, `invoice_number` → triggers retry → stored as `flagged`.

---

### Case 3 — Minimal receipt (expects `status: success` with some nulls)

```
Receipt #R-8821
Date: 29 Apr 2024
Vendor: Digital Ocean LLC
Amount Charged: $48.00
```

Expected output: `vendor`, `amount`, `date`, `invoice_number` extracted; `due_date` null; `category: receipt`.
