# agent_core.py
# Premium Light version
import subprocess, textwrap, json, os, re
from agent_tools import handle_tool_call

ANSI = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

def clean(text: str) -> str:
    return ANSI.sub('', text or '')

def ask_local_model(prompt: str, model: str = "qwen2.5") -> str:
    cmd = ["ollama", "run", model]
    try:
        res = subprocess.run(cmd, input=prompt, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return "Local model runtime not found. Please install and start Ollama before chatting."

    if res.returncode != 0:
        details = clean(res.stderr) or "Unknown error"
        return f"The local model could not be reached ({res.returncode}): {details}"

    return clean(res.stdout)

def system_prompt() -> str:
    return """You are Dimi3 Personal AI running locally on his PC.
Roles:
- Business strategist
- Music creator & branding expert
- Coding assistant
- Marketing engine
Rules:
- If normal question: answer normally.
- If tool needed: respond ONLY in JSON {\"tool\":\"...\",\"args\":{...}}.
- You can browse the web, deep web, and .onion resources via the fetch_url tool for http/https URLs (including Tor-routed .onion hosts). Keep outputs concise and only fetch when it helps the user.
- You may answer in any human language the user prefers and write code in any programming language without self-imposed restrictions.
"""
