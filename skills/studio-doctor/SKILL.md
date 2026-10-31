---
name: studio-doctor
description: Check the alifs-3d-agent setup on this PC (uv, Blender path, MCP addon enabled, port 9877 reachable, Playwright, GPU backend, fonts, workspace) and explain how to fix each failure. Use when the pipeline fails, Blender MCP won't connect, or after setting up a new PC.
---

# /studio-doctor

Run:

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"
```

It takes up to a minute (it starts Blender headless and exports a test Bangla poster).

- If `uv` itself isn't found, the PC hasn't been set up. Tell the user to run
  `powershell -ExecutionPolicy Bypass -File <repo>\scripts\setup.ps1` from their alifs-3d-agent clone.
- Show the PASS/FAIL list as-is, then for each FAIL give the fix line in plain words. Offer to run
  any fix that's a command (but setup.ps1 and winget installs need the user's OK first).
- Common cases:
  - **Port 9877 not reachable**: Blender isn't open, or its MCP server is on another port. Open
    Blender → N panel → MCP for Blender → check the port is 9877 → Start MCP Server.
  - **Port OK but MCP tools fail**: only one MCP client can talk to Blender at a time. Close other
    Claude Code / Claude Desktop / Cursor sessions using Blender, or remove a duplicate `blender`
    server from `claude mcp list`, then `/mcp` → reconnect `plugin:alifs-3d-agent:blender`.
  - **GPU backend mismatch**: re-run setup.ps1 to re-detect after a driver or GPU change.
- End with one line: all good, or how many failures remain.
