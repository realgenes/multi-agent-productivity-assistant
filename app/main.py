from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, engine, get_db
from app.repositories import NoteRepository, TaskRepository, WorkflowRepository
from app.schemas import ChatRequest, ChatResponse, NoteCreate, NoteRead, TaskCreate, TaskRead
from app.services.llm import GeminiService, LLMConfigurationError
from app.services.orchestrator import ProductivityOrchestrator
from app.services.tools import MCPToolRegistry

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


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    try:
        llm = GeminiService(settings)
        orchestrator = ProductivityOrchestrator(
            llm=llm,
            db=db,
            settings=settings,
            mcp_servers_json=settings.resolved_mcp_servers_json(),
        )
        response = orchestrator.handle(request.message)
        WorkflowRepository(db).create(
            user_message=request.message,
            plan=response.plan.model_dump_json(),
            outcome=response.answer,
        )
        return response
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


@app.get("/api/v1/notes", response_model=list[NoteRead])
def list_notes(db: Session = Depends(get_db)):
    return NoteRepository(db).list_all()


@app.post("/api/v1/notes", response_model=NoteRead)
def create_note(payload: NoteCreate, db: Session = Depends(get_db)):
    return NoteRepository(db).create(payload)
