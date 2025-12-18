# ADK MCP Ping

Keep-alive pings for Google ADK MCP connections.

## Problem

When running Google ADK agents with MCP servers behind AWS ALB (or similar load balancers), long-running tool executions can timeout due to the load balancer's idle connection timeout (default 60s for ALB).

## Solution

`adk-mcp-ping` provides a drop-in replacement for `McpToolset` that automatically sends periodic MCP ping requests to keep connections alive during long-running operations.

## Installation

```bash
pip install adk-mcp-ping
```

Or with uv:
```bash
uv add adk-mcp-ping
```

## Usage

Simply replace `McpToolset` with `PingEnabledMcpToolset`:

```python
# Before
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

agent = LlmAgent(
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="http://server:8000/mcp",
            ),
        )
    ],
)

# After
from adk_mcp_ping import PingEnabledMcpToolset

agent = LlmAgent(
    tools=[
        PingEnabledMcpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="http://server:8000/mcp",
            ),
            ping_interval=50.0,  # Send ping every 50s (< ALB 60s timeout)
        )
    ],
)
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ping_interval` | 50.0 | Interval in seconds between keep-alive pings |

The default `ping_interval` of 50 seconds is suitable for AWS ALB's default 60-second idle timeout. Adjust based on your load balancer's configuration.

## How It Works

1. When a session is created, a background task starts that sends periodic MCP ping requests
2. Pings are JSON-RPC requests: `{"jsonrpc":"2.0","id":N,"method":"ping"}`
3. The server responds immediately (even during tool execution), resetting idle timers
4. When the session closes, the ping task is automatically cancelled

## Requirements

- Python 3.10+
- google-adk >= 0.1.0
- mcp >= 1.0.0
- Server tools must be async (use `await asyncio.sleep()` not `time.sleep()`)

## License

MIT
