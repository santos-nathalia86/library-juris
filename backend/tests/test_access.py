import dataclasses

from core import access
from core.config import get_settings
from main import app


def protect(settings, monkeypatch, password="segredo forte"):
    monkeypatch.setattr(access, "_FAILURE_DELAY", 0)
    app.dependency_overrides[get_settings] = lambda: dataclasses.replace(settings, access_password=password)


def test_without_password_everything_is_open(client):
    assert client.get("/api/health").status_code == 200


def test_password_is_required_everywhere(client, settings, monkeypatch, book_pdf):
    protect(settings, monkeypatch)
    for path in ("/api/health", "/api/books", "/", "/citacoes", "/api/books/1/file"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.headers["www-authenticate"].startswith("Basic")
    assert client.post("/api/books", files={"file": ("a.pdf", book_pdf, "application/pdf")}).status_code == 401
    assert client.get("/api/health", auth=("qualquer", "errada")).status_code == 401
    assert client.get("/api/health", headers={"Authorization": "Basic %%%"}).status_code == 401
    assert client.get("/api/health", auth=("qualquer", "segredo forte")).status_code == 200


def test_frontend_is_served_with_spa_fallback(client, settings):
    assert client.get("/citacoes").status_code == 404  # ainda não compilado
    settings.frontend_dir.mkdir(parents=True)
    (settings.frontend_dir / "index.html").write_text("<app-root></app-root>")
    (settings.frontend_dir / "main.js").write_text("console.log(1)")
    (settings.frontend_dir.parent / "segredo.txt").write_text("fora da pasta")
    assert client.get("/").text == "<app-root></app-root>"
    assert client.get("/biblioteca/3").text == "<app-root></app-root>"
    assert client.get("/main.js").text == "console.log(1)"
    assert client.get("/%2e%2e/segredo.txt").text == "<app-root></app-root>"
    assert client.get("/api/rota-inexistente").status_code == 404
    assert client.get("/api/health").json()["status"] == "ok"
