"""JurisFind — API de pesquisa jurídica local.

Execução em desenvolvimento (a partir de backend/):
    uvicorn main:app --reload --port 8010
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.access import install_access_control, install_frontend
from core.config import get_settings
from core.database import init_db
from routes import books, health, legal, search


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(app.dependency_overrides.get(get_settings, get_settings)())
    yield


app = FastAPI(title="JurisFind API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
for module in (health, books, search, legal):
    app.include_router(module.router)
install_frontend(app)  # depois das rotas da API, que têm precedência
install_access_control(app)
