# Verified dependencies and sources

Last checked: 2026-11-12

## Package versions

| Package | Version | Notes |
|---|---|---|
| langgraph | 1.2.20 | Current 1.2 line |
| langgraph-checkpoint-sqlite | 3.1.3 | Latest. Import: `from langgraph.checkpoint.sqlite import SqliteSaver` |
| mcp | 2.3.0 | v2 has breaking changes from v1 |
| openai | 3.49.0 | v3 uses httpx2 and the OS certificate store |
| langsmith | 0.14.17 | Installed, tracing disabled |
| pydantic | 2.14.3 | No issues |

Exact versions of every installed package are in `requirements.lock`.

## Notes

### MCP Python SDK v2
- `FastMCP` was renamed `MCPServer`: `from mcp.server import MCPServer`. The old import path is removed.
- Most online tutorials are for v1 and will not work as written.
- The SDK no longer validates tool arguments before the handler runs. Our server must validate every argument itself.

### OpenAI Python SDK v3
- The core API is unchanged.
- It uses `httpx2` and the operating system's certificate store instead of `certifi`. A certificate error on the first live call points here.
- HTTP mocks built on the old `httpx` cannot intercept it. Tests use our own fake provider instead.

## Not yet verified
- Fed, ECB and BLS feed URLs, robots rules and rate limits (next step).
- OpenAI API key and billing limit (needed at M3).
- OANDA practice account and v20 token (needed at Q1).
- LangSmith pricing and data-retention settings (needed before tracing is enabled).

## Sources
- https://py.sdk.modelcontextprotocol.io/whats-new/
- https://py.sdk.modelcontextprotocol.io/migration/
- https://pypi.org/project/langgraph-checkpoint-sqlite
- https://developers.openai.com/api/docs/models/gpt-5.4-mini