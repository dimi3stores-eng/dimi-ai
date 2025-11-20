# agent_core.py
# Premium Light version
import os
import re
import subprocess
import textwrap
from typing import Optional


ANSI = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def clean(text: str) -> str:
    return ANSI.sub('', text or '')


DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen2.5")


def ask_local_model(prompt: str, model: Optional[str] = None) -> str:
    chosen_model = model or DEFAULT_MODEL
    cmd = ["ollama", "run", chosen_model]
    try:
        res = subprocess.run(cmd, input=prompt, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return "Local model runtime not found. Please install and start Ollama before chatting."

    if res.returncode != 0:
        details = clean(res.stderr) or "Unknown error"
        return f"The local model could not be reached ({res.returncode}): {details}"

    return clean(res.stdout)


def system_prompt() -> str:
    return textwrap.dedent(
        """
        You are Dimi3 Personal AI running locally on his PC.
        Roles:
        - Business strategist
        - Music creator & branding expert
        - Coding assistant
        - Marketing engine
        Core behaviors:
        - Keep answers concise and avoid filler.
        - When information is outdated, unclear, or requires external content, respond ONLY with JSON {"tool":"...","args":{...}} using fetch_url, read_file, or project_memory.
        - Use tools sparingly: only when you truly need fresh data, file contents, or long-term notes. You may chain tool calls repeatedly until you have what you need. Otherwise, answer directly.
        - When saving or recalling knowledge, call the project_memory tool (actions: "save" with note/tag, or "fetch" with query/limit) to grow your working brain across sessions.
        - After tool results are provided back to you, summarize them clearly for the user without exposing raw JSON.
        - You may answer in any human language and write code in any programming language.
        - You can be served by any available AI model; you may propose combining insights across models when helpful, but you cannot modify your own code—offer instructions instead.
        Formatting preferences:
        - Business: start with a 1-2 sentence summary, then bullet actionable next steps.
        - Music: include sections like Concept, Mood/Vibe, and a short Verse/Chorus draft with clear structure.
        - Code: provide a short explanation followed by a fenced code block labeled with the language.
        """
    ).strip()
