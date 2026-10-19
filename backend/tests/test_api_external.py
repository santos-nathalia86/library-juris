import json

import httpx

from main import app
from services.http_client import get_http_client

SENADO = {"ListaDocumento": {"documentos": {"documento": [{
    "id": "549954", "descricao": "Lei Numerada", "norma": "LEI-8078-1990-09-11",
    "normaNome": "Lei nº 8.078 de 11/09/1990", "ementa": "Dispõe sobre a proteção do consumidor.",
    "dataassinatura": "11/09/1990", "apelido": "LEI-8078-1990-09-11 , Código de Defesa do Consumidor (1990) (CDC)",
}]}}}
TST = {"totalRegistros": 1, "registros": [{"registro": {
    "id": "abc123", "numFormatado": "RR - 1-2.2023.5.12.0004", "ementa": " RECURSO DE REVISTA. DANO MORAL. ",
    "orgaoJudicante": {"descricao": "1ª Turma"}, "nomRelatorSemTratamento": "Fulano de Tal",
    "dtaJulgamento": "2026-10-02", "dtaPublicacao": "2026-10-09",
}}]}
DATAJUD = {"hits": {"total": {"value": 1}, "hits": [{"_source": {
    "numeroProcesso": "00481678720168190000", "classe": {"nome": "Agravo em Recurso Especial"}, "tribunal": "STJ",
    "grau": "SUP", "assuntos": [{"nome": "Direito do Consumidor"}], "dataAjuizamento": "2017-11-30T00:00:00.000Z",
}}]}}
BRASILAPI = {
    "isbn": "9788533302273", "title": "MANUAL", "subtitle": None, "authors": ["MARIA EXEMPLO TESTE"],
    "publisher": "Editora Modelo", "year": 2021, "location": "São Paulo, SP", "provider": "cbl",
}


def test_legislation(client, external):
    external["legis.senado.leg.br"] = httpx.Response(200, json=SENADO)
    result = client.get("/api/legislacao", params={"tipo": "LEI", "numero": "8078"}).json()
    assert result["total"] == 1 and result["error"] is None
    item = result["items"][0]
    assert item["title"] == "Lei nº 8.078 de 11/09/1990"
    assert item["url"] == "https://legis.senado.leg.br/norma/549954"
    assert item["details"]["Também conhecida como"] == "Código de Defesa do Consumidor (1990) (CDC)"
    assert [link["name"] for link in result["manual_links"]][0] == "LexML"
    assert client.get("/api/search/history").json()[0]["kind"] == "legislacao"


def test_legislation_requires_number_or_year(client):
    assert client.get("/api/legislacao").status_code == 422
    assert client.get("/api/legislacao", params={"tipo": "LEI"}).status_code == 422
    assert client.get("/api/legislacao", params={"termo": "consumidor"}).status_code == 422


def test_legislation_words_filter_the_returned_norms(client, external):
    other = {"id": "1", "normaNome": "Lei nº 8.156 de 28/12/1990", "ementa": "Autoriza créditos adicionais."}
    docs = SENADO["ListaDocumento"]["documentos"]["documento"] + [other]
    external["legis.senado.leg.br"] = httpx.Response(200, json={"ListaDocumento": {"documentos": {"documento": docs}}})
    params = {"tipo": "LEI", "ano": 1990}
    assert client.get("/api/legislacao", params=params).json()["total"] == 2
    filtered = client.get("/api/legislacao", params={**params, "termo": "PROTEÇÃO consumidor"}).json()
    assert [i["title"] for i in filtered["items"]] == ["Lei nº 8.078 de 11/09/1990"]
    assert client.get("/api/legislacao", params={**params, "termo": "usucapião"}).json()["total"] == 0


def test_legislation_source_failure_is_reported_not_faked(client, external):
    external["legis.senado.leg.br"] = httpx.ConnectError("sem rede")
    result = client.get("/api/legislacao", params={"termo": "consumidor", "ano": 1990}).json()
    assert result["items"] == [] and result["total"] is None
    assert "conectar" in result["error"] and result["manual_links"]
    assert client.get("/api/search/history").json() == []


