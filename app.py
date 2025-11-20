# app.py
import asyncio
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from agent_core import ask_local_model, system_prompt
from agent_tools import handle_tool_call

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')

DATA_DIR = Path("data")
INTERACTIONS_FILE = DATA_DIR / "interactions.jsonl"
FEEDBACK_FILE = DATA_DIR / "feedback.jsonl"
TRAINING_DATA_FILE = DATA_DIR / "training_data.jsonl"

DATA_DIR.mkdir(exist_ok=True)

# Keep a short rolling history per session so the model can maintain context.
MAX_HISTORY = 10
conversation_histories: Dict[str, List[Dict[str, str]]] = defaultdict(list)
# Allow a bounded chain of tool calls so the model can iterate until it is satisfied.
MAX_TOOL_CALLS = 5


def _chunk_text(text: str, size: int = 80):
    for i in range(0, len(text), size):
        yield text[i : i + size]


def _format_history(session_id: str) -> str:
    history = conversation_histories.get(session_id, [])[-MAX_HISTORY:]
    formatted = []
    for turn in history:
        formatted.append(f"USER:\n{turn['user']}\nASSISTANT:\n{turn['assistant']}\n")
    return "\n".join(formatted)


def _parse_tool_request(raw: str) -> Optional[Dict[str, object]]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict) and parsed.get("tool"):
        args = parsed.get("args", {}) if isinstance(parsed.get("args", {}), dict) else {}
        return {"tool": parsed["tool"], "args": args}
    return None


def _update_history(session_id: str, user_msg: str, assistant_reply: str) -> None:
    conversation_histories[session_id].append({"user": user_msg, "assistant": assistant_reply})
    conversation_histories[session_id] = conversation_histories[session_id][-MAX_HISTORY:]


def _append_jsonl(path: Path, record: Dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _log_interaction(
    turn_id: str,
    session_id: str,
    message: str,
    assistant_reply: str,
    model: Optional[str],
    tool_name: Optional[str],
    tool_args: Optional[Dict[str, object]],
    tool_result: Optional[str],
    tool_calls: Optional[List[Dict[str, object]]] = None,
) -> None:
    payload = {
        "turn_id": turn_id,
        "session": session_id,
        "model": model,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user_message": message,
        "assistant_reply": assistant_reply,
        "tool": tool_name,
        "tool_args": tool_args,
        "tool_result": tool_result,
        "tool_calls": tool_calls or [],
    }
    _append_jsonl(INTERACTIONS_FILE, payload)


def _log_feedback(turn_id: str, session_id: str, rating: str, comment: Optional[str]) -> None:
    payload = {
        "turn_id": turn_id,
        "session": session_id,
        "rating": rating,
        "comment": comment or "",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    _append_jsonl(FEEDBACK_FILE, payload)


def _prepare_training_data() -> Dict[str, object]:
    interactions = []
    if INTERACTIONS_FILE.exists():
        interactions = [json.loads(line) for line in INTERACTIONS_FILE.read_text().splitlines() if line]

    feedback_map: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    if FEEDBACK_FILE.exists():
        for line in FEEDBACK_FILE.read_text().splitlines():
            if not line:
                continue
            fb = json.loads(line)
            feedback_map[fb.get("turn_id", "")].append(fb)

    training_records = []
    for interaction in interactions:
        turn_id = interaction.get("turn_id")
        fb_list = feedback_map.get(turn_id, [])
        if not fb_list:
            continue
        for fb in fb_list:
            record = {
                "turn_id": turn_id,
                "session": interaction.get("session"),
                "model": interaction.get("model"),
                "prompt": interaction.get("user_message"),
                "response": interaction.get("assistant_reply"),
                "rating": fb.get("rating"),
                "comment": fb.get("comment", ""),
            }
            training_records.append(record)

    if training_records:
        TRAINING_DATA_FILE.write_text("\n".join(json.dumps(r) for r in training_records))

    return {
        "prepared": len(training_records),
        "output_file": str(TRAINING_DATA_FILE),
        "interactions_consumed": len(interactions),
        "feedback_consumed": sum(len(v) for v in feedback_map.values()),
    }


def _run_model_interaction(session_id: str, message: str, model: Optional[str]) -> Tuple[str, str]:
    turn_id = uuid4().hex
    history_block = _format_history(session_id)
    base_prompt = f"{system_prompt()}\n\nConversation so far:\n{history_block}USER:\n{message}\nASSISTANT:"
    prompt = base_prompt
    tool_calls: List[Dict[str, object]] = []
    final_reply = ""

    for _ in range(MAX_TOOL_CALLS):
        candidate_reply = ask_local_model(prompt, model=model)
        tool_request = _parse_tool_request(candidate_reply)

        if not tool_request:
            final_reply = candidate_reply
            break

        tool_name = str(tool_request["tool"])
        tool_args = tool_request["args"] or {}
        tool_result = handle_tool_call(tool_name, tool_args, session_id=session_id)

        tool_calls.append({
            "tool": tool_name,
            "args": tool_args,
            "result": tool_result,
        })

        tool_transcript = "\n\n".join(
            [
                f"Tool {idx + 1}: {call['tool']} with args {call['args']}\nResult:\n{call['result']}"
                for idx, call in enumerate(tool_calls)
            ]
        )

        prompt = (
            f"{system_prompt()}\n\nConversation so far:\n{history_block}USER:\n{message}\nASSISTANT (tool executed):\n"
            f"{tool_transcript}\n\nIf you still need more information, request another tool call in JSON."
            " Otherwise, respond to the user using the results above."
        )
    else:
        final_reply = "Maximum tool depth reached. Please ask again with more context."

    last_tool = tool_calls[-1] if tool_calls else None
    _update_history(session_id, message, final_reply)
    _log_interaction(
        turn_id,
        session_id,
        message,
        final_reply,
        model,
        last_tool.get("tool") if last_tool else None,
        last_tool.get("args") if last_tool else None,
        last_tool.get("result") if last_tool else None,
        tool_calls,
    )
    return final_reply, turn_id


def _stream_response(text: str):
    async def generator():
        for chunk in _chunk_text(text, size=64):
            yield chunk
            await asyncio.sleep(0)
    return generator()


@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})


@app.post('/chat')
async def chat(payload: dict):
    msg = payload.get('message', '')
    model = payload.get('model') or None
    session_id = payload.get('session') or 'default'

    reply_text, turn_id = _run_model_interaction(session_id, msg, model)
    return StreamingResponse(
        _stream_response(reply_text),
        media_type='text/plain',
        headers={"X-Turn-Id": turn_id},
    )


@app.post('/feedback')
async def feedback(payload: dict):
    turn_id = str(payload.get('turn_id') or '')
    rating = str(payload.get('rating') or '').lower()
    session_id = str(payload.get('session') or 'default')
    comment = payload.get('comment')

    if rating not in {'good', 'bad'}:
        return {'status': 'error', 'detail': "rating must be 'good' or 'bad'"}
    if not turn_id:
        return {'status': 'error', 'detail': 'turn_id is required'}

    _log_feedback(turn_id, session_id, rating, comment)
    return {'status': 'ok', 'turn_id': turn_id, 'rating': rating}


@app.post('/train')
async def train():
    summary = _prepare_training_data()
    return {'status': 'ok', **summary}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
