from future import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from .models import Task


class Database:
    def __init__(self, path: str = "data/bot.db") -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init()

    def init(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                search_url TEXT NOT NULL,
                min_price INTEGER,
                max_price INTEGER,
                keywords TEXT NOT NULL DEFAULT '',
                stopwords TEXT NOT NULL DEFAULT '',
                brands TEXT NOT NULL DEFAULT '',
                sizes TEXT NOT NULL DEFAULT '',
                min_score INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                check_interval_sec INTEGER NOT NULL DEFAULT 30,
                last_hash TEXT NOT NULL DEFAULT '',
                last_checked_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            name=row["name"],
            search_url=row["search_url"],
            min_price=row["min_price"],
            max_price=row["max_price"],
            keywords=row["keywords"],
            stopwords=row["stopwords"],
            brands=row["brands"],
            sizes=row["sizes"],
            min_score=row["min_score"],
            enabled=bool(row["enabled"]),
            check_interval_sec=row["check_interval_sec"],
            last_hash=row["last_hash"],
            last_checked_at=row["last_checked_at"],
            created_at=row["created_at"],
        )

    def add_task(
        self,
        *,
        name: str,
        search_url: str,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        keywords: str = "",
        stopwords: str = "",
        brands: str = "",
        sizes: str = "",
        min_score: int = 0,
        check_interval_sec: int = 30,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO tasks (
                name, search_url, min_price, max_price,
                keywords, stopwords, brands, sizes,
                min_score, check_interval_sec
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                search_url,
                min_price,
                max_price,
                keywords,
                stopwords,
                brands,
                sizes,
                min_score,
                check_interval_sec,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_tasks(self) -> list[Task]:
        rows = self.conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
        return [self._row_to_task(row) for row in rows]

    def active_tasks(self) -> list[Task]:
        rows = self.conn.execute("SELECT * FROM tasks WHERE enabled = 1 ORDER BY id").fetchall()
        return [self._row_to_task(row) for row in rows]

    def get_task(self, task_id: int) -> Optional[Task]:
        row = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def set_enabled(self, task_id: int, enabled: bool) -> bool:
        cur = self.conn.execute(
            "UPDATE tasks SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, task_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def delete_task(self, task_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()
        return cur.rowcount > 0
        def update_hash(self, task_id: int, last_hash: str) -> None:
        self.conn.execute(
            "UPDATE tasks SET last_hash = ?, last_checked_at = CURRENT_TIMESTAMP WHERE id = ?",
            (last_hash, task_id),
        )
        self.conn.commit()
