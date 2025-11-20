# app.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json

from agent_core import ask_local_model, system_prompt
from agent_tools import handle_tool_call
import uvicorn

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')

@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})

@app.post('/chat')
async def chat(payload: dict):
    msg = payload.get('message','')
    base_prompt = system_prompt()
    initial_reply = ask_local_model(base_prompt + "\nUSER:\n" + msg + "\nASSISTANT:")

    reply = initial_reply
    try:
        data = json.loads(initial_reply)
        if isinstance(data, dict) and data.get("tool"):
            tool_name = data.get("tool")
            tool_args = data.get("args", {}) if isinstance(data.get("args", {}), dict) else {}
            tool_result = handle_tool_call(tool_name, tool_args)

            follow_up = """{base}
USER:
{user}
ASSISTANT (tool executed):
Tool {name} returned:\n{result}

Now respond to the user using the tool output above.
""".format(base=base_prompt, user=msg, name=tool_name, result=tool_result)
            reply = ask_local_model(follow_up)
    except json.JSONDecodeError:
        pass

    return {"reply": reply}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
