import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from core.database import get_db
from models.search import SearchLog, SearchMode, SearchResponse
from repositories.search_log_repository import SearchLogRepository
from services.citation_search import CitationSearch, EmptyQuery

router = APIRouter(prefix="/api/search", tags=["citações"])


@router.get("", response_model=SearchResponse)
def search_citations(
    q: str = Query(min_length=2, max_length=300),
    mode: SearchMode = "frase",
    book_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        result = CitationSearch(conn).search(q.strip(), mode, book_id, limit, offset)
    except EmptyQuery as exc:
        raise HTTPException(422, str(exc)) from exc
    if offset == 0:
        SearchLogRepository(conn).add("citacoes", q.strip(), {"mode": mode, "book_id": book_id}, result.total_pages)
    return result


@router.get("/history", response_model=list[SearchLog])
def search_history(limit: int = Query(default=20, ge=1, le=100), conn: sqlite3.Connection = Depends(get_db)):
    return SearchLogRepository(conn).recent(limit)


@router.delete("/history", status_code=204)
def clear_history(conn: sqlite3.Connection = Depends(get_db)):
    SearchLogRepository(conn).clear()
