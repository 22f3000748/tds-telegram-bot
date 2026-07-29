import asyncio
from pathlib import Path
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse

from bot import build_application, log_event

app = FastAPI()

telegram_app = None

LOG_FILE = Path(__file__).parent / "run.jsonl"


@app.get("/")
def home():
    return {"status": "Bot is running"}


@app.get("/logs")
def logs():
    p = Path(__file__).parent / "run.jsonl"

    return {
        "exists": p.exists(),
        "path": str(p),
        "cwd": os.getcwd(),
        "files": os.listdir(Path(__file__).parent),
    }


@app.on_event("startup")
async def startup():
    global telegram_app

    telegram_app = build_application()

    log_event({
        "direction": "startup",
        "text": "Bot started on Render"
    })

    await telegram_app.initialize()
    await telegram_app.start()

    asyncio.create_task(
        telegram_app.updater.start_polling()
    )


@app.on_event("shutdown")
async def shutdown():
    global telegram_app

    if telegram_app:
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()