def test_jurisprudence_tst(client, external):
    external["tst.jus.br"] = httpx.Response(200, json=TST)
    result = client.get("/api/jurisprudencia", params={"q": "dano moral"}).json()
    item = result["items"][0]
    assert item["summary"] == "RECURSO DE REVISTA. DANO MORAL."
    assert item["details"] == {
        "Órgão judicante": "1ª Turma", "Relator(a)": "Fulano de Tal", "Julgamento": "02/10/2026",
        "Publicação": "09/10/2026",
    }
    assert item["url"].endswith("/rest/documentos/abc123")
    assert any(link["name"].startswith("STF") for link in result["manual_links"])


def test_jurisprudence_tst_can_be_restricted_to_the_summary(client, external):
    sent = []

    def capture(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=TST)

    transport = httpx.MockTransport(capture)
    app.dependency_overrides[get_http_client] = lambda: httpx.Client(transport=transport)
    client.get("/api/jurisprudencia", params={"q": "dano moral"})
    client.get("/api/jurisprudencia", params={"q": "dano moral", "so_ementa": "true"})
    assert sent == [
        {"e": "dano moral", "tipos": ["ACORDAO"]},
        {"e": "dano moral", "tipos": ["ACORDAO"], "ementa": "dano moral"},
    ]


def test_jurisprudence_datajud(client, external):
    external["datajud.cnj.jus.br/api_publica_stj"] = httpx.Response(200, json=DATAJUD)
    result = client.get("/api/jurisprudencia", params={"q": "consumidor", "fonte": "datajud"}).json()
    assert result["source"] == "CNJ — DataJud (STJ)"
    assert result["items"][0]["title"] == "Agravo em Recurso Especial nº 00481678720168190000"
    assert result["items"][0]["summary"] == "Assuntos: Direito do Consumidor"
    assert client.get("/api/jurisprudencia", params={"q": "abc", "fonte": "datajud", "tribunal": "x/../y"}).status_code == 422


def test_jurisprudence_overload_is_reported(client, external):
    external["datajud.cnj.jus.br"] = httpx.Response(429, json={"status": 429})
    result = client.get("/api/jurisprudencia", params={"q": "consumidor", "fonte": "datajud"}).json()
    assert result["items"] == [] and "429" in result["error"]


def test_isbn_lookup(client, external):
    external["brasilapi.com.br/api/isbn/v1/9788533302273"] = httpx.Response(200, json=BRASILAPI)
    result = client.get("/api/metadata/lookup", params={"isbn": "978-85-333-0227-3"}).json()
    assert result["candidates"] == [{
        "source": "BrasilAPI — Câmara Brasileira do Livro", "author": "MARIA EXEMPLO TESTE", "title": "MANUAL",
        "subtitle": None, "year": "2021", "edition": None, "publisher": "Editora Modelo", "city": "São Paulo, SP",
        "isbn": "9788533302273",
    }]
    assert {link["name"] for link in result["manual_links"]} == {"Biblioteca Nacional — catálogo", "CBL — pesquisa de ISBN"}


def test_isbn_lookup_failures(client, external):
    invalid = client.get("/api/metadata/lookup", params={"isbn": "978-85-333-0227-4"}).json()
    assert invalid["candidates"] == [] and "inválido" in invalid["errors"][0]
    missing = client.get("/api/metadata/lookup", params={"isbn": "9788533302273", "title": "Manual"}).json()
    assert missing["candidates"] == [] and "não encontrado" in missing["errors"][0]
    assert len(missing["manual_links"]) == 3
    external["brasilapi.com.br"] = httpx.ReadTimeout("lento")
    assert "tempo" in client.get("/api/metadata/lookup", params={"isbn": "9788533302273"}).json()["errors"][0]
