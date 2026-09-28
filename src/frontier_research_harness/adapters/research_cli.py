"""JSON stdin/file access to the same tools used by MCP; no shell interpolation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .frontier_science_workspace import DEFAULT_DATABASE
from .research_tool_contracts import list_tool_contracts
from .research_tool_dispatch import dispatch_research_tool, tool_result_is_error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", help="Tool name, or 'tools' to inspect contracts")
    parser.add_argument("--input", type=Path, help="UTF-8 JSON arguments; default stdin")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    try:
        if args.tool == "tools":
            result = {"tools": list_tool_contracts()}
        else:
            raw = args.input.read_text(encoding="utf-8-sig") if args.input else sys.stdin.read()
            payload = json.loads(raw) if raw.strip() else {}
            if not isinstance(payload, dict):
                raise ValueError("tool arguments must be a JSON object")
            result = dispatch_research_tool(args.tool, payload, database=args.database)
            if tool_result_is_error(result):
                print(json.dumps(result, ensure_ascii=False))
                raise SystemExit(1)
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"status": "FAILED", "error_type": type(exc).__name__,
                          "message": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
