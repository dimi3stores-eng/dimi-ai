# agent_tools.py
import json, os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests


PROJECT_MEMORY_PATH = Path("project_memory.json")


def _load_project_memory() -> List[Dict[str, Any]]:
    if PROJECT_MEMORY_PATH.exists():
        try:
            return json.loads(PROJECT_MEMORY_PATH.read_text())
        except Exception:  # pragma: no cover - defensive
            return []
    return []


def _persist_project_memory(entries: List[Dict[str, Any]]):
    PROJECT_MEMORY_PATH.write_text(json.dumps(entries, indent=2))


def _save_memory_note(note: str, tag: Optional[str], session_id: Optional[str]) -> str:
    note = (note or "").strip()
    if not note:
        return "No note provided to store."

    entries = _load_project_memory()
    record = {"note": note, "tag": tag or None, "session": session_id or None}
    entries.append(record)
    _persist_project_memory(entries)
    return "Saved to project memory."


def _search_memory(query: str, limit: int = 5, session_id: Optional[str] = None) -> str:
    entries = _load_project_memory()
    if not entries:
        return "Project memory is empty."

    query_lower = (query or "").lower()

    def _score(entry: Dict[str, Any]) -> int:
        score = 0
        if query_lower and query_lower in (entry.get("note", "").lower()):
            score += 2
        if query_lower and query_lower in (entry.get("tag", "") or "").lower():
            score += 1
        if session_id and entry.get("session") == session_id:
            score += 1
        return score

    ranked = sorted(entries, key=_score, reverse=True)
    top = ranked[: max(limit, 1)]
    formatted = []
    for item in top:
        tag = f"[{item['tag']}] " if item.get("tag") else ""
        owner = f"(session: {item['session']}) " if item.get("session") else ""
        formatted.append(f"{tag}{owner}{item['note']}")
    return "\n".join(formatted)


def _fetch_url(url: str, limit: int = 4000, use_tor: Optional[bool] = None, tor_proxy: Optional[str] = None) -> str:
    if not url.lower().startswith(("http://", "https://")):
        return "Only http:// or https:// URLs are supported, including .onion hosts over Tor."

    parsed = urlparse(url)
    is_onion = parsed.hostname.endswith(".onion") if parsed.hostname else False
    should_use_tor = use_tor if use_tor is not None else is_onion
    proxy = tor_proxy or os.getenv("TOR_PROXY", "socks5h://127.0.0.1:9050")
    proxies = {"http": proxy, "https": proxy} if should_use_tor else None

    try:
        res = requests.get(url, timeout=15, proxies=proxies)
        res.raise_for_status()
    except Exception as exc:  # pragma: no cover - network dependent
        return f"Failed to fetch URL: {exc}"

    body = res.text
    if len(body) > limit:
        return body[:limit] + f"\n... (truncated, total {len(body)} chars)"
    return body


def handle_tool_call(name: str, args: Dict[str, Any], session_id: Optional[str] = None):
    try:
        if name == "read_file":
            p = Path(args.get("path", "")).expanduser()
            if not p.exists():
                return "File not found"
            return p.read_text()
        if name == "echo":
            return args.get("text", "")
        if name == "fetch_url":
            return _fetch_url(
                str(args.get("url", "")),
                limit=int(args.get("limit", 4000)),
                use_tor=args.get("use_tor"),
                tor_proxy=str(args.get("tor_proxy", "")) or None,
            )
        if name == "project_memory":
            action = (args.get("action") or "fetch").lower()
            if action == "save":
                return _save_memory_note(
                    note=str(args.get("note", "")),
                    tag=str(args.get("tag", "")) or None,
                    session_id=session_id,
                )
            if action == "fetch":
                return _search_memory(
                    query=str(args.get("query", "")),
                    limit=int(args.get("limit", 5)),
                    session_id=session_id,
                )
            return "Unknown project_memory action"
        return f"Unknown tool: {name}"
    except Exception as e:  # pragma: no cover - defensive guard
        return f"Tool error: {e}"
