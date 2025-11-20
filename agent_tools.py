# agent_tools.py
import json, os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests


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


def handle_tool_call(name: str, args: Dict[str, Any]):
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
        return f"Unknown tool: {name}"
    except Exception as e:  # pragma: no cover - defensive guard
        return f"Tool error: {e}"
