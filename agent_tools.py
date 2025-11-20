# agent_tools.py
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import uuid4

import requests


DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

PROJECT_MEMORY_PATH = DATA_DIR / "project_memory.json"
HANDS_PATH = DATA_DIR / "hands.json"


def _load_project_memory() -> List[Dict[str, Any]]:
    if PROJECT_MEMORY_PATH.exists():
        try:
            return json.loads(PROJECT_MEMORY_PATH.read_text())
        except Exception:  # pragma: no cover - defensive
            return []
    return []


def _persist_project_memory(entries: List[Dict[str, Any]]):
    PROJECT_MEMORY_PATH.write_text(json.dumps(entries, indent=2))


def _load_hands() -> List[Dict[str, Any]]:
    if HANDS_PATH.exists():
        try:
            return json.loads(HANDS_PATH.read_text())
        except Exception:  # pragma: no cover - defensive
            return []
    return []


def _persist_hands(entries: List[Dict[str, Any]]):
    HANDS_PATH.write_text(json.dumps(entries, indent=2))


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


def _resolve_hand(identifier: Optional[str], hands: List[Dict[str, Any]], session_id: Optional[str]):
    if not identifier:
        return None

    ident_lower = identifier.lower()

    def _matches(hand: Dict[str, Any]) -> bool:
        return ident_lower in {hand.get("id", "").lower(), hand.get("name", "").lower()}

    # Prefer a session-local hand first, then any match.
    for hand in hands:
        if _matches(hand) and session_id and hand.get("session") == session_id:
            return hand
    for hand in hands:
        if _matches(hand):
            return hand
    return None


def _create_hand(name: str, goal: Optional[str], session_id: Optional[str]) -> str:
    name = (name or "").strip()
    if not name:
        return "Hand name is required."

    hands = _load_hands()
    hand_id = uuid4().hex[:8]
    record = {
        "id": hand_id,
        "name": name,
        "goal": (goal or "").strip(),
        "session": session_id,
        "tasks": [],
    }
    hands.append(record)
    _persist_hands(hands)
    return f"Created hand '{name}' (id: {hand_id})."


def _list_hands(session_id: Optional[str]) -> str:
    hands = _load_hands()
    if not hands:
        return "No hands yet. Create one with action=create_hand."

    summaries = []
    for hand in hands:
        scope = "session" if session_id and hand.get("session") == session_id else "shared"
        summaries.append(
            f"{hand.get('name')} (id: {hand.get('id')}, scope: {scope}) — "
            f"goal: {hand.get('goal') or 'n/a'}, tasks: {len(hand.get('tasks') or [])}"
        )
    return "\n".join(summaries)


def _add_task_to_hand(hand_ref: str, title: str, detail: Optional[str], session_id: Optional[str]) -> str:
    title = (title or "").strip()
    if not title:
        return "Task title is required."

    hands = _load_hands()
    hand = _resolve_hand(hand_ref, hands, session_id)
    if not hand:
        return "Hand not found."

    task_id = uuid4().hex[:8]
    task = {
        "id": task_id,
        "title": title,
        "detail": (detail or "").strip(),
        "status": "todo",
        "created": datetime.utcnow().isoformat() + "Z",
    }
    hand.setdefault("tasks", []).append(task)
    _persist_hands(hands)
    return f"Task '{title}' added to hand {hand.get('name')} (task id: {task_id})."


def _list_tasks(hand_ref: str, session_id: Optional[str]) -> str:
    hands = _load_hands()
    hand = _resolve_hand(hand_ref, hands, session_id)
    if not hand:
        return "Hand not found."

    tasks = hand.get("tasks") or []
    if not tasks:
        return f"No tasks for {hand.get('name')} (id: {hand.get('id')})."

    lines = []
    for t in tasks:
        detail = f" — {t['detail']}" if t.get("detail") else ""
        lines.append(f"[{t.get('status', 'todo')}] {t.get('title')} (id: {t.get('id')}){detail}")
    return "\n".join(lines)


def _update_task(hand_ref: str, task_ref: str, status: Optional[str], detail: Optional[str], session_id: Optional[str]) -> str:
    hands = _load_hands()
    hand = _resolve_hand(hand_ref, hands, session_id)
    if not hand:
        return "Hand not found."

    valid_status = {"todo", "doing", "done"}
    tasks = hand.get("tasks") or []
    for task in tasks:
        if task_ref and task_ref.lower() in {task.get("id", "").lower(), task.get("title", "").lower()}:
            if status:
                norm_status = status.lower()
                if norm_status not in valid_status:
                    return "Status must be todo/doing/done."
                task["status"] = norm_status
            if detail:
                task["detail"] = detail
            _persist_hands(hands)
            return f"Updated task {task.get('id')} in hand {hand.get('name')} to {task.get('status')}"
    return "Task not found."


def _remove_task(hand_ref: str, task_ref: str, session_id: Optional[str]) -> str:
    hands = _load_hands()
    hand = _resolve_hand(hand_ref, hands, session_id)
    if not hand:
        return "Hand not found."

    tasks = hand.get("tasks") or []
    filtered = [t for t in tasks if task_ref.lower() not in {t.get("id", "").lower(), t.get("title", "").lower()}]
    if len(filtered) == len(tasks):
        return "Task not found."

    hand["tasks"] = filtered
    _persist_hands(hands)
    return f"Removed task {task_ref} from hand {hand.get('name')}"


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
        if name == "hands":
            action = (args.get("action") or "list_hands").lower()
            if action == "create_hand":
                return _create_hand(
                    name=str(args.get("name", "")),
                    goal=str(args.get("goal", "")) or None,
                    session_id=session_id,
                )
            if action == "list_hands":
                return _list_hands(session_id=session_id)
            if action == "add_task":
                return _add_task_to_hand(
                    hand_ref=str(args.get("hand", "")),
                    title=str(args.get("title", "")),
                    detail=str(args.get("detail", "")) or None,
                    session_id=session_id,
                )
            if action == "list_tasks":
                return _list_tasks(
                    hand_ref=str(args.get("hand", "")),
                    session_id=session_id,
                )
            if action == "update_task":
                return _update_task(
                    hand_ref=str(args.get("hand", "")),
                    task_ref=str(args.get("task", "")),
                    status=str(args.get("status", "")) or None,
                    detail=str(args.get("detail", "")) or None,
                    session_id=session_id,
                )
            if action == "remove_task":
                return _remove_task(
                    hand_ref=str(args.get("hand", "")),
                    task_ref=str(args.get("task", "")),
                    session_id=session_id,
                )
            return "Unknown hands action"
        return f"Unknown tool: {name}"
    except Exception as e:  # pragma: no cover - defensive guard
        return f"Tool error: {e}"
