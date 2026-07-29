import os
import asyncio
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import PlainTextResponse
from fastapi import FastAPI
from fastapi.responses import FileResponse

from bot import build_application

app = FastAPI()

telegram_app = None


@app.get("/")
def home():
    return {"status": "Bot is running"}




LOG_FILE = Path(__file__).parent / "run.jsonl"

@app.get("/logs")
def logs():
    if not LOG_FILE.exists():
        raise HTTPException(status_code=404, detail="run.jsonl not found")

    return PlainTextResponse(LOG_FILE.read_text(encoding="utf-8"))


@app.on_event("startup")
async def startup():
    global telegram_app

    telegram_app = build_application()

    await telegram_app.initialize()
    await telegram_app.start()

    # Start polling in the background
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