import re
from sqlalchemy.orm import Session
from app.config import Settings
from app.services.tools import LocalProductivityTools, MCPToolRegistry
from app.repositories import DuplicateError


class ProductivityOrchestrator:
    def __init__(self, llm, db: Session, settings: Settings, mcp_servers_json: str | None):
        self.db = db
        self.settings = settings
        self.local_tools = LocalProductivityTools(db, settings)
        self.mcp_tools = MCPToolRegistry(mcp_servers_json)

    def _fallback_tool_args(self, message: str, tool_name: str) -> dict:
        cleaned = re.sub(r"\s+", " ", message).strip()
        lowered = cleaned.lower()

        if tool_name == "create_task":
            title = cleaned
            for prefix in [
                "create a task to", "create task to", "add a task to", "add task to",
                "make a task to", "new task to", "create a task", "create task",
                "add a task", "add task"
            ]:
                if lowered.startswith(prefix):
                    title = cleaned[len(prefix):].strip()
                    break

            title = re.sub(r"\bby [^.!,]+", "", title, flags=re.IGNORECASE).strip(" .:-")

            return {
                "title": title or "Untitled task",
                "description": cleaned,
                "due_date": None
            }

        if tool_name == "create_note":
            title = cleaned
            for prefix in [
                "create a note titled", "create note titled", "add a note titled", "add note titled",
                "save a note titled", "save note titled", "new note titled",
                "create a note about", "create note about", "add a note about",
                "create a note", "create note", "add a note", "add note",
                "save a note", "save note", "new note", "capture a note",
            ]:
                if lowered.startswith(prefix):
                    title = cleaned[len(prefix):].strip().strip('"\'')
                    break
            # Truncate to first sentence or 80 chars for the title
            title = re.split(r"[.!?\n]", title)[0].strip()[:80] or "Quick note"
            return {
                "title": title,
                "content": cleaned
            }

        return {}

    def _extract_delete_target(self, message: str) -> str | None:
        """Returns None for bulk delete (all), or the title string for single delete."""
        cleaned = re.sub(r"\s+", " ", message).strip()
        lowered = cleaned.lower()

        # Bulk delete patterns: "delete all tasks", "delete tasks", "remove all notes", etc.
        bulk_patterns = [
            r"^(delete|remove)\s+all\s+(tasks?|notes?)$",
            r"^(delete|remove)\s+(tasks?|notes?)$",
            r"^clear\s+all\s+(tasks?|notes?)$",
            r"^clear\s+(tasks?|notes?)$",
        ]
        for pattern in bulk_patterns:
            if re.match(pattern, lowered):
                return None  # signals bulk delete

        # Single delete: strip the verb+noun prefix to get the title
        for prefix in [
            "delete the task", "remove the task", "delete task",  "remove task",
            "delete the note", "remove the note", "delete note",  "remove note",
        ]:
            if lowered.startswith(prefix):
                return cleaned[len(prefix):].strip().strip('"\'')

        return cleaned

    def handle(self, message: str) -> dict:
        tool_results = []
        lowered = message.lower()

        # Delete intents — check before create so "delete task" doesn't also trigger create
        is_delete = any(kw in lowered for kw in ["delete", "remove"])

        if is_delete and "task" in lowered:
            title = self._extract_delete_target(message)
            if title is None:
                count = self.local_tools.tasks.delete_all()
                return {"answer": f"Deleted all {count} task(s).", "plan": {"steps": []}, "tool_results": []}
            deleted = self.local_tools.tasks.delete_by_title(title)
            answer = f"Task '{title}' deleted." if deleted else f"No task found with title '{title}'."
            return {"answer": answer, "plan": {"steps": []}, "tool_results": []}

        if is_delete and "note" in lowered:
            title = self._extract_delete_target(message)
            if title is None:
                count = self.local_tools.notes.delete_all()
                return {"answer": f"Deleted all {count} note(s).", "plan": {"steps": []}, "tool_results": []}
            deleted = self.local_tools.notes.delete_by_title(title)
            answer = f"Note '{title}' deleted." if deleted else f"No note found with title '{title}'."
            return {"answer": answer, "plan": {"steps": []}, "tool_results": []}

        # 1. Logic for Tasks
        if "task" in lowered:
            args = self._fallback_tool_args(message, "create_task")
            try:
                task = self.local_tools.execute("create_task", args)
                tool_results.append({"tool_name": "create_task", "result": {"output": args}})
            except DuplicateError as e:
                return {
                    "answer": str(e),
                    "plan": {"steps": []},
                    "tool_results": []
                }

        # 2. Logic for Notes — only if explicitly asking to create/add/save a note
        note_keywords = ["create a note", "add a note", "save a note", "new note", "capture a note"]
        if any(kw in lowered for kw in note_keywords):
            args = self._fallback_tool_args(message, "create_note")
            try:
                self.local_tools.execute("create_note", args)
                tool_results.append({"tool_name": "create_note", "result": {"output": args}})
            except DuplicateError as e:
                return {
                    "answer": str(e),
                    "plan": {"steps": []},
                    "tool_results": []
                }

        # 3. Final Return (The UI reads this)
        return {
            "answer": f"I've processed your request: {message}",
            "plan": {"steps": tool_results},
            "tool_results": tool_results
        }
