import os
import logging

import httpx

from app.validator import validate_haiku
from app.database import add_haiku, get_user_pref, set_user_pref, redact_name

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

WELCOME = (
    "Welcome to Haiku for Humans!\n\n"
    "Send me a haiku (5-7-5 syllables) and I'll publish it to haikuforhumans.com.\n\n"
    "Format: three lines, separated by line breaks.\n\n"
    "Example:\n"
    "An old silent pond\n"
    "A frog jumps into the pond\n"
    "Splash! Silence again\n\n"
    "Your handle is redacted by default. Commands:\n"
    "/public — show your full handle on your haikus\n"
    "/private — redact your handle (default)"
)


async def send_message(chat_id: int, text: str):
    """Send a text message via Telegram Bot API."""
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )


async def handle_update(update: dict):
    """Process an incoming Telegram update."""
    message = update.get("message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

    if text.startswith("/start") or text.startswith("/help"):
        await send_message(chat_id, WELCOME)
        return

    if text.startswith("/public"):
        await set_user_pref(user_id, True)
        author = message["from"].get("username") or message["from"].get(
            "first_name", "Anonymous"
        )
        await send_message(
            chat_id,
            f"Your handle will now be shown as @{author} on future haikus.",
        )
        return

    if text.startswith("/private"):
        await set_user_pref(user_id, False)
        author = message["from"].get("username") or message["from"].get(
            "first_name", "Anonymous"
        )
        await send_message(
            chat_id,
            f"Your handle will now appear as @{redact_name(author)} on future haikus.",
        )
        return

    if not text.strip():
        await send_message(chat_id, "Send me a haiku! Three lines, 5-7-5 syllables.")
        return

    result = validate_haiku(text)

    if result.valid:
        author = message["from"].get("username") or message["from"].get(
            "first_name", "Anonymous"
        )
        show = await get_user_pref(user_id)
        haiku_id = await add_haiku(text, author, show_author=show)
        display = author if show else redact_name(author)
        await send_message(
            chat_id,
            f"{result.message}\n\n"
            f"Published as @{display}\n"
            f"See it at haikuforhumans.com",
        )
        logger.info(f"New haiku #{haiku_id} by @{display}")
    else:
        await send_message(chat_id, result.message)
