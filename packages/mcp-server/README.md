# Quadfile MCP server

Read-only MCP wrapper for the public Quadfile friendly API.

**Default path:** paste `https://www.quadfile.org/api/mcp` as a Claude
custom connector (Settings → Connectors → Add custom connector). Streamable
HTTP, no API key. That is the URL for web, desktop, mobile, and Cowork.

This stdio file is for local development and Claude Code. One Node file, no
install (the package `quadfile-mcp`, version 0.2.0, is not published
to npm; run it from a clone of this repository). Stdio is newline-delimited
JSON-RPC.

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
    "quadfile": {
      "command": "node",
      "args": ["/absolute/path/to/quadfile/packages/mcp-server/bin/collegedata-mcp.js"]
    }
  }
}
```

If Claude reports `spawn node ENOENT`, set `command` to the path that
`which node` prints. Node 20 or newer. `QUADFILE_API_BASE` is optional and
defaults to `https://www.quadfile.org`. Point it at `http://localhost:3000`
when developing the friendly API locally.

Tools (same five as the hosted endpoint, `web/src/lib/mcp/tools.ts`):

- `search_schools` (`query`, optional `limit`)
- `get_school_facts` (`school_id`, optional `categories`)
- `compare_schools` (`school_ids`, optional `categories`, `fields`)
- `get_source_documents` (`school_id`)
- `get_field_dictionary` (optional `category`)

The `finance` category (endowment values and spending) is available through `get_school_facts` and `get_field_dictionary`, not `compare_schools`.

The server does not use a service-role key and exposes no write tools.
`api.quadfile.org` is PostgREST, not MCP — do not paste that host as a
connector URL.

## Using the data?

Tell us what you're building, researching, or using in your work.
A link and a sentence are plenty: https://www.quadfile.org/feedback.
You can also [open an issue](https://github.com/bolewood/collegedata-fyi/issues)
or [star this repository](https://github.com/bolewood/collegedata-fyi).
No account or response is required to use the data.
