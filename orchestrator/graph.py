from typing import Optional, TypedDict
from langgraph.graph import StateGraph, END
from models.schema import DocumentExtraction, DocumentRecord, ExtractionStatus
from agents import ingestion, extractor, validator
from storage import db


class OrchestratorState(TypedDict):
    filename: str
    raw_text: str
    extraction: Optional[DocumentExtraction]
    retry_count: int
    status: str
    record_id: Optional[int]
    error: Optional[str]


# ── nodes ──────────────────────────────────────────────────────────────────────

def ingest_node(state: OrchestratorState) -> OrchestratorState:
    return {**state, "raw_text": ingestion.ingest_text(state["raw_text"])}


def extract_node(state: OrchestratorState) -> OrchestratorState:
    strict = state["retry_count"] > 0
    try:
        result = extractor.extract(state["raw_text"], strict=strict)
        return {**state, "extraction": result}
    except Exception as exc:
        return {**state, "error": str(exc)}


def validate_node(state: OrchestratorState) -> OrchestratorState:
    if state.get("error") or state["extraction"] is None:
        return {**state, "status": "store_flagged"}
    decision = validator.route(state["extraction"], state["retry_count"])
    return {**state, "status": decision}


def store_node(state: OrchestratorState) -> OrchestratorState:
    ext = state["extraction"]
    is_flagged = state["status"] == "store_flagged"

    record = DocumentRecord(
        filename=state["filename"],
        vendor=ext.vendor.value if ext else None,
        amount=ext.amount.value if ext else None,
        date=ext.date.value if ext else None,
        due_date=ext.due_date.value if ext else None,
        category=ext.category.value if ext else None,
        invoice_number=ext.invoice_number.value if ext else None,
        min_confidence=ext.min_confidence() if ext else 0.0,
        status=ExtractionStatus.FLAGGED if is_flagged else ExtractionStatus.SUCCESS,
        retry_count=state["retry_count"],
    )
    record_id = db.insert_record(record)
    return {**state, "record_id": record_id}


def increment_retry(state: OrchestratorState) -> OrchestratorState:
    return {**state, "retry_count": state["retry_count"] + 1}


# ── routing ────────────────────────────────────────────────────────────────────

def route_after_validate(state: OrchestratorState) -> str:
    return state["status"]


# ── graph ──────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(OrchestratorState)

    g.add_node("ingest", ingest_node)
    g.add_node("extract", extract_node)
    g.add_node("validate", validate_node)
    g.add_node("retry", increment_retry)
    g.add_node("store", store_node)

    g.set_entry_point("ingest")
    g.add_edge("ingest", "extract")
    g.add_edge("extract", "validate")
    g.add_conditional_edges(
        "validate",
        route_after_validate,
        {
            "retry": "retry",
            "store_success": "store",
            "store_flagged": "store",
        },
    )
    g.add_edge("retry", "extract")
    g.add_edge("store", END)

    return g.compile()


pipeline = build_graph()


def run(filename: str, raw_text: str) -> OrchestratorState:
    initial: OrchestratorState = {
        "filename": filename,
        "raw_text": raw_text,
        "extraction": None,
        "retry_count": 0,
        "status": "",
        "record_id": None,
        "error": None,
    }
    return pipeline.invoke(initial)
