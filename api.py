
import os
from dotenv import load_dotenv
load_dotenv()
#!/usr/bin/env python3
"""HTTP API для бота Денис-продавец — используется виджетом на сайте"""
import json, os, aiohttp, hashlib
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["https://kodkontenta.ru"], allow_methods=["POST"], allow_headers=["*"])

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_URL = "https://api.anthropic.com/v1/messages"
LLM_MODEL = "claude-haiku-4-5-20251001"
HISTORY_FILE = "/root/prodavec/history.json"

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            return json.load(open(HISTORY_FILE))
    except:
        pass
    return {}

def save_history(h):
    json.dump(h, open(HISTORY_FILE, "w"), ensure_ascii=False)

def get_system():
    p = open("/root/prodavec/prompt.txt", encoding="utf-8").read()
    pr = open("/root/prodavec/products.txt", encoding="utf-8").read()
    return p + "\n\n" + pr

async def ask_llm(system, messages):
    payload = {"model": LLM_MODEL, "messages": messages, "max_tokens": 600, "system": system}
    headers = {"x-api-key": LLM_API_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(LLM_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as r:
            data = await r.json()
    if "error" in data:
        raise Exception(str(data["error"]))
    return data["content"][0]["text"]

@app.post("/chat")
async def chat(req: Request):
    try:
        body = await req.json()
        session_id = body.get("session_id", "web_anon")
        text = body.get("message", "").strip()
        if not text:
            return {"reply": "Напишите что-нибудь!"}

        uid = "web_" + hashlib.md5(session_id.encode()).hexdigest()[:8]

        h = load_history()
        if uid not in h:
            h[uid] = []
        h[uid].append({"role": "user", "content": text})
        if len(h[uid]) > 20:
            h[uid] = h[uid][-20:]

        reply = await ask_llm(get_system(), h[uid])
        h[uid].append({"role": "assistant", "content": reply})
        save_history(h)

        return {"reply": reply}
    except Exception as e:
        return {"reply": "Минуту, уточняю информацию... Попробуйте снова."}

@app.get("/health")
async def health():
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8766)
