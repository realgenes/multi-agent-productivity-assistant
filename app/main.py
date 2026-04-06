from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, engine, get_db
from app.repositories import NoteRepository, TaskRepository, WorkflowRepository
from app.schemas import ChatRequest, NoteCreate, NoteRead, TaskCreate, TaskRead
from app.services.llm import GeminiService, LLMConfigurationError
from app.services.orchestrator import ProductivityOrchestrator
from app.services.tools import MCPToolRegistry

import os

print("RAW ENV:", os.getenv("GOOGLE_API_KEY"))

settings = get_settings()
Base.metadata.create_all(bind=engine)
static_dir = Path(__file__).parent / "static"

app = FastAPI(title="Multi-Agent Productivity Assistant", version="0.1.0")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_mcp_registry() -> MCPToolRegistry:
    return MCPToolRegistry(settings.resolved_mcp_servers_json())


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": settings.app_name}


@app.get("/api/v1/config")
def config_status():
    mcp_summary = []
    mcp_error = None
    try:
        mcp_summary = get_mcp_registry().summary()
    except Exception as exc:
        mcp_error = str(exc)
    return {
        "vertex_ai_enabled": settings.google_use_vertex_ai,
        "google_cloud_project_configured": bool(settings.google_cloud_project),
        "google_cloud_location": settings.google_cloud_location,
        "model": settings.google_genai_model,
        "developer_api_key_configured": bool(settings.google_api_key),
        "google_calendar_configured": settings.google_calendar_configured(),
        "mcp_servers_configured": len(mcp_summary),
        "mcp_servers": mcp_summary,
        "mcp_config_error": mcp_error,
    }


@app.get("/api/v1/mcp/tools")
def list_mcp_tools():
    try:
        return get_mcp_registry().list_tools()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to load MCP tools: {exc}") from exc


@app.post("/api/v1/chat")
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    try:
        llm = GeminiService(settings)
        orchestrator = ProductivityOrchestrator(
            llm=llm,
            db=db,
            settings=settings,
            mcp_servers_json=settings.resolved_mcp_servers_json(),
        )

        raw_response = orchestrator.handle(request.message)

        answer = ""
        plan = {}

        if isinstance(raw_response, dict):
            answer = raw_response.get("answer", "")
            plan = raw_response.get("plan", {})
        else:
            answer = getattr(raw_response, "answer", "")
            try:
                plan = raw_response.plan.model_dump()
            except Exception:
                plan = str(getattr(raw_response, "plan", {}))

        WorkflowRepository(db).create(
            user_message=request.message,
            plan=str(plan),
            outcome=str(answer),
        )

        tool_results = raw_response.get("tool_results", []) if isinstance(raw_response, dict) else []

        return {
            "answer": str(answer),
            "plan": plan,
            "tool_results": tool_results,
            "status": "ok"
        }

    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {exc}") from exc


@app.get("/api/v1/tasks", response_model=list[TaskRead])
def list_tasks(db: Session = Depends(get_db)):
    return TaskRepository(db).list_all()


@app.post("/api/v1/tasks", response_model=TaskRead)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    return TaskRepository(db).create(payload)


@app.patch("/api/v1/tasks/{task_id}/complete")
def complete_task(task_id: int, db: Session = Depends(get_db)):
    done = TaskRepository(db).complete(task_id)
    if not done:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "completed"}


@app.delete("/api/v1/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    deleted = TaskRepository(db).delete_by_id(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}


@app.get("/api/v1/notes", response_model=list[NoteRead])
def list_notes(db: Session = Depends(get_db)):
    return NoteRepository(db).list_all()


@app.post("/api/v1/notes", response_model=NoteRead)
def create_note(payload: NoteCreate, db: Session = Depends(get_db)):
    return NoteRepository(db).create(payload)


@app.delete("/api/v1/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    deleted = NoteRepository(db).delete_by_id(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"status": "deleted"}



print("API KEY:", settings.google_api_key)
print("VERTEX:", settings.google_use_vertex_ai)