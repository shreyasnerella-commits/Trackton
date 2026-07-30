from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
from uuid import UUID

from app.database import supabase
from app.models import SpanIngestPayload, SpanNode
from app.anomaly import check_for_infinite_loop

app = FastAPI(title="Trackton Backend API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Trackton Backend"}

@app.post("/api/telemetry", status_code=status.HTTP_201_CREATED)
async def ingest_telemetry(span: SpanIngestPayload):
    is_loop = check_for_infinite_loop(
        supabase_client=supabase,
        trace_id=str(span.trace_id),
        agent_id=span.agent_id,
        tool_name=span.tool_name,
        input_hash=span.input_hash
    )
    
    final_status = "CIRCUIT_BROKEN" if is_loop else span.status
    
    record = span.dict()
    record["trace_id"] = str(record["trace_id"])
    record["span_id"] = str(record["span_id"])
    if record["parent_span_id"]:
        record["parent_span_id"] = str(record["parent_span_id"])
    record["status"] = final_status

    res = supabase.table("spans").insert(record).execute()
    
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to log telemetry span.")

    return {
        "status": "ok",
        "circuit_breaker_tripped": is_loop,
        "span_id": str(span.span_id)
    }

@app.get("/api/traces/{trace_id}", response_model=SpanNode)
async def get_trace_tree(trace_id: UUID):
    res = supabase.table("spans").select("*").eq("trace_id", str(trace_id)).execute()
    flat_spans = res.data

    if not flat_spans:
        raise HTTPException(status_code=404, detail="Trace ID not found.")

    nodes: Dict[str, Dict[str, Any]] = {}
    root_node = None

    for s in flat_spans:
        s["children"] = []
        nodes[s["span_id"]] = s

    for s in flat_spans:
        parent_id = s.get("parent_span_id")
        if parent_id and parent_id in nodes:
            nodes[parent_id]["children"].append(nodes[s["span_id"]])
        else:
            root_node = nodes[s["span_id"]]

    if not root_node:
        raise HTTPException(status_code=500, detail="Could not reconstruct trace tree root.")

    return root_node

@app.get("/api/traces")
async def list_traces():
    res = supabase.table("spans").select("trace_id, agent_id, status, created_at").is_("parent_span_id", "null").order("created_at", desc=True).execute()
    return res.data