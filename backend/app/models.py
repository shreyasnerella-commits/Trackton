from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from uuid import UUID

class SpanIngestPayload(BaseModel):
    trace_id: UUID
    span_id: UUID
    parent_span_id: Optional[UUID] = None
    agent_id: str
    tool_name: str
    input_hash: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float
    depth: int = 0
    status: str = "SUCCESS"
    metadata: Optional[Dict[str, Any]] = {}

class SpanNode(BaseModel):
    span_id: UUID
    trace_id: UUID
    parent_span_id: Optional[UUID]
    agent_id: str
    tool_name: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    depth: int
    status: str
    metadata: Dict[str, Any]
    children: List['SpanNode'] = []
