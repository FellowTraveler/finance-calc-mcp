# finance-calc-mcp — MCP Protocol Compliance & Visibility Fixes

## Summary of Issues Found

Inspected via MCP Inspector v0.15.0. The server's tools are fully correct and functional,
but several protocol and packaging issues cause it to render poorly in Claude Desktop and
fail to connect cleanly in the inspector. Fix all items below.

---

## Issue 1: Protocol Version Not Pinned — SDK Negotiates Too New (CRITICAL)

### Current behavior
`pyproject.toml` pins `mcp>=1.0.0` with no upper bound. The installed SDK version
supports protocol versions up to `2025-11-25`. When Claude Desktop (or the inspector)
requests a recent version like `2025-03-26`, the Python MCP SDK echoes it back
faithfully — and Claude Desktop renders the server as a **toggle** (on/off) rather than
the proper **"Add from finance-calculator → [tool submenu]"** picker.

This is confirmed by comparing against rs_wallet, which hard-codes `2024-11-05` and
gets the submenu rendering. The submenu rendering is tied to clients and servers
agreeing on the `2024-11-05` protocol era behavior.

### Fix — pin the negotiated protocol version in `server.py`

In `run_mcp_server()`, before calling `server.run(...)`, monkeypatch the SDK's supported
versions list to force negotiation to `2024-11-05`:

```python
def run_mcp_server():
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    import mcp.shared.version as _mcp_version
    import asyncio

    # Force protocol negotiation to 2024-11-05 so Claude Desktop renders
    # individual tool submenus instead of a dumb on/off toggle.
    _mcp_version.SUPPORTED_PROTOCOL_VERSIONS = ["2024-11-05"]

    server = Server("finance-calculator")
    # ... rest of setup unchanged
```

### Why this is safe
The `2024-11-05` protocol version fully supports tools/list, tools/call, and all
features this server uses. You are not losing any functionality — only gaining correct
UI rendering in Claude Desktop.

### Longer-term fix
Pin the SDK version in `pyproject.toml` so a `uv` upgrade doesn't silently break this:
```toml
dependencies = ["mcp>=1.0.0,<2.0.0"]
```
And track SDK major versions intentionally rather than floating.

---

## Issue 2: Inspector Connection Fails When Launched via Shell Wrapper (HIGH)

### Current behavior
The Claude Desktop config entry uses a shell wrapper:
```json
"finance-calculator": {
    "command": "/bin/bash",
    "args": ["-lc", "uvx finance-calc-mcp"]
}
```
When this same invocation is typed into the MCP Inspector UI manually, the inspector
fails to connect. Additionally, clicking the **Environment Variables** section in the
inspector causes the entire page to go blank — a known inspector v0.15.0 bug triggered
by certain command configurations.

### Fix — use the direct binary path in the inspector

First, find the installed binary:
```bash
uvx finance-calc-mcp --help  # confirms it works
which finance-calc-mcp        # if installed globally via pipx/uv tool
# or locate via uv:
uv tool dir                   # shows tool install root
```

Then connect the inspector directly:
```
Command:   /Users/au/.local/bin/finance-calc-mcp    # (adjust to actual path)
Arguments: (none)
```

No shell wrapper needed. The inspector pre-fills the form correctly when the command is
a direct binary path, matching the behavior you see with rs_wallet.

### For Claude Desktop config — also update to use direct binary

```json
"finance-calculator": {
    "command": "/Users/au/.local/bin/finance-calc-mcp"
}
```

This is cleaner, avoids the bash wrapper, and gives Claude Desktop the same clean
invocation path.

To find the exact binary path on your machine:
```bash
uv tool install finance-calc-mcp   # if not already installed as a tool
uv tool list                        # shows installed tools and versions
ls $(uv tool dir)/finance-calc-mcp/bin/  # shows the actual binary
```

---

## Issue 3: No Tool Annotations (MEDIUM)

### Current behavior
All 10 tools in the `list_tools()` handler have no `annotations` field. The MCP spec
defines `ToolAnnotations` to help clients understand safety characteristics of tools
— whether they are read-only, destructive, idempotent, etc.

### Fix
Add an `annotations` key to each `Tool(...)` definition. The MCP Python SDK's `Tool`
type accepts an `annotations` parameter. Since this server uses the low-level SDK and
constructs `Tool` objects directly, add it as an extra field (Pydantic models with
`extra='allow'` will pass it through):

```python
Tool(
    name="calculate",
    description="...",
    inputSchema={...},
    annotations={
        "title": "Calculate Expression",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
),
```

Recommended annotations by tool:

| Tool | readOnlyHint | destructiveHint | idempotentHint | title |
|------|-------------|----------------|----------------|-------|
| `calculate` | true | false | true | Calculate Expression |
| `gross_margin` | true | false | true | Gross Margin |
| `us_income_tax_estimate` | true | false | true | US Income Tax Estimate |
| `self_employment_tax` | true | false | true | Self-Employment Tax |
| `depreciation` | true | false | true | Depreciation Schedule |
| `payroll_summary` | true | false | true | Payroll Summary |
| `loan_amortization` | true | false | true | Loan Amortization |
| `percent_change` | true | false | true | Percent Change |
| `break_even` | true | false | true | Break-Even Analysis |
| `currency_format` | true | false | true | Format Currency |

All tools are pure calculations with no side effects, so `readOnlyHint: true` and
`destructiveHint: false` are correct for all of them.

---

## Issue 4: No `instructions` Field in Server Initialization (LOW)

### Current behavior
`server.create_initialization_options()` is called with no `instructions` argument.
The MCP spec allows servers to provide a natural-language description of what the server
does and how to use it — clients like Claude Desktop surface this as context.

### Fix
Pass instructions when initializing:

```python
async def _run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(
                # instructions visible to Claude and the user
            ),
        )
```

But `create_initialization_options` doesn't take instructions directly in the low-level
SDK — set it on the server object instead:

```python
server = Server(
    "finance-calculator",
    instructions=(
        "Business, financial, and tax calculator. Use these tools to evaluate math "
        "expressions, compute gross margins, estimate US federal income tax, calculate "
        "self-employment tax, generate depreciation schedules, summarize payroll costs, "
        "amortize loans, compute percent changes, run break-even analyses, and format "
        "currency values. All tools are read-only calculations with no side effects."
    )
)
```

---

## Issue 5: Server Version Not Pulled From Package Metadata (LOW)

### Current behavior
The SDK derives version from `importlib.metadata` automatically, but it uses the `mcp`
package version rather than `finance-calc-mcp`. This means the version shown in the
inspector's `serverInfo` is the MCP SDK version, not your server's version.

### Fix
Pass your server's version explicitly:

```python
import importlib.metadata

server = Server(
    "finance-calculator",
    version=importlib.metadata.version("finance-calc-mcp"),
    instructions="...",
)
```

---

## Summary Checklist

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| 1 | Protocol version floats to latest — breaks Claude Desktop submenu UI | CRITICAL | `server.py` `run_mcp_server()` |
| 2 | Shell wrapper command breaks inspector connection and crashes env vars panel | HIGH | `claude_desktop_config.json` + inspector usage |
| 3 | Tool annotations missing — clients can't assess tool safety | MEDIUM | `server.py` `list_tools()` |
| 4 | No server instructions provided to client | LOW | `server.py` `Server(...)` constructor |
| 5 | Server version reports MCP SDK version instead of `finance-calc-mcp` version | LOW | `server.py` `Server(...)` constructor |

Fix item 1 first — it is the single change that makes Claude Desktop render this server
correctly with individual tool visibility instead of a toggle.
