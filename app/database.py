from __future__ import annotations

import json
import aiosqlite
from app.models import SearchTask


CREATE_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    search_url TEXT NOT NULL,
    max_price INTEGER,
    city TEXT,
    include_keywords TEXT NOT NULL,
    exclude_keywords TEXT NOT NULL,
    brand_filters TEXT NOT NULL,
    size_filters TEXT NOT NULL,
    min_score INTEGER NOT NULL,
    check_interval_sec INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
)
"""

CREATE_SEEN = """
CREATE TABLE IF NOT EXISTS seen_listings (
    task_id INTEGER NOT NULL,
    external_id TEXT NOT NULL,
    url TEXT NOT NULL,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, external_id)
)
"""


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(CREATE_TASKS)
            await db.execute(CREATE_SEEN)
            await db.commit()

    async def add_task(self, task: SearchTask) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                INSERT INTO tasks (
                    name, search_url, max_price, city, include_keywords, exclude_keywords,
                    brand_filters, size_filters, min_score, check_interval_sec, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.name,
                    task.search_url,
                    task.max_price,
                    task.city,
                    json.dumps(task.include_keywords, ensure_ascii=False),
                    json.dumps(task.exclude_keywords, ensure_ascii=False),
                    json.dumps(task.brand_filters, ensure_ascii=False),
                    json.dumps(task.size_filters, ensure_ascii=False),
                    task.min_score,
                    task.check_interval_sec,
                    int(task.enabled),
                ),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def list_tasks(self) -> list[SearchTask]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT * FROM tasks ORDER BY id")
            rows = await cursor.fetchall()
        return [self._row_to_task(row) for row in rows]

    async def get_task(self, task_id: int) -> SearchTask | None:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
        return self._row_to_task(row) if row else None

    async def set_enabled(self, task_id: int, enabled: bool) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE tasks SET enabled = ? WHERE id = ?", (int(enabled), task_id))
            await db.commit()

    async def delete_task(self, task_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            await db.execute("DELETE FROM seen_listings WHERE task_id = ?", (task_id,))
            await db.commit()

    async def has_seen(self, task_id: int, external_id: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM seen_listings WHERE task_id = ? AND external_id = ?",
                (task_id, external_id),
            )
            row = await cursor.fetchone()
        return row is not None

    async def mark_seen(self, task_id: int, external_id: str, url: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO seen_listings (task_id, external_id, url) VALUES (?, ?, ?)",
                (task_id, external_id, url),
            )
            await db.commit()

    @staticmethod
    def _row_to_task(row: tuple) -> SearchTask:
        return SearchTask(
            id=row[0],
            name=row[1],
            search_url=row[2],
            max_price=row[3],
            city=row[4],
            include_keywords=json.loads(row[5]),
            exclude_keywords=json.loads(row[6]),
            brand_filters=json.loads(row[7]),
            size_filters=json.loads(row[8]),
            min_score=row[9],
            check_interval_sec=row[10],
            enabled=bool(row[11]),
        )
