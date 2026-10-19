"""Conexão SQLite e criação do esquema (metadados, páginas, índice FTS5 e histórico)."""
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Depends

from core.config import Settings, get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT,
    title TEXT,
    subtitle TEXT,
    year TEXT,
    edition TEXT,
    publisher TEXT,
    city TEXT,
    isbn TEXT,
    confirmed_fields TEXT NOT NULL DEFAULT '[]',
    suggestions TEXT NOT NULL DEFAULT '{}',
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL UNIQUE,
    size_bytes INTEGER NOT NULL,
    page_count INTEGER NOT NULL,
    text_page_count INTEGER NOT NULL,
    imported_at TEXT NOT NULL,
    source_url TEXT
);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    pdf_page INTEGER NOT NULL,
    printed_page TEXT,
    printed_page_source TEXT,
    chapter TEXT,
    text TEXT NOT NULL,
    UNIQUE (book_id, pdf_page)
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    text, content='pages', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
    INSERT INTO pages_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    query TEXT NOT NULL,
    params TEXT NOT NULL DEFAULT '{}',
    total INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(settings: Settings) -> None:
    settings.pdf_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(settings.db_path)
    try:
        conn.executescript(SCHEMA)
        # Bancos criados antes da importação por endereço não têm esta coluna.
        if "source_url" not in {row["name"] for row in conn.execute("PRAGMA table_info(books)")}:
            conn.execute("ALTER TABLE books ADD COLUMN source_url TEXT")
        conn.commit()
    finally:
        conn.close()


def get_db(settings: Settings = Depends(get_settings)) -> Iterator[sqlite3.Connection]:
    conn = connect(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()
