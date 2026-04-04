# Multi-Agent Productivity Assistant

This project is a Python API and browser UI for a multi-agent productivity assistant built with the Google Generative AI library, FastAPI, SQLite, Cloud Run deployment assets, GitHub Actions, and live MCP tool integration over Streamable HTTP and stdio.

## Cloud-ready MCP scope

For Cloud Run, the recommended supported MCP setup is:

- Todoist via `@greirson/mcp-todoist`
- Notion via `@notionhq/notion-mcp-server`
- Google Calendar disabled for now

This is because the local Google Calendar setup depends on interactive OAuth and local credential files, which is not a clean Cloud Run fit yet.

## Cloud Run MCP requirements

The Cloud Run container now installs Node.js so the service can launch stdio MCP servers with `npx`.

Cloud deployment expects these additional GitHub secrets:

- `TODOIST_API_TOKEN`
- `NOTION_TOKEN`

The GitHub Actions workflow builds `MCP_SERVERS_JSON` from those secrets and injects it into Cloud Run as an environment variable.

## GitHub Actions secrets

Required:

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `GCP_RUNTIME_SERVICE_ACCOUNT`
- `TODOIST_API_TOKEN`
- `NOTION_TOKEN`

## Verify deployed MCP

After redeploy, check:

- `/api/v1/config`
- `/api/v1/mcp/tools`

A successful cloud MCP config should show:

- `mcp_servers_configured: 2`
- reachable `todoist`
- reachable `notion`

## Local development

Local development can still use `MCP_SERVERS_FILE=./mcp-servers.local.json`.
