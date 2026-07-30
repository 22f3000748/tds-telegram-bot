import json
import logging
import os
import time
from collections import defaultdict
from pathlib import Path

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
    raise ValueError("BOT_TOKEN is missing")

if not AIPIPE_TOKEN:
    raise ValueError("AIPIPE_TOKEN is missing")

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

LOG_FILE = Path(__file__).parent / "run.jsonl"
LOG_FILE.touch(exist_ok=True)


def log_event(event: dict):
    event["timestamp"] = time.time()

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# ----------------------------
# AI Client
# ----------------------------
client = OpenAI(
    base_url="https://aipipe.org/openai/v1",
    api_key=AIPIPE_TOKEN,
)

conversation_history = defaultdict(list)

SYSTEM_PROMPT = """
You are an expert data analyst.

Solve the user's task.

The user may specify the required JSON format.

Return ONLY the content that belongs inside the top-level "answer" field.

Examples:

Expected final response:
{
  "answer": 42,
  "log_url": "..."
}

You return:
42

Expected final response:
{
  "answer": {
    "state": "Assam"
  },
  "log_url": "..."
}

You return:
{
  "state": "Assam"
}

Never include:
- log_url
- an outer "answer" object
- markdown
- explanations
- code fences
"""


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

    log_event(
        {
            "direction": "incoming",
            "chat_id": chat_id,
            "user": user,
            "text": text,
        }
    )

    history = conversation_history[chat_id]
    history.append({"role": "user", "content": text})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-6:]

    try:
        reply = ask_ai(messages)

        answer = json.loads(reply)

        final_reply = {
            "answer": answer,
            "log_url": LOG_URL
        }

        reply = json.dumps(final_reply, ensure_ascii=False)

        history.append({"role": "assistant", "content": reply})

        log_event(
            {
                "direction": "outgoing",
                "chat_id": chat_id,
                "user": user,
                "text": reply,
            }
        )

        await update.message.reply_text(reply)

    except Exception as e:
        err = str(e)

        log_event(
            {
                "direction": "error",
                "chat_id": chat_id,
                "user": user,
                "text": err,
            }
        )

        await update.message.reply_text(
            json.dumps(
                {
                    "answer": None,
                    "log_url": LOG_URL,
                    "error": err
                }
            )
        )


# ----------------------------
# Build Telegram App
# ----------------------------
def build_application():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    return application