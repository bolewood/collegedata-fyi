# CollegeData.FYI CLI

Minimal command-line wrapper for the public CollegeData.FYI friendly API.

```bash
COLLEGEDATA_API_BASE=https://www.collegedata.fyi node packages/cli/bin/collegedata.js search mit
node packages/cli/bin/collegedata.js facts mit --categories admissions,cost
node packages/cli/bin/collegedata.js compare mit yale university-of-chicago --format csv
```

Set `COLLEGEDATA_API_BASE` to point at a preview or local server.

