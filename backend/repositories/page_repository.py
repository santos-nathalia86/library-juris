import sqlite3


class PageRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert_many(self, book_id: int, pages: list[dict]) -> None:
        self.conn.executemany(
            "INSERT INTO pages (book_id, pdf_page, printed_page, printed_page_source, chapter, text) "
            "VALUES (:book_id, :pdf_page, :printed_page, :printed_page_source, :chapter, :text)",
            [{**page, "book_id": book_id} for page in pages],
        )

    def delete_for_book(self, book_id: int) -> None:
        # Exclusão explícita para que o gatilho mantenha o índice FTS em dia.
        self.conn.execute("DELETE FROM pages WHERE book_id = ?", (book_id,))

    def _where(self, book_id: int | None) -> tuple[str, list]:
        return ("AND p.book_id = ?", [book_id]) if book_id is not None else ("", [])

    def count_matches(self, fts_query: str, book_id: int | None) -> int:
        extra, params = self._where(book_id)
        row = self.conn.execute(
            f"SELECT COUNT(*) FROM pages_fts JOIN pages p ON p.id = pages_fts.rowid "
            f"WHERE pages_fts MATCH ? {extra}",
            [fts_query, *params],
        ).fetchone()
        return row[0]

    def search(self, fts_query: str, book_id: int | None, limit: int, offset: int) -> list[sqlite3.Row]:
        extra, params = self._where(book_id)
        return self.conn.execute(
            f"SELECT p.* FROM pages_fts JOIN pages p ON p.id = pages_fts.rowid "
            f"WHERE pages_fts MATCH ? {extra} ORDER BY pages_fts.rank, p.book_id, p.pdf_page LIMIT ? OFFSET ?",
            [fts_query, *params, limit, offset],
        ).fetchall()

    def labeling_summary(self, book_id: int) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT COALESCE(printed_page_source, 'nenhuma') AS source, COUNT(*) AS n "
            "FROM pages WHERE book_id = ? GROUP BY source",
            (book_id,),
        ).fetchall()
        return {row["source"]: row["n"] for row in rows}
