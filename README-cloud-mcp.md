# Multi-Agent Productivity Assistant

This project is a Python API and browser UI for a multi-agent productivity assistant built with the Google Generative AI library, FastAPI, SQLite, Cloud Run deployment assets, GitHub Actions, and live MCP tool integration over Streamable HTTP and stdio.

## Cloud-ready integration scope

For Cloud Run, the production-ready integrations are:

- Todoist via globally installed `mcp-todoist`
- Notion via globally installed `notion-mcp-server`
- Google Calendar via direct Google Calendar API access using OAuth refresh tokens

Todoist and Notion stay on MCP. Google Calendar uses a native backend integration because interactive local OAuth and `npx`-driven MCP startup are not reliable for Cloud Run.

## Required GitHub secrets

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `GCP_RUNTIME_SERVICE_ACCOUNT`
- `TODOIST_API_TOKEN`
- `NOTION_TOKEN`
- `GOOGLE_CALENDAR_CLIENT_ID`
- `GOOGLE_CALENDAR_CLIENT_SECRET`
- `GOOGLE_CALENDAR_REFRESH_TOKEN`
- `GOOGLE_CALENDAR_ID`
- `GOOGLE_CALENDAR_TIMEZONE`

## Verify cloud integrations

After deploy, check:

- `/api/v1/config`
- `/api/v1/mcp/tools`

Expected:

- `google_calendar_configured: true`
- `mcp_servers_configured: 2`
- `todoist` reachable
- `notion` reachable
