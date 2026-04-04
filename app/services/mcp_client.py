import json
import os
import subprocess
from typing import Any

import httpx


class MCPClientError(RuntimeError):
    """Raised when communication with an MCP server fails."""


class StreamableHTTPMCPClient:
    def __init__(self, spec: dict[str, Any]):
        self.name = spec["name"]
        self.url = spec["url"]
        self.timeout = float(spec.get("timeout_seconds", 20))
        self.protocol_version = spec.get("protocol_version", "2025-11-25")
        self.extra_headers = spec.get("headers", {})
        self.session_id: str | None = None
        self.initialized = False
        self._request_id = 0

    def list_tools(self) -> list[dict[str, Any]]:
        self.initialize()
        payload = self._request("tools/list", {})
        return payload.get("tools", [])

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        self.initialize()
        payload = self._request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )
        return payload

    def initialize(self) -> None:
        if self.initialized:
            return
        result, headers = self._send_request(
            method="initialize",
            params={
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": {
                    "name": "multi-agent-productivity-assistant",
                    "version": "0.1.0",
                },
            },
            include_session_header=False,
        )
        self.protocol_version = result.get("protocolVersion", self.protocol_version)
        self.session_id = headers.get("Mcp-Session-Id") or headers.get("mcp-session-id")
        self._send_notification("notifications/initialized", {})
        self.initialized = True

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        result, _ = self._send_request(method=method, params=params, include_session_header=True)
        return result

    def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        headers = self._headers(include_session_header=bool(self.session_id))
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.url, json=message, headers=headers)
            response.raise_for_status()

    def _send_request(self, method: str, params: dict[str, Any], include_session_header: bool) -> tuple[dict[str, Any], httpx.Headers]:
        self._request_id += 1
        message = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        headers = self._headers(include_session_header=include_session_header)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.url, json=message, headers=headers)
                if response.status_code == 404 and self.session_id:
                    self.session_id = None
                    self.initialized = False
                    raise MCPClientError(f"MCP session expired for server '{self.name}'. Retry the request.")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MCPClientError(f"MCP server '{self.name}' request failed: {exc}") from exc

        payload = self._parse_response_payload(response)
        if "error" in payload:
            error = payload["error"]
            raise MCPClientError(
                f"MCP server '{self.name}' returned error {error.get('code')}: {error.get('message')}"
            )
        return payload.get("result", {}), response.headers

    def _headers(self, include_session_header: bool) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Mcp-Protocol-Version": self.protocol_version,
        }
        headers.update({str(key): str(value) for key, value in self.extra_headers.items()})
        if include_session_header and self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def _parse_response_payload(self, response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            data_lines = []
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    data_lines.append(line[5:].strip())
            if not data_lines:
                raise MCPClientError(f"MCP server '{self.name}' returned an empty event stream.")
            return json.loads(data_lines[-1])
        return response.json()


class StdioMCPClient:
    def __init__(self, spec: dict[str, Any]):
        self.name = spec["name"]
        self.command = spec["command"]
        self.args = [str(arg) for arg in spec.get("args", [])]
        self.timeout = float(spec.get("timeout_seconds", 20))
        self.protocol_version = spec.get("protocol_version", "2025-11-25")
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in spec.get("env", {}).items()})
        self.env = env
        self.process: subprocess.Popen[str] | None = None
        self._request_id = 0
        self.initialized = False

    def list_tools(self) -> list[dict[str, Any]]:
        self.initialize()
        payload = self._request("tools/list", {})
        return payload.get("tools", [])

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        self.initialize()
        payload = self._request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )
        return payload

    def initialize(self) -> None:
        if self.initialized:
            return
        self._ensure_process()
        result = self._request(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": {
                    "name": "multi-agent-productivity-assistant",
                    "version": "0.1.0",
                },
            },
        )
        self.protocol_version = result.get("protocolVersion", self.protocol_version)
        self._send_notification("notifications/initialized", {})
        self.initialized = True

    def close(self) -> None:
        if not self.process:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def _ensure_process(self) -> None:
        if self.process and self.process.poll() is None:
            return
        try:
            self.process = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env=self.env,
            )
        except OSError as exc:
            raise MCPClientError(f"Failed to start MCP server '{self.name}': {exc}") from exc

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = self._send_request(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": method,
                "params": params,
            }
        )
        if "error" in payload:
            error = payload["error"]
            raise MCPClientError(
                f"MCP server '{self.name}' returned error {error.get('code')}: {error.get('message')}"
            )
        return payload.get("result", {})

    def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        self._write_message(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            }
        )

    def _send_request(self, message: dict[str, Any]) -> dict[str, Any]:
        self._write_message(message)
        return self._read_message()

    def _write_message(self, message: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            raise MCPClientError(f"MCP server '{self.name}' is not running.")
        self.process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def _read_message(self) -> dict[str, Any]:
        if not self.process or not self.process.stdout:
            raise MCPClientError(f"MCP server '{self.name}' is not running.")
        try:
            line = self.process.stdout.readline()
        except OSError as exc:
            raise MCPClientError(f"Failed to read from MCP server '{self.name}': {exc}") from exc
        if not line:
            stderr_text = ""
            if self.process.stderr:
                try:
                    stderr_text = self.process.stderr.read().strip()
                except OSError:
                    stderr_text = ""
            raise MCPClientError(
                f"MCP server '{self.name}' closed unexpectedly." + (f" Stderr: {stderr_text}" if stderr_text else "")
            )
        try:
            return json.loads(line.strip())
        except json.JSONDecodeError as exc:
            raise MCPClientError(f"MCP server '{self.name}' returned invalid JSON: {line.strip()}") from exc

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id
