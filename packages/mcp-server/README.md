# CollegeData.FYI MCP server

Read-only MCP wrapper for the public CollegeData.FYI friendly API.

```bash
COLLEGEDATA_API_BASE=https://www.collegedata.fyi node packages/mcp-server/bin/collegedata-mcp.js
```

Tools:

- `search_schools`
- `get_school_facts`
- `compare_schools`
- `get_source_documents`
- `get_field_dictionary`

The server does not use a service-role key and exposes no write tools.

