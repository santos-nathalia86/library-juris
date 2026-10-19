import json
import sqlite3
from collections.abc import Iterable

from models.book import BIBLIO_FIELDS

_INSERT_COLUMNS = (
    *BIBLIO_FIELDS, "suggestions", "original_filename", "stored_filename", "sha256",
    "size_bytes", "page_count", "text_page_count", "imported_at", "source_url",
)


def _to_dict(row: sqlite3.Row) -> dict:
    book = dict(row)
    book["confirmed_fields"] = json.loads(book["confirmed_fields"])
    book["suggestions"] = json.loads(book["suggestions"])
    return book


class BookRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, data: dict) -> int:
        row = {**data, "suggestions": json.dumps(data["suggestions"], ensure_ascii=False)}
        columns = ", ".join(_INSERT_COLUMNS)
        marks = ", ".join(f":{c}" for c in _INSERT_COLUMNS)
        cur = self.conn.execute(f"INSERT INTO books ({columns}) VALUES ({marks})", row)
        return cur.lastrowid

    def get(self, book_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        return _to_dict(row) if row else None

    def get_many(self, ids: Iterable[int]) -> dict[int, dict]:
        ids = list(set(ids))
        if not ids:
            return {}
        marks = ", ".join("?" * len(ids))
        rows = self.conn.execute(f"SELECT * FROM books WHERE id IN ({marks})", ids).fetchall()
        return {row["id"]: _to_dict(row) for row in rows}

    def find_by_sha256(self, sha256: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM books WHERE sha256 = ?", (sha256,)).fetchone()
        return _to_dict(row) if row else None

    def list(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM books ORDER BY imported_at DESC, id DESC").fetchall()
        return [_to_dict(row) for row in rows]

    def update_fields(self, book_id: int, values: dict[str, str | None], confirmed: list[str]) -> None:
        sets = ", ".join(f"{name} = :{name}" for name in values)
        sets = f"{sets}, " if sets else ""
        self.conn.execute(
            f"UPDATE books SET {sets}confirmed_fields = :confirmed WHERE id = :id",
            {**values, "confirmed": json.dumps(confirmed), "id": book_id},
        )

    def delete(self, book_id: int) -> None:
        self.conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
