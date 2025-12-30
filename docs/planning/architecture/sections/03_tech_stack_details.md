# 03. Technology Stack Details

## Core Technologies

*   **Runtime**: Python 3.12+ (Backend/Agents), Node.js 22 LTS (Frontend).
*   **Orchestration**: **LangGraph v1.x**. A stateful, graph-based library for building cyclic agent workflows.
*   **Async Workers**: **Celery 5.x** with **Redis 7.x** Broker. Handles background agent tasks.
*   **LLM Interface**: **LangChain 0.3+ / LiteLLM 1.x**.
*   **Protocol**: **Model Context Protocol (MCP)** SDK (Python & TS).
*   **Auth**: **Clerk** (User & Agent Identity).
*   **Database**: **Neo4j 5.x** (Community) or AuraDB.
*   **Sandboxing**: **E2B Code Interpreter SDK v1.x+**. Enforces "Side-Effect Containment" (network allowlist, resource caps).

## MCP Server Ecosystem
The Workbench connects to external tools via standardized MCP servers:
*   **`git-mcp`**: For all version control operations.
*   **`filesystem-mcp`**: For safe, scoped file access (respects `.mcpignore`).
*   **`postgres-mcp`**: For database querying (read-only by default for Planner).
*   **`brave-search-mcp`**: For web research (Planner only).

## Integration Points

*   **GitHub/GitLab**: Accessed via `git-mcp` server.
*   **Slack/Linear**: For notifying users of "Human-in-the-Loop" requests.
*   **Observability**: **Helicone** (Trace & Cost). Caches common queries to save tokens.
