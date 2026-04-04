# Multi-Agent Productivity Assistant

This project is a Python API and browser UI for a multi-agent productivity assistant built with the Google Generative AI library, FastAPI, SQLite, Cloud Run deployment assets, GitHub Actions, and live MCP tool integration over Streamable HTTP and stdio.

## What it does

- Uses a primary coordinator agent to interpret the user's request.
- Routes work to specialist agents for tasks, schedules, knowledge, and external MCP tools.
- Stores structured data for tasks, notes, and workflow history in a database.
- Connects to configured MCP servers over Streamable HTTP or stdio for live `tools/list` and `tools/call` operations.
- Exposes both an API and a browser UI that can run locally or on Google Cloud Run.

## Actual MCP servers you can connect now

The codebase now supports real MCP servers such as:

- Todoist task server via `@greirson/mcp-todoist`
- Notion notes server via `@notionhq/notion-mcp-server`
- Google Calendar server via `@nchufa/calendar`

A starter config is included in [mcp-servers.sample.json](./mcp-servers.sample.json).

## MCP integration

You can configure MCP servers in either of two ways:

1. Put JSON directly in `MCP_SERVERS_JSON`
2. Point `MCP_SERVERS_FILE` to a JSON file such as `./mcp-servers.local.json`

Sample config file shape:

```json
[
  {
    "name": "todoist",
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@greirson/mcp-todoist"],
    "env": {
      "TODOIST_API_TOKEN": "replace-me"
    },
    "timeout_seconds": 30
  }
]
```

HTTP MCP servers are also supported:

```json
[
  {
    "name": "calendar",
    "transport": "streamable_http",
    "url": "http://localhost:3001/mcp",
    "headers": {
      "Authorization": "Bearer your-token"
    }
  }
]
```

You can inspect discovered tools at [http://localhost:8080/api/v1/mcp/tools](http://localhost:8080/api/v1/mcp/tools).

## Recommended local setup for your use case

1. Copy [mcp-servers.sample.json](./mcp-servers.sample.json) to `mcp-servers.local.json`
2. Replace placeholder tokens with your real credentials
3. In `.env`, set:

```env
MCP_SERVERS_FILE=./mcp-servers.local.json
```

4. Restart the app
5. Open [http://localhost:8080/api/v1/config](http://localhost:8080/api/v1/config)
6. Open [http://localhost:8080/api/v1/mcp/tools](http://localhost:8080/api/v1/mcp/tools)

## Important local prerequisite

Your machine currently has `node` but `npm` and `npx` are broken. Since the sample MCP servers use `npx`, you will need to repair your Node installation or reinstall Node.js so that `npm` and `npx` work.

Check with:

```bash
node --version
npm --version
npx --version
```

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and update the values.
4. If you are using Vertex AI locally, run:

```bash
gcloud auth application-default login
```

5. Start the API and UI:

```bash
uvicorn app.main:app --reload --port 8080
```

6. Open [http://localhost:8080](http://localhost:8080).
