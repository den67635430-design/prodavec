#!/usr/bin/env python3
import json, logging, os
from dotenv import load_dotenv

load_dotenv()
import aiohttp
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_URL = "https://api.anthropic.com/v1/messages"
LLM_MODEL = "claude-haiku-4-5-20251001"
HISTORY_FILE = "/root/prodavec/history.json"
SKILLS_DIR = "/root/prodavec/skills"
SHTAB_ID = -1003383555753

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {}

def save_history(h):
    with open(HISTORY_FILE, "w") as f:
        json.dump(h, f, ensure_ascii=False)

def load_skills() -> str:
    if not os.path.exists(SKILLS_DIR):
        return ""
    skills = []
    for fname in sorted(os.listdir(SKILLS_DIR)):
        if fname.endswith(".md"):
            path = os.path.join(SKILLS_DIR, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    skills.append(f.read()[:500])
            except Exception:
                pass
    return "\n---\n".join(skills) if skills else ""

def get_system():
    p = open("/root/prodavec/prompt.txt", encoding="utf-8").read()
    pr = open("/root/prodavec/products.txt", encoding="utf-8").read()
    base = p + chr(10)*2 + pr
    skills = load_skills()
    if skills:
        base += chr(10)*2 + "Novye AI-instrumenty (dlya rekomendacij klientam):\n" + skills
    return base

async def ask_llm(system, messages):
    payload = {"model": LLM_MODEL, "messages": messages, "max_tokens": 600, "system": system}
    headers = {"x-api-key": LLM_API_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(LLM_URL, headers=headers, json=payload) as r:
            data = await r.json()
    if "error" in data:
        raise Exception(str(data["error"]))
    return data["content"][0]["text"]

async def process(user_id, text):
    h = load_history()
    uid = str(user_id)
    if uid not in h:
        h[uid] = []
    h[uid].append({"role": "user", "content": text})
    if len(h[uid]) > 30:
        h[uid] = h[uid][-30:]
    reply = await ask_llm(get_system(), h[uid])
    h[uid].append({"role": "assistant", "content": reply})
    save_history(h)
    return reply

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    await update.message.chat.send_action("typing")
    try:
        reply = await process(user_id, text)
        try:
            await update.message.reply_text(f"<b>💼 Denis Prodavec</b>\n\n{reply}", parse_mode="HTML")
        except Exception:
            await update.message.reply_text(reply)
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("⏳ Секунду, уточняю...")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "друг"
    nl = chr(10)
    msg = f"<b>💼 Привет, {name}!</b>{nl*2}Я помогаю бизнесу зарабатывать больше с помощью AI-автоматизации.{nl*2}💡 Расскажи — чем занимаешься? Найдём, где теряются деньги и клиенты"
    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    h = load_history()
    h[str(update.effective_user.id)] = []
    save_history(h)
    await update.message.reply_text("🔄 Начнём с чистого листа!")

async def handle_shtab_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений из Штаба Дениса — УЛУЧШЕННЫЙ ФОРМАТ"""
    user_id = update.effective_user.id
    text = update.message.text
    await update.message.chat.send_action("typing")
    try:
        reply = await process(user_id, text)

        # Форматируем ответ с эмодзи и структурой
        formatted = f"<b>💼 Denis Prodavec</b>\n\n{reply}"

        try:
            await update.message.reply_text(formatted, parse_mode="HTML")
        except Exception:
            await update.message.reply_text(reply)
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("❌ Ошибка в Штабе: " + str(e)[:100])

def main():
    os.makedirs("/root/prodavec", exist_ok=True)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Chat(chat_id=SHTAB_ID) & filters.TEXT & ~filters.COMMAND, handle_shtab_message))
    logger.info("Prodavec bot started (improved format)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
