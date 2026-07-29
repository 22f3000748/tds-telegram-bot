import os
import asyncio

from fastapi import FastAPI
from fastapi.responses import FileResponse

from bot import build_application

app = FastAPI()

telegram_app = None


@app.get("/")
def home():
    return {"status": "Bot is running"}


@app.get("/logs")
def logs():
    return FileResponse("run.jsonl")


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