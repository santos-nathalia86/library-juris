"""Configuração da aplicação, lida de variáveis de ambiente com padrões locais."""
import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / "backend" / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Lê pares CHAVE=valor de backend/.env; variáveis já definidas no ambiente prevalecem."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() and not key.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_env_file()

# Chave pública do DataJud, divulgada pelo próprio CNJ em
# https://datajud-wiki.cnj.jus.br/api-publica/acesso — não é um segredo, mas o
# CNJ pode trocá-la; nesse caso defina JURISFIND_DATAJUD_API_KEY.
DATAJUD_PUBLIC_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="


def _origins() -> list[str]:
    raw = os.getenv("JURISFIND_CORS_ORIGINS", "http://localhost:4300,http://127.0.0.1:4300")
    return [o.strip() for o in raw.split(",") if o.strip()]


@dataclass(frozen=True)
class Settings:
    storage_dir: Path = field(
        default_factory=lambda: Path(os.getenv("JURISFIND_STORAGE_DIR", PROJECT_ROOT / "storage"))
    )
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("JURISFIND_MAX_UPLOAD_MB", "200")))
    cors_origins: list[str] = field(default_factory=_origins)
    http_timeout: float = field(default_factory=lambda: float(os.getenv("JURISFIND_HTTP_TIMEOUT", "20")))
    datajud_api_key: str = field(
        default_factory=lambda: os.getenv("JURISFIND_DATAJUD_API_KEY", DATAJUD_PUBLIC_KEY)
    )

    # Senha exigida em todo acesso (HTTP Basic). Vazia = sem senha, adequado só ao uso local.
    access_password: str = field(default_factory=lambda: os.getenv("JURISFIND_ACCESS_PASSWORD", ""))
    # Pasta com o Angular compilado; se existir, a API também serve a interface (uma porta só).
    frontend_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("JURISFIND_FRONTEND_DIR", PROJECT_ROOT / "frontend" / "dist" / "frontend" / "browser")
        )
    )
    # Chave pessoal da Books API; sem ela a fonte "Google Livros" fica desativada.
    google_books_api_key: str = field(default_factory=lambda: os.getenv("JURISFIND_GOOGLE_BOOKS_KEY", ""))

    @property
    def pdf_dir(self) -> Path:
        return self.storage_dir / "pdfs"

    @property
    def db_path(self) -> Path:
        return self.storage_dir / "jurisfind.sqlite3"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def get_settings() -> Settings:
    return Settings()
