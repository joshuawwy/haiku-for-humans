import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db, get_haikus, get_top_haikus, upvote, get_vote_count
from app.bot import handle_update
from app.models import HaikuPage, Haiku

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")
    yield


app = FastAPI(title="Haiku for Humans", lifespan=lifespan)


# --- API routes ---


@app.get("/api/haikus")
async def list_haikus(page: int = 1) -> HaikuPage:
    rows, has_more = await get_haikus(page)
    haikus = [
        Haiku(
            id=r["id"],
            text=r["text"],
            author=r["author"],
            created_at=r["created_at"],
            votes=r["votes"],
        )
        for r in rows
    ]
    return HaikuPage(haikus=haikus, has_more=has_more)


@app.get("/api/haikus/top")
async def top_haikus():
    rows = await get_top_haikus()
    haikus = [
        Haiku(
            id=r["id"],
            text=r["text"],
            author=r["author"],
            created_at=r["created_at"],
            votes=r["votes"],
        )
        for r in rows
    ]
    return {"haikus": haikus}


@app.post("/api/haikus/{haiku_id}/upvote")
async def upvote_haiku(haiku_id: int, request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host)
    voted = await upvote(haiku_id, ip)
    count = await get_vote_count(haiku_id)
    return {"voted": voted, "votes": count}


# --- Telegram webhook ---


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    update = await request.json()
    try:
        await handle_update(update)
    except Exception:
        logger.exception("Error handling Telegram update")
    return JSONResponse({"ok": True})


# --- Static files (must be last) ---

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
