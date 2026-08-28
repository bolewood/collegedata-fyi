# CollegeData.FYI MCP server

Read-only MCP wrapper for the public CollegeData.FYI friendly API. One Node
file, no install, no API key. Stdio is newline-delimited JSON-RPC — the
framing Claude Desktop and other MCP clients speak.

```bash
node packages/mcp-server/bin/collegedata-mcp.js
```

Claude Desktop does not run from this repository. Put an **absolute path**
in `claude_desktop_config.json` (macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`; Windows:
`%APPDATA%\Claude\claude_desktop_config.json`), then fully quit and reopen
Claude:

```json
{
  "mcpServers": {
    "collegedata": {
      "command": "node",
      "args": ["/absolute/path/to/collegedata-fyi/packages/mcp-server/bin/collegedata-mcp.js"]
    }
  }
}
```

If Claude reports `spawn node ENOENT`, set `command` to the full path from
`which node`. Node 20 or newer. `COLLEGEDATA_API_BASE` is optional and
defaults to `https://www.collegedata.fyi`.

Tools:

- `search_schools`
- `get_school_facts`
- `compare_schools`
- `get_source_documents`
- `get_field_dictionary`

The server does not use a service-role key and exposes no write tools.
