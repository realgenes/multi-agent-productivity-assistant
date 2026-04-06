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


from pydantic import BaseModel
from typing import Any, Optional


class ChatResponse(BaseModel):
    answer: str
    plan: Any
    status: Optional[str] = None

    model_config = {
        "from_attributes": True
    }
class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    due_date: str | None = None

from datetime import datetime
from pydantic import BaseModel


class TaskRead(BaseModel):
    id: int
    title: str
    description: str | None = None
    due_date: datetime | None = None
    status: str = "pending"
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
class NoteCreate(BaseModel):
    title: str
    content: str


class NoteRead(NoteCreate):
    id: int

    model_config = {"from_attributes": True}

