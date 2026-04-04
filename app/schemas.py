from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message to the productivity assistant.")


class ToolResult(BaseModel):
    tool_name: str
    result: Any


class WorkflowStep(BaseModel):
    agent: str
    action: str
    rationale: str


class WorkflowPlan(BaseModel):
    summary: str
    steps: List[WorkflowStep]


class ChatResponse(BaseModel):
    answer: str
    plan: WorkflowPlan
    tool_results: List[ToolResult]


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None


class TaskRead(TaskCreate):
    id: int
    status: str

    model_config = {"from_attributes": True}


class NoteCreate(BaseModel):
    title: str
    content: str


class NoteRead(NoteCreate):
    id: int

    model_config = {"from_attributes": True}
