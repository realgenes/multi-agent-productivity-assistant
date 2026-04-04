# Multi-Agent Productivity Assistant

This project is a Python API and browser UI for a multi-agent productivity assistant built with the Google Generative AI library, FastAPI, SQLite, Cloud Run deployment assets, GitHub Actions, and live MCP tool integration over Streamable HTTP and stdio.

## Cloud-ready MCP scope

For Cloud Run, the supported MCP setup is:

- Todoist via globally installed `mcp-todoist`
- Notion via globally installed `notion-mcp-server`
- Google Calendar disabled for now

These MCP packages are installed into the image at build time so Cloud Run does not rely on `npx` downloading packages at request time.

## Required GitHub secrets

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `GCP_RUNTIME_SERVICE_ACCOUNT`
- `TODOIST_API_TOKEN`
- `NOTION_TOKEN`

## Verify cloud MCP

After deploy, check:

- `/api/v1/config`
- `/api/v1/mcp/tools`

Expected:

- `mcp_servers_configured: 2`
- `todoist` reachable
- `notion` reachable
