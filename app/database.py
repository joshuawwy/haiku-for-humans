import hashlib
from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).parent.parent / "data" / "haiku.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS haikus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    haiku_id INTEGER NOT NULL REFERENCES haikus(id),
    ip_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(haiku_id, ip_hash)
);
"""

PAGE_SIZE = 20


async def init_db():
    """Create tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def add_haiku(text: str, author: str) -> int:
    """Insert a haiku and return its id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO haikus (text, author) VALUES (?, ?)", (text, author)
        )
        await db.commit()
        return cursor.lastrowid


async def get_haikus(page: int = 1) -> tuple[list[dict], bool]:
    """Return a page of haikus (newest first) with vote counts."""
    offset = (page - 1) * PAGE_SIZE
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT h.id, h.text, h.author, h.created_at,
                   COALESCE(v.cnt, 0) AS votes
            FROM haikus h
            LEFT JOIN (SELECT haiku_id, COUNT(*) AS cnt FROM votes GROUP BY haiku_id) v
                ON v.haiku_id = h.id
            ORDER BY h.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (PAGE_SIZE + 1, offset),
        )
        haikus = [dict(r) for r in rows]
        has_more = len(haikus) > PAGE_SIZE
        return haikus[:PAGE_SIZE], has_more


async def get_top_haikus(limit: int = 20) -> list[dict]:
    """Return haikus sorted by most votes (min 1 vote)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT h.id, h.text, h.author, h.created_at,
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
        return [dict(r) for r in rows]


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
