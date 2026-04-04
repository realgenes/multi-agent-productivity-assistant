import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.schemas import ChatResponse, ToolResult, WorkflowPlan, WorkflowStep
from app.services.agents import KnowledgeAgent, PlanningAgent, ScheduleAgent, TaskAgent
from app.services.llm import GeminiService
from app.services.tools import LocalProductivityTools, MCPToolRegistry


class ProductivityOrchestrator:
    def __init__(self, llm: GeminiService, db: Session, mcp_servers_json: str | None):
        self.llm = llm
        self.db = db
        self.local_tools = LocalProductivityTools(db)
        self.mcp_tools = MCPToolRegistry(mcp_servers_json)
        self.planner = PlanningAgent(llm)
        self.specialists = {
            TaskAgent.name: TaskAgent(),
            ScheduleAgent.name: ScheduleAgent(),
            KnowledgeAgent.name: KnowledgeAgent(),
        }

    def _all_tools(self) -> list[dict[str, Any]]:
        return self.local_tools.list_tools() + self.mcp_tools.list_tools()

    def _canonical_tool_name(self, tool_name: str) -> str:
        return tool_name.split(".")[-1]

    def _tool_group(self, tool_name: str) -> str:
        normalized = self._canonical_tool_name(tool_name).lower()
        qualified = tool_name.lower()
        if any(token in normalized for token in ["create_task", "task_create", "subtask_create", "tasks_bulk_create"]):
            return "task_create"
        if any(token in normalized for token in ["list_tasks", "task_get", "tasks_get", "task_list"]):
            return "task_read"
        if any(token in normalized for token in ["create_note", "note_create"]):
            return "note_create"
        if any(token in normalized for token in ["list_notes", "note_get", "note_list"]):
            return "note_read"
        if "schedule_summary" in normalized or "calendar" in qualified or "event" in normalized:
            return "schedule"
        return normalized

    def _tool_definition(self, tool_name: str) -> dict[str, Any] | None:
        canonical = self._canonical_tool_name(tool_name).lower()
        qualified = tool_name.lower()
        for tool in self._all_tools():
            raw_name = tool["name"].lower()
            raw_qualified = tool.get("qualified_name", tool["name"]).lower()
            if qualified in {raw_name, raw_qualified} or canonical in {raw_name, raw_qualified}:
                return tool
        return None

    def _pick_tool(self, step_action: str, user_message: str) -> tuple[str, dict[str, Any]]:
        action = step_action.lower()
        message = user_message.lower()

        dynamic_tool = self._match_dynamic_tool(step_action)
        if dynamic_tool:
            return dynamic_tool, {}

        message_dynamic_tool = self._match_dynamic_tool(user_message)
        message_dynamic_group = self._tool_group(message_dynamic_tool) if message_dynamic_tool else None

        if any(term in message for term in ["create a task", "create task", "add a task", "add task", "make a task", "new task"]):
            if message_dynamic_tool and message_dynamic_group == "task_create":
                return message_dynamic_tool, {}
            return "create_task", {}
        if any(term in message for term in ["create a note", "create note", "save a note", "save note", "write a note"]):
            if message_dynamic_tool and message_dynamic_group == "note_create":
                return message_dynamic_tool, {}
            return "create_note", {}
        if "list task" in action or "retrieve task" in action:
            return "list_tasks", {}
        if "create_task" in action or "create task" in action or "add task" in action:
            if message_dynamic_tool and message_dynamic_group == "task_create":
                return message_dynamic_tool, {}
            return "create_task", {}
        if "schedule_summary" in action or "schedule" in action or "timeline" in action:
            if message_dynamic_tool and message_dynamic_group == "schedule":
                return message_dynamic_tool, {}
            return "schedule_summary", {}
        if "create_note" in action or ("note" in action and ("create" in action or "save" in action)):
            if message_dynamic_tool and message_dynamic_group == "note_create":
                return message_dynamic_tool, {}
            return "create_note", {}
        if "list_notes" in action or "note" in action or "knowledge" in action:
            return "list_notes", {}
        return "list_tasks", {}

    def _match_dynamic_tool(self, text: str) -> str | None:
        normalized = text.lower()
        for tool in self._all_tools():
            raw_name = tool["name"].lower()
            qualified_name = tool.get("qualified_name", raw_name).lower()
            if raw_name in normalized or qualified_name in normalized:
                return tool.get("qualified_name", tool["name"])
        return None

    def _extract_tool_args(self, message: str, tool_name: str) -> dict[str, Any]:
        prompt = f"""
Extract arguments for tool `{tool_name}` from the user request.
Return valid JSON only.

Tool name: {tool_name}
User request: {message}

Rules:
- For create_task return {{"title": "...", "description": "...", "due_date": "..."}}.
- For create_note return {{"title": "...", "content": "..."}}.
- For unknown or external tools, infer a best-effort arguments object from the request.
- For read-only tools return {{}}.
"""
        try:
            payload = self.llm.generate_json(prompt)
            if isinstance(payload, dict) and payload:
                return payload
        except Exception:
            pass
        return self._fallback_tool_args(message, tool_name)

    def _run_tool(self, tool_name: str, args: dict[str, Any]) -> Any:
        local_tool_names = {tool["name"] for tool in self.local_tools.list_tools()}
        local_qualified_names = {tool["qualified_name"] for tool in self.local_tools.list_tools()}
        if tool_name in local_tool_names or tool_name in local_qualified_names:
            return self.local_tools.execute(tool_name, args)
        return self.mcp_tools.execute(tool_name, args)

    def _final_answer(self, message: str, plan: WorkflowPlan, results: list[ToolResult]) -> str:
        prompt = f"""
You are a helpful productivity assistant.
Create a concise final response for the user.

User request:
{message}

Execution plan:
{plan.model_dump_json(indent=2)}

Tool results:
{json.dumps([result.model_dump() for result in results], indent=2)}
"""
        return self.llm.generate_text(prompt).strip()

    def handle(self, message: str) -> ChatResponse:
        plan = self.planner.create_plan(message, self._all_tools())
        tool_results: list[ToolResult] = []
        executed_groups: set[str] = set()

        for tool_name in self._tool_sequence_from_message(message):
            tool_group = self._tool_group(tool_name)
            if tool_group in executed_groups:
                continue
            args = self._extract_tool_args(message, tool_name)
            result = self._run_tool(tool_name, args)
            tool_results.append(ToolResult(tool_name=tool_name, result=result))
            executed_groups.add(tool_group)

        for step in plan.steps:
            specialist = self.specialists.get(step.agent)
            if specialist is None:
                continue
            tool_name, _ = self._pick_tool(step.action, message)
            tool_group = self._tool_group(tool_name)
            if tool_group in executed_groups:
                continue
            args = self._extract_tool_args(message, tool_name)
            result = self._run_tool(tool_name, args)
            tool_results.append(ToolResult(tool_name=tool_name, result=result))
            executed_groups.add(tool_group)

        if not plan.steps:
            plan = WorkflowPlan(
                summary=re.sub(r"\s+", " ", message).strip()[:100],
                steps=[WorkflowStep(agent="task-agent", action="list_tasks", rationale="Fallback action when intent is unclear.")],
            )

        answer = self._final_answer(message, plan, tool_results)
        return ChatResponse(answer=answer, plan=plan, tool_results=tool_results)

    def _tool_sequence_from_message(self, message: str) -> list[str]:
        lowered = message.lower()
        ordered: list[str] = []
        ordered_groups: set[str] = set()
        dynamic_tool = self._match_dynamic_tool(message)
        dynamic_group = self._tool_group(dynamic_tool) if dynamic_tool else None

        if any(term in lowered for term in ["create a task", "create task", "add a task", "add task", "make a task", "new task"]):
            if dynamic_tool and dynamic_group == "task_create":
                ordered.append(dynamic_tool)
                ordered_groups.add(dynamic_group)
            else:
                ordered.append("create_task")
                ordered_groups.add("task_create")
        if any(term in lowered for term in ["create a note", "create note", "save a note", "save note", "write a note"]):
            if dynamic_tool and dynamic_group == "note_create" and dynamic_group not in ordered_groups:
                ordered.append(dynamic_tool)
                ordered_groups.add(dynamic_group)
            elif "note_create" not in ordered_groups:
                ordered.append("create_note")
                ordered_groups.add("note_create")
        if any(term in lowered for term in ["schedule", "calendar", "timeline", "upcoming workload", "summarize my schedule"]):
            if dynamic_tool and dynamic_group == "schedule" and dynamic_group not in ordered_groups:
                ordered.append(dynamic_tool)
                ordered_groups.add(dynamic_group)
            elif "schedule" not in ordered_groups:
                ordered.append("schedule_summary")
                ordered_groups.add("schedule")
        if dynamic_tool and dynamic_group not in ordered_groups:
            ordered.append(dynamic_tool)
            ordered_groups.add(dynamic_group)
        if not ordered and any(term in lowered for term in ["list tasks", "show tasks", "my tasks"]):
            ordered.append("list_tasks")
        if not ordered and any(term in lowered for term in ["list notes", "show notes", "my notes"]):
            ordered.append("list_notes")
        return ordered

    def _fallback_tool_args(self, message: str, tool_name: str) -> dict[str, Any]:
        cleaned = re.sub(r"\s+", " ", message).strip()
        normalized_tool = self._canonical_tool_name(tool_name).lower()
        lower_tool_name = tool_name.lower()
        due_match = re.search(r"\bby ([^.!,]+)", cleaned, re.IGNORECASE)
        due_value = due_match.group(1).strip() if due_match else None
        if normalized_tool == "create_task":
            title = cleaned
            for prefix in [
                "create a task to",
                "create task to",
                "add a task to",
                "add task to",
                "make a task to",
                "new task to",
                "create a task",
                "create task",
                "add a task",
                "add task",
            ]:
                if cleaned.lower().startswith(prefix):
                    title = cleaned[len(prefix):].strip()
                    break
            title = re.sub(r"\bby [^.!,]+", "", title, flags=re.IGNORECASE).strip(" .:-")
            return {
                "title": (title[:255] or "Untitled task"),
                "description": cleaned[:500],
                "due_date": due_value,
            }
        if "todoist" in lower_tool_name and any(token in normalized_tool for token in ["task_create", "create_task"]):
            content = cleaned
            for prefix in [
                "create a task to",
                "create task to",
                "add a task to",
                "add task to",
                "make a task to",
                "new task to",
                "create a task",
                "create task",
                "add a task",
                "add task",
            ]:
                if cleaned.lower().startswith(prefix):
                    content = cleaned[len(prefix):].strip()
                    break
            content = re.sub(r"\bby [^.!,]+", "", content, flags=re.IGNORECASE).strip(" .:-")
            payload = {
                "content": content[:255] or "Untitled task",
                "description": cleaned[:500],
            }
            if due_value:
                payload["due_string"] = due_value
            return payload
        if normalized_tool == "create_note":
            return {
                "title": cleaned[:80] or "Quick note",
                "content": cleaned,
            }
        return {"query": cleaned}
