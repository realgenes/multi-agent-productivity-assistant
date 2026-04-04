import re
from dataclasses import dataclass
from typing import Any

from app.schemas import WorkflowPlan
from app.services.llm import GeminiService


@dataclass
class AgentDecision:
    name: str
    task: str
    rationale: str


class PlanningAgent:
    def __init__(self, llm: GeminiService):
        self.llm = llm

    def create_plan(self, message: str, tools: list[dict[str, Any]]) -> WorkflowPlan:
        prompt = f"""
You are the coordinator for a multi-agent productivity assistant.
Return valid JSON with this shape:
{{
  "summary": "short overall intent",
  "steps": [
    {{"agent": "task-agent|schedule-agent|knowledge-agent", "action": "specific action using an exact tool name when possible", "rationale": "why"}}
  ]
}}

When a tool is appropriate, include its exact tool name or qualified name in the action.
Available tools:
{tools}

User request:
{message}
"""
        try:
            payload = self.llm.generate_json(prompt)
            return WorkflowPlan.model_validate(payload)
        except Exception:
            lowered = message.lower()
            steps = []
            if any(term in lowered for term in ["create task", "add task", "make task", "new task", "todo", "task"]):
                action = "create_task" if any(term in lowered for term in ["create", "add", "make", "new"]) else "list_tasks"
                steps.append(
                    {
                        "agent": "task-agent",
                        "action": action,
                        "rationale": "The user is asking for task management support.",
                    }
                )
            if any(term in lowered for term in ["schedule", "calendar", "plan", "timeline"]):
                steps.append(
                    {
                        "agent": "schedule-agent",
                        "action": "schedule_summary",
                        "rationale": "The user is asking for planning or schedule help.",
                    }
                )
            if any(term in lowered for term in ["note", "remember", "save this", "knowledge"]):
                action = "create_note" if any(term in lowered for term in ["create", "save", "store", "write"]) else "list_notes"
                steps.append(
                    {
                        "agent": "knowledge-agent",
                        "action": action,
                        "rationale": "The user is asking for note or knowledge support.",
                    }
                )
            if not steps:
                steps.append(
                    {
                        "agent": "task-agent",
                        "action": "list_tasks",
                        "rationale": "Fallback action when intent is unclear.",
                    }
                )
            return WorkflowPlan.model_validate(
                {
                    "summary": re.sub(r"\s+", " ", message).strip()[:100],
                    "steps": steps,
                }
            )


class TaskAgent:
    name = "task-agent"

    def decide(self, user_message: str) -> AgentDecision:
        return AgentDecision(
            name=self.name,
            task="Handle task creation or task retrieval from structured storage.",
            rationale="This specialist manages action items and task records.",
        )


class ScheduleAgent:
    name = "schedule-agent"

    def decide(self, user_message: str) -> AgentDecision:
        return AgentDecision(
            name=self.name,
            task="Analyze schedule-related requests and summarize timeline data.",
            rationale="This specialist focuses on planning and upcoming work.",
        )


class KnowledgeAgent:
    name = "knowledge-agent"

    def decide(self, user_message: str) -> AgentDecision:
        return AgentDecision(
            name=self.name,
            task="Manage notes, context retrieval, and informational support.",
            rationale="This specialist handles notes and knowledge capture.",
        )
