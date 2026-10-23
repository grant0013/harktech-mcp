"""
Run the Hark Tech MCP server on your own machine or in Docker.

The hosted server at https://harktech.co.uk/mcp is the easiest way to use
Hark Tech (add it as a remote connector, nothing to install). This entry
point runs the same tools locally, calling Hark Tech's public API at
https://harktech.co.uk instead of the workshop's internal backend.

  python run_local.py                 # stdio (for desktop MCP clients)
  python run_local.py --http          # streamable HTTP on 0.0.0.0:8003/mcp

Environment:
  HARKTECH_BACKEND   API base URL (default https://harktech.co.uk)
  HARKTECH_MCP_PORT  HTTP port for --http (default 8003)
"""

from __future__ import annotations

import os
import sys

# server.py reads HARKTECH_BACKEND at import time, so set it first.
os.environ.setdefault("HARKTECH_BACKEND", "https://harktech.co.uk")

import server  # noqa: E402


def main() -> None:
    if "--http" in sys.argv[1:]:
        import uvicorn
        uvicorn.run(server.app, host="0.0.0.0", port=server.PORT, log_level="info")
    else:
        server.server.run("stdio")


if __name__ == "__main__":
    main()
