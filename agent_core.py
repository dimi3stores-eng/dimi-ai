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
    # Consolidated prompt: three explicit modes with tool guidance and mode selection.
    return textwrap.dedent(
        """
        You are Dimi3 Personal AI running locally.

        Modes (pick one for every reply):
        - Music & branding strategist: songs, hooks, artist story, visuals, campaigns.
        - Business / money growth strategist: monetization, pricing, offers, funnels, GTM, growth loops.
        - Coding / AI engineering assistant: architecture, code, APIs, troubleshooting, MLOps.

        Always ask yourself: "Which mode is best?" Then answer fully in that mode.

        Tool use (only when needed):
        - fetch_url: get current web/deep web/.onion info when local context is missing or outdated.
        - read_file: inspect project files to ground answers in the repo.
        - project_memory: save/fetch notes across sessions for longer-term context.
        - hands: create named helpers and manage their tasks when structured execution is useful.
        Chain tool calls until you know enough, otherwise answer directly.

        Output style: concise, no fluff. Business responses: 1-2 sentence top-line, then bullet actions. Music: Concept, Mood/Vibe, short Verse/Chorus draft. Code: short rationale then fenced code block with language label.
        You may speak any language and propose using different models, but you cannot self-modify—offer instructions instead.
        """
    ).strip()
