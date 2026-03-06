import hashlib
from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).parent.parent / "data" / "haiku.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS haikus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT NOT NULL,
    show_author INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    haiku_id INTEGER NOT NULL REFERENCES haikus(id),
    ip_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(haiku_id, ip_hash)
);

CREATE TABLE IF NOT EXISTS user_prefs (
    telegram_id INTEGER PRIMARY KEY,
    show_name INTEGER NOT NULL DEFAULT 0
);
"""

PAGE_SIZE = 20


async def init_db():
    """Create tables if they don't exist, and migrate existing ones."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        # Migrate: add show_author column if missing (existing rows default to 0)
        cols = [r[1] for r in await db.execute_fetchall("PRAGMA table_info(haikus)")]
        if "show_author" not in cols:
            await db.execute(
                "ALTER TABLE haikus ADD COLUMN show_author INTEGER NOT NULL DEFAULT 0"
            )
        await db.commit()


def redact_name(name: str) -> str:
    """Redact a username: 'testpoet' → 't*****t'."""
    if len(name) <= 2:
        return name[0] + "*" if len(name) == 2 else "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


def _apply_redaction(haiku: dict) -> dict:
    """Redact author name if show_author is false, and fix UTC timestamps."""
    if not haiku.get("show_author"):
        haiku["author"] = redact_name(haiku["author"])
    # SQLite CURRENT_TIMESTAMP is UTC but lacks the Z suffix
    ts = haiku.get("created_at", "")
    if ts and not ts.endswith("Z") and "+" not in ts:
        haiku["created_at"] = ts + "Z"
    return haiku


async def add_haiku(text: str, author: str, show_author: bool = False) -> int:
    """Insert a haiku and return its id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO haikus (text, author, show_author) VALUES (?, ?, ?)",
            (text, author, int(show_author)),
        )
        await db.commit()
        return cursor.lastrowid


async def get_user_pref(telegram_id: int) -> bool:
    """Get whether a user wants their name shown. Default: False (redacted)."""
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchall(
            "SELECT show_name FROM user_prefs WHERE telegram_id = ?",
            (telegram_id,),
        )
        return bool(row[0][0]) if row else False


async def set_user_pref(telegram_id: int, show_name: bool):
    """Set the user's name visibility preference."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_prefs (telegram_id, show_name) VALUES (?, ?)"
            " ON CONFLICT(telegram_id) DO UPDATE SET show_name = ?",
            (telegram_id, int(show_name), int(show_name)),
        )
        await db.commit()


async def get_haikus(page: int = 1) -> tuple[list[dict], bool]:
    """Return a page of haikus (newest first) with vote counts."""
    offset = (page - 1) * PAGE_SIZE
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT h.id, h.text, h.author, h.show_author, h.created_at,
                   COALESCE(v.cnt, 0) AS votes
            FROM haikus h
            LEFT JOIN (SELECT haiku_id, COUNT(*) AS cnt FROM votes GROUP BY haiku_id) v
                ON v.haiku_id = h.id
            ORDER BY h.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (PAGE_SIZE + 1, offset),
        )
        haikus = [_apply_redaction(dict(r)) for r in rows]
        has_more = len(haikus) > PAGE_SIZE
        return haikus[:PAGE_SIZE], has_more


async def get_top_haikus(limit: int = 20) -> list[dict]:
    """Return haikus sorted by most votes (min 1 vote)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT h.id, h.text, h.author, h.show_author, h.created_at,
                   COALESCE(v.cnt, 0) AS votes
            FROM haikus h
            LEFT JOIN (SELECT haiku_id, COUNT(*) AS cnt FROM votes GROUP BY haiku_id) v
                ON v.haiku_id = h.id
            WHERE COALESCE(v.cnt, 0) > 0
            ORDER BY votes DESC, h.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [_apply_redaction(dict(r)) for r in rows]


async def upvote(haiku_id: int, ip: str) -> bool:
    """Add an upvote. Returns False if already voted."""
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO votes (haiku_id, ip_hash) VALUES (?, ?)",
                (haiku_id, ip_hash),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_vote_count(haiku_id: int) -> int:
    """Get current vote count for a haiku."""
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchall(
            "SELECT COUNT(*) FROM votes WHERE haiku_id = ?", (haiku_id,)
        )
        return row[0][0]
