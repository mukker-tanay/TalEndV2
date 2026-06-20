"""PostToolUse hook: ruff-format only the just-edited Python file.

Reads the hook JSON from stdin, pulls the edited path, and runs `ruff format` on
it when it's a .py file. Never fails the tool call (best-effort).
"""
import json
import subprocess
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

path = (data.get("tool_input") or {}).get("file_path") or ""
if path.endswith(".py"):
    try:
        subprocess.run(["python", "-m", "ruff", "format", path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
