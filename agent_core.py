# agent_core.py
# Premium Light version
import subprocess, textwrap, json, os, re
from agent_tools import handle_tool_call

ANSI = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
def clean(t): return ANSI.sub('', t or '')

def ask_local_model(prompt, model="qwen2.5"):
    cmd = ["ollama", "run", model]
    res = subprocess.run(cmd, input=prompt, text=True, capture_output=True)
    return clean(res.stdout)

def system_prompt():
    return """You are Dimi3 Personal AI running locally on his PC.
Roles:
- Business strategist
- Music creator & branding expert
- Coding assistant
- Marketing engine
Rules:
- If normal question: answer normally.
- If tool needed: respond ONLY in JSON {"tool":"...","args":{...}}.
"""