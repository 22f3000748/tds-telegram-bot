"""
Improved Telegram + AI Pipe Bot for TDS
---------------------------------------
Requirements:
pip install python-telegram-bot==21.6 openai python-dotenv

Create a .env file:

BOT_TOKEN=xxxxxxxx
AIPIPE_TOKEN=xxxxxxxx
LOG_URL=https://your-public-url/run.jsonl
"""

from fastapi import FastAPI
from fastapi.responses import FileResponse
import threading
import uvicorn
import json
import logging
import asyncio
import os
import time
from collections import defaultdict

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ----------------------------
# Environment
# ----------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
AIPIPE_TOKEN = os.getenv("AIPIPE_TOKEN")
LOG_URL = os.getenv("LOG_URL", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing in .env")

if not AIPIPE_TOKEN:
    raise ValueError("AIPIPE_TOKEN missing in .env")

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

LOG_FILE = "run.jsonl"

def log_event(event: dict):
    event["timestamp"] = time.time()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

# ----------------------------
# AI Client
# ----------------------------
client = OpenAI(
    base_url="https://aipipe.org/openai/v1",
    api_key=AIPIPE_TOKEN,
)

conversation_history = defaultdict(list)

SYSTEM_PROMPT = (
    "You are a careful data analyst. "
    "Return ONLY valid JSON when the user explicitly requests JSON. "
    "Otherwise answer normally."
)

# ----------------------------
# Commands
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello 👋\n"
        "I am your AI Pipe Telegram Bot.\n\n"
        "Send me any question."
    )

# ----------------------------
# AI
# ----------------------------
def ask_ai(messages):
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=messages,
    )
    return response.choices[0].message.content.strip()

# ----------------------------
# Message Handler
# ----------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user.full_name
    text = update.message.text

    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)

    log_event({
        "direction":"incoming",
        "chat_id":chat_id,
        "user":user,
        "text":text
    })

    history = conversation_history[chat_id]
    history.append({"role":"user","content":text})

    messages = [{"role":"system","content":SYSTEM_PROMPT}] + history[-6:]

    try:
        reply = ask_ai(messages)

        # If response is JSON, inject log_url
        try:
            obj = json.loads(reply)
            if isinstance(obj, dict):
                obj["log_url"] = LOG_URL
                reply = json.dumps(obj, ensure_ascii=False)
        except Exception:
            pass

        history.append({"role":"assistant","content":reply})

        log_event({
            "direction":"outgoing",
            "chat_id":chat_id,
            "user":user,
            "text":reply
        })

        await update.message.reply_text(reply)

    except Exception as e:
        err = f"Error: {e}"

        log_event({
            "direction":"error",
            "chat_id":chat_id,
            "user":user,
            "text":err
        })

        await update.message.reply_text(
            "Sorry, something went wrong.\n\n"+err
        )

# ----------------------------
# Main
# ----------------------------

api = FastAPI()

@api.get("/")
def home():
    return {"status": "Bot is running"}

@api.get("/logs")
def logs():
    return FileResponse("run.jsonl")


def run_api():
    uvicorn.run(
        api,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000))
    )




def main():
    threading.Thread(target=run_api, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    print("Bot is running...")
    app.run_polling()

    if __name__ == "__main__":
    main()