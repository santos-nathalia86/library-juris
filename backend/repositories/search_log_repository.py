import json
import sqlite3
from datetime import datetime, timezone


class SearchLogRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, kind: str, query: str, params: dict, total: int) -> None:
        self.conn.execute(
            "INSERT INTO searches (kind, query, params, total, created_at) VALUES (?, ?, ?, ?, ?)",
            (kind, query, json.dumps(params, ensure_ascii=False), total,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def recent(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM searches ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(row), "params": json.loads(row["params"])} for row in rows]

    def clear(self) -> None:
        self.conn.execute("DELETE FROM searches")
        self.conn.commit()
