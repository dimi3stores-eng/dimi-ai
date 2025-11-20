# agent_tools.py
import json, os
from pathlib import Path

def handle_tool_call(name, args):
    try:
        if name == "read_file":
            p = Path(args.get("path","")).expanduser()
            if not p.exists(): return "File not found"
            return p.read_text()
        if name == "echo":
            return args.get("text","")
        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error: {e}"
