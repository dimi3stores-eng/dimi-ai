# app.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from agent_core import ask_local_model, system_prompt

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')

@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})

@app.post('/chat')
async def chat(payload: dict):
    msg = payload.get('message','')
    reply = ask_local_model(system_prompt() + "\nUSER:\n" + msg + "\nASSISTANT:")
    return {"reply": reply}
