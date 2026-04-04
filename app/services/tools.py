import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app import schemas
from app.repositories import NoteRepository, TaskRepository
from app.services.mcp_client import MCPClientError, StdioMCPClient, StreamableHTTPMCPClient


@dataclass
class ToolContext:
    db: Session


class LocalProductivityTools:
    def __init__(self, db: Session):
        self.tasks = TaskRepository(db)
        self.notes = NoteRepository(db)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "create_task",
                "description": "Create a structured task entry in the database.",
                "parameters": {"title": "string", "description": "string|null", "due_date": "string|null"},
                "server": "local",
                "qualified_name": "local.create_task",
            },
            {
                "name": "list_tasks",
                "description": "List known tasks ordered by most recent.",
                "parameters": {},
                "server": "local",
                "qualified_name": "local.list_tasks",
            },
            {
                "name": "create_note",
                "description": "Create a note entry in the database.",
                "parameters": {"title": "string", "content": "string"},
                "server": "local",
                "qualified_name": "local.create_note",
            },
            {
                "name": "list_notes",
                "description": "List note records ordered by most recent.",
                "parameters": {},
                "server": "local",
                "qualified_name": "local.list_notes",
            },
            {
                "name": "schedule_summary",
                "description": "Summarize upcoming work from stored tasks.",
                "parameters": {},
                "server": "local",
                "qualified_name": "local.schedule_summary",
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        normalized_name = tool_name.split(".")[-1]
        if normalized_name == "create_task":
            record = self.tasks.create(schemas.TaskCreate(**arguments))
            return schemas.TaskRead.model_validate(record).model_dump()
        if normalized_name == "list_tasks":
            return [schemas.TaskRead.model_validate(task).model_dump() for task in self.tasks.list_all()]
        if normalized_name == "create_note":
            record = self.notes.create(schemas.NoteCreate(**arguments))
            return schemas.NoteRead.model_validate(record).model_dump()
        if normalized_name == "list_notes":
            return [schemas.NoteRead.model_validate(note).model_dump() for note in self.notes.list_all()]
        if normalized_name == "schedule_summary":
            tasks = [schemas.TaskRead.model_validate(task).model_dump() for task in self.tasks.list_all()]
            if not tasks:
                return {"summary": "No tasks are stored yet."}
            due_lines = [f"{task['title']} (status: {task['status']}, due: {task['due_date'] or 'unspecified'})" for task in tasks]
            return {"summary": "Upcoming workload:\n" + "\n".join(due_lines)}
        raise ValueError(f"Unsupported tool: {tool_name}")


class MCPToolRegistry:
    def __init__(self, mcp_servers_json: str | None):
        try:
            self._server_specs = json.loads(mcp_servers_json) if mcp_servers_json else []
        except json.JSONDecodeError as exc:
            raise MCPClientError(f"Invalid MCP_SERVERS_JSON configuration: {exc}") from exc

    def list_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for spec in self._server_specs:
            transport = spec.get("transport", "static")
            if transport in {"streamable_http", "http"} and spec.get("url"):
                client = StreamableHTTPMCPClient(spec)
                for tool in client.list_tools():
                    tools.append(
                        {
                            "name": tool["name"],
                            "qualified_name": f"{spec['name']}.{tool['name']}",
                            "description": tool.get("description", f"MCP tool from {spec['name']}"),
                            "parameters": tool.get("inputSchema", tool.get("parameters", {})),
                            "server": spec["name"],
                            "transport": transport,
                        }
                    )
                continue
            if transport == "stdio" and spec.get("command"):
                client = StdioMCPClient(spec)
                try:
                    for tool in client.list_tools():
                        tools.append(
                            {
                                "name": tool["name"],
                                "qualified_name": f"{spec['name']}.{tool['name']}",
                                "description": tool.get("description", f"MCP tool from {spec['name']}"),
                                "parameters": tool.get("inputSchema", tool.get("parameters", {})),
                                "server": spec["name"],
                                "transport": transport,
                            }
                        )
                finally:
                    client.close()
                continue
            for tool in spec.get("tools", []):
                tools.append(
                    {
                        "name": tool["name"],
                        "qualified_name": f"{spec['name']}.{tool['name']}",
                        "description": tool.get("description", f"MCP tool from {spec.get('name', 'server')}"),
                        "parameters": tool.get("parameters", {}),
                        "server": spec.get("name"),
                        "transport": transport,
                    }
                )
        return tools

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        requested_server, requested_name = self._split_tool_name(tool_name)
        for spec in self._server_specs:
            if requested_server and spec.get("name") != requested_server:
                continue
            transport = spec.get("transport", "static")
            if transport in {"streamable_http", "http"} and spec.get("url"):
                client = StreamableHTTPMCPClient(spec)
                available_tools = {tool["name"] for tool in client.list_tools()}
                if requested_name in available_tools:
                    result = client.call_tool(requested_name, arguments)
                    return {
                        "server": spec["name"],
                        "tool": requested_name,
                        "transport": transport,
                        "result": result,
                    }
            if transport == "stdio" and spec.get("command"):
                client = StdioMCPClient(spec)
                try:
                    available_tools = {tool["name"] for tool in client.list_tools()}
                    if requested_name in available_tools:
                        result = client.call_tool(requested_name, arguments)
                        return {
                            "server": spec["name"],
                            "tool": requested_name,
                            "transport": transport,
                            "result": result,
                        }
                finally:
                    client.close()
            for tool in spec.get("tools", []):
                if tool["name"] == requested_name:
                    return {
                        "status": "configured_only",
                        "message": f"Tool '{requested_name}' is declared in configuration but does not have a live transport yet.",
                        "arguments": arguments,
                        "server": spec.get("name"),
                    }
        raise ValueError(f"Unknown MCP tool: {tool_name}")

    def summary(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for spec in self._server_specs:
            record = {
                "name": spec.get("name"),
                "transport": spec.get("transport", "static"),
                "url": spec.get("url"),
                "configured": True,
            }
            try:
                tools = self._list_tools_for_server(spec)
                record["reachable"] = True
                record["tool_count"] = len(tools)
                record["tools"] = [tool["name"] for tool in tools]
            except MCPClientError as exc:
                record["reachable"] = False
                record["tool_count"] = 0
                record["tools"] = []
                record["error"] = str(exc)
            items.append(record)
        return items

    def _list_tools_for_server(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        transport = spec.get("transport", "static")
        if transport in {"streamable_http", "http"} and spec.get("url"):
            return StreamableHTTPMCPClient(spec).list_tools()
        if transport == "stdio" and spec.get("command"):
            client = StdioMCPClient(spec)
            try:
                return client.list_tools()
            finally:
                client.close()
        return spec.get("tools", [])

    def _split_tool_name(self, tool_name: str) -> tuple[str | None, str]:
        if "." in tool_name:
            server_name, raw_name = tool_name.split(".", 1)
            return server_name, raw_name
        return None, tool_name

