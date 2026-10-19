# JurisFind

Pesquisa jurídica local: biblioteca de livros em PDF com localizador de citações, busca de obras
em acervos on-line de acesso aberto, referência bibliográfica no padrão ABNT e consulta a fontes
oficiais de jurisprudência e legislação.

Tudo roda no seu computador, sem Docker, login, serviços pagos ou APIs de IA. Os PDFs não saem
da máquina.

## Princípio de funcionamento

Toda citação exibida foi recortada do texto de um PDF importado e aponta para o arquivo e a
página de onde saiu. O sistema não gera trechos, páginas, autores, editoras, edições ou anos:

- o que não é encontrado no documento aparece como **Não identificado**;
- dados bibliográficos detectados automaticamente são **sugestões**, sempre com a indicação de
  onde foram lidos (por exemplo, "ficha catalográfica, página 3 do PDF"), e só entram na
  referência depois que você confere e salva;
- a **página impressa** do livro e a **página do arquivo PDF** são mostradas separadamente.

## Requisitos

| Ferramenta | Versão usada no desenvolvimento | Mínimo |
|------------|---------------------------------|--------|
| Python     | 3.14.4                          | 3.10   |
| Node.js    | 20.20.2                         | 20.19 (ou 22.12+) |
| npm        | 10.8.2                          | —      |
| Angular    | 21.2 (instalado pelo `npm install`) | —  |

O Angular 21 foi escolhido por ser a versão mais recente compatível com o Node 20; o Angular 22
exige Node 22.22 ou superior.

## Como executar em desenvolvimento

São dois processos, cada um em um terminal.

### 1. Backend (FastAPI) — porta 8010

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8010
```

Documentação interativa da API: <http://localhost:8010/docs>.

Se `python3 -m venv` falhar com "ensurepip is not available" (Debian/Ubuntu sem o pacote
`python3-venv`), instale o pacote ou use:

```bash
python3 -m venv --without-pip .venv
python3 -m pip --python .venv/bin/python install -r requirements.txt
.venv/bin/uvicorn main:app --reload --port 8010
```

### 2. Frontend (Angular) — porta 4300

```bash
cd frontend
npm install
npm start
```

Abra <http://localhost:4300>. O servidor de desenvolvimento encaminha `/api` para
`http://127.0.0.1:8010` (arquivo `frontend/proxy.conf.json`); o navegador nunca acessa o banco
de dados nem guarda chaves.

As portas 8010 e 4300 foram escolhidas para não colidir com outros projetos que usem as portas
padrão 8000 e 4200. Para mudar, ajuste `--port` no uvicorn, `target` em `proxy.conf.json` e
`port` em `angular.json`.

### Testes

```bash
cd backend
python -m pytest
```

Os testes geram seus próprios PDFs e simulam as fontes externas; não usam internet nem a pasta
`storage/`.

## Uso

A página **Início** tem a busca central: escolha a categoria (meus documentos, livros e doutrina,
jurisprudência ou legislação) e a pesquisa abre na seção correspondente. **Histórico** lista as
pesquisas feitas e permite repeti-las. O botão no alto alterna entre tema claro e escuro.

1. **Meus Documentos** — importe um PDF. O sistema extrai o texto, tenta identificar os dados
   bibliográficos e a paginação impressa, e abre a ficha do livro.
2. **Ficha do livro** — confira cada campo com a folha de rosto e a ficha catalográfica (o link
   "Conferir" abre o PDF na página de onde o dado foi lido), corrija e clique em **Confirmar e
   salvar dados**. Campo salvo em branco fica registrado como "Não identificado".
3. **Citações** — pesquise uma expressão exata, todas as palavras ou qualquer palavra, em toda a
   biblioteca ou em um livro. A busca ignora acentos e maiúsculas. Cada resultado tem os botões
   **Copiar trecho** e **Copiar referência**, além de **Abrir PDF nesta página**.
4. **Livros e Doutrina** — pesquise um termo na BDJur (STJ), no OpenAlex ou, com chave configurada, no
   Google Livros (este só mostra um trecho curto, sem página, e não permite importar). A lista mostra as obras
   em que o termo aparece; em **Importar e localizar o trecho**, o PDF de acesso aberto é baixado
   para a biblioteca e a tela de citações abre já com os trechos e as páginas daquele livro.
5. **Jurisprudência** e **Legislação** — consulta às fontes oficiais descritas abaixo.

## Como os dados são identificados

**Metadados.** São analisadas as 12 primeiras e as 4 últimas páginas, além dos metadados
internos do PDF. A ficha catalográfica (CIP) é a fonte preferida para autor, título, subtítulo,
edição, local, editora e ano. Sem ela, o sistema recorre ao ISBN impresso, à indicação de
edição, ao aviso de copyright, a linhas com nome de editora e ao texto de maior destaque
tipográfico da capa ou folha de rosto. São heurísticas: erram, e por isso nada é tratado como
confirmado antes da sua revisão.

**Paginação impressa.** O número é lido nos cabeçalhos e rodapés e só é aceito quando forma
sequência com as páginas vizinhas (números soltos, como "Capítulo 3" ou um artigo de lei, são
descartados). Cada página fica em uma destas situações:

| Situação | Como aparece | Entra na referência? |
|----------|--------------|----------------------|
| Número lido na própria página | "Página impressa no livro: 45" | Sim (`p. 45`) |
| Página sem número visível, entre duas páginas da mesma sequência | "Página impressa (deduzida)" | Não |
| Apenas o rótulo de página gravado no PDF | "Rótulo de página do arquivo" | Não |
| Nada identificado | "Não identificada" | Não |

A página do arquivo PDF é sempre informada, à parte.

**Capítulo ou seção.** Vem do sumário embutido no PDF (marcadores) quando existe; caso
contrário, de títulos como "Capítulo 3" no alto das páginas.

**Citação ABNT.** Cada trecho encontrado já vem como citação direta no sistema autor-data da
NBR 10520:2023: `"trecho" (Sobrenome, ano, p. 45).` O sobrenome vai só com a inicial maiúscula,
como manda a revisão de 2023. Supressões no recorte aparecem como `[...]` e aspas internas viram
aspas simples. Trechos com mais de cerca de 250 caracteres (mais de três linhas) são tratados
como citação longa: saem sem aspas, e a tela lembra que no trabalho vão em bloco com recuo de
4 cm. A chamada usa só dados confirmados e só a página lida na própria página; o que falta
aparece como aviso, nunca é preenchido por estimativa.

**Referência ABNT.** Segue o modelo de livro da NBR 6023: `SOBRENOME, Prenome. Título:
subtítulo. Edição. Local: Editora, ano.` Usa apenas campos confirmados. Faltando local, editora
ou ano, emprega `[S. l.]`, `[s. n.]` e `[s. d.]` e lista o que falta. Sem autor confirmado, a
entrada é feita pelo título. Autores-entidade (tribunais, conselhos, universidades) não são
invertidos. Nos resultados de livros on-line a referência é montada com os dados do catálogo da
fonte e vem marcada como não conferida. Confira a referência final com a norma: o sistema não estima datas
aproximadas nem trata casos como organizadores, tradutores, volumes e capítulos de obra coletiva.

## Livros disponíveis na internet

Os acervos on-line informam **em quais obras** um termo aparece, mas não a página nem o trecho
exato. Para não exibir citação que não possa ser conferida, o JurisFind só mostra trecho e página
depois de importar o PDF, que passa pela mesma extração dos livros locais. Os dados do registro
do acervo (autor, título, ano, editora) entram como sugestões a confirmar, e o endereço de
origem fica gravado na ficha do livro.

No Google Livros e no OpenAlex, que cobrem todas as áreas, a opção **Apenas obras classificadas
como Direito** vem marcada: usa o filtro de assunto da própria fonte (`subject:law` e a subárea
"Law", respectivamente). A classificação é das fontes e tem falhas — desmarque a opção se uma
obra jurídica que você procura não aparecer. A BDJur já é um acervo jurídico.

Só entram obras que os acervos disponibilizam legalmente. Livros comerciais protegidos por
direito autoral não têm texto integral aberto na internet; para esses, a BDJur costuma ter
apenas o sumário (tipo "Sumário de livro"), e parte do acervo é restrita a usuários do STJ.

O download aceita apenas endereços `https` de servidores públicos, confere cada redirecionamento
e aplica o mesmo limite de tamanho e a mesma validação de PDF do envio manual.

## Fontes externas

Situação verificada em 09/10/2026. Nenhuma delas é necessária para as funções da biblioteca.

| Finalidade | Fonte | Integração |
|------------|-------|------------|
| Dados do livro por ISBN | [BrasilAPI](https://brasilapi.com.br/docs#tag/ISBN), que consulta CBL, Mercado Editorial, Open Library e Google Books | Automática, gratuita, sem chave. Envia só o ISBN. |
| Dados do livro | Biblioteca Nacional (Sophia) | Sem API pública; o catálogo recusa clientes automatizados (HTTP 403). Link para pesquisa manual. |
| Dados do livro | Câmara Brasileira do Livro | Sem API própria. Os registros da CBL chegam pela BrasilAPI; há link para a busca manual de ISBN. |
| Livros (texto integral) | [BDJur](https://bdjur.stj.jus.br/), biblioteca digital do STJ | Automática (API REST do DSpace). Busca no texto integral; PDFs de acesso aberto podem ser importados. |
| Livros (texto integral) | [OpenAlex](https://docs.openalex.org/) | Automática. Livros e capítulos em acesso aberto; sem chave, cerca de 100 buscas por dia. Nem toda obra traz endereço direto do PDF. |
| Livros (trechos) | [Google Livros](https://developers.google.com/books) | Opcional, com chave pessoal gratuita da Books API em `backend/.env`. Inclui obras protegidas: devolve um trecho curto **sem página** e não permite importar o texto. |
| Livros | OAPEN, DOAB, Biblioteca Digital do Senado, SciELO Livros | APIs recusam acesso ou bloqueiam robôs. Links de pesquisa manual. |
| Legislação federal | [Dados Abertos do Senado Federal](https://legis.senado.leg.br/dadosabertos/docs/) | Automática. A API localiza normas por tipo, número e ano, **não por palavras**; as palavras digitadas filtram as ementas das normas retornadas. |
| Jurisprudência | TST | Automática, pelo serviço usado pelo site oficial do tribunal. Não é uma API documentada e pode parar de funcionar. |
| Processos | [DataJud (CNJ)](https://datajud-wiki.cnj.jus.br/api-publica/) | Automática. Retorna metadados processuais (classe, assuntos, órgão), **não ementas**. Costuma levar cerca de 20 s. |
| Jurisprudência | STF, STJ, LexML | Respondem com verificação anti-robô. Links de pesquisa manual já preenchidos com o termo. |
| Legislação | Planalto, LexML, Normas.leg.br | Links para pesquisa manual. |

Quando uma fonte falha, a tela informa o erro e oferece os links manuais; nenhum resultado é
simulado.

O DataJud exige uma chave que o próprio CNJ publica na documentação. Ela fica no backend
(`core/config.py`) e pode ser trocada pela variável `JURISFIND_DATAJUD_API_KEY` se o CNJ a
alterar.

## Acesso de fora do computador (túnel)

```bash
./tunel.sh
```

O script compila a interface, sobe uma instância só local na porta 8020 e abre um
[Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/)
temporário: aparece um endereço `https://….trycloudflare.com` que funciona enquanto o script
estiver rodando e este computador ligado. Não exige conta nem servidor.

- **Senha:** na primeira vez o script cria `JURISFIND_ACCESS_PASSWORD` em `backend/.env`. O
  navegador pede usuário (qualquer nome) e essa senha. Sem senha definida, o túnel não abre.
- O endereço muda a cada execução. Para um endereço fixo é preciso conta na Cloudflare e domínio.
- O tráfego passa pelos servidores da Cloudflare. Compartilhe o endereço e a senha só com quem
  pode ver os documentos da biblioteca.
- Se o `cloudflared` não estiver instalado, o script baixa o binário oficial para `.tools/`.

Com a variável `JURISFIND_ACCESS_PASSWORD` definida, a senha também passa a ser exigida no uso
local (`npm start` + `uvicorn`).

## Configuração

Variáveis de ambiente opcionais, lidas pelo backend. Também podem ficar no arquivo `backend/.env`
(modelo em `backend/.env.example`), que não vai para o Git:

| Variável | Padrão | Função |
|----------|--------|--------|
| `JURISFIND_STORAGE_DIR` | `storage/` na raiz do projeto | Onde ficam os PDFs e o banco SQLite |
| `JURISFIND_MAX_UPLOAD_MB` | `200` | Tamanho máximo de cada PDF |
| `JURISFIND_CORS_ORIGINS` | `http://localhost:4300,http://127.0.0.1:4300` | Origens aceitas quando o frontend não usa o proxy |
| `JURISFIND_HTTP_TIMEOUT` | `20` | Tempo limite, em segundos, das consultas externas |
| `JURISFIND_DATAJUD_API_KEY` | chave pública do CNJ | Chave do DataJud |
| `JURISFIND_ACCESS_PASSWORD` | vazio | Senha exigida em todo acesso (HTTP Basic). Obrigatória para o túnel. |
| `JURISFIND_FRONTEND_DIR` | `frontend/dist/frontend/browser` | Interface compilada que a API também serve, se existir |
| `JURISFIND_GOOGLE_BOOKS_KEY` | vazio | Chave da Books API; habilita a fonte "Google Livros". Crie em <https://console.cloud.google.com/> (ative a "Books API" e gere uma chave de API restrita a ela). |

## Armazenamento

- `storage/jurisfind.sqlite3` — metadados dos livros, texto por página com índice de busca
  (SQLite FTS5) e histórico de pesquisas.
- `storage/pdfs/` — os PDFs importados, gravados com nomes gerados. O nome original é guardado
  apenas para exibição, depois de saneado.

No envio são conferidos a extensão, o tipo declarado, a assinatura `%PDF-` do conteúdo, o
tamanho e se o arquivo abre como PDF. Documentos repetidos (mesmo conteúdo) são recusados. O
conteúdo de `storage/` está no `.gitignore`.

O SQLite atende bem a uma biblioteca pessoal e dispensa instalar um servidor de banco de dados;
por isso o MongoDB (PyMongo) não foi incluído nesta versão. O acesso a dados está isolado em
`backend/repositories/`, que é o ponto de troca caso isso mude.

## Estrutura

```
jurisfind/
├── frontend/                 Angular
│   ├── proxy.conf.json       /api → backend
│   └── src/app/
│       ├── core/             serviço de API e tipos
│       ├── shared/           ícones, botão de copiar, referência, resultados de fontes públicas
│       └── pages/            início, citações, meus documentos, ficha do livro, livros e doutrina,
│                             jurisprudência, legislação, histórico
├── backend/                  FastAPI
│   ├── main.py
│   ├── routes/               books, search, legal, health
│   ├── services/             PDF, metadados, paginação, busca, ABNT, acervos on-line, fontes externas, armazenamento
│   ├── models/               esquemas Pydantic
│   ├── repositories/         acesso ao SQLite
│   ├── core/                 configuração, banco, utilitários de texto
│   ├── tests/
│   └── requirements.txt
├── storage/                  dados locais (fora do Git)
├── .gitignore
└── README.md
```

## Limitações conhecidas

- **PDFs digitalizados sem camada de texto** são guardados, mas não podem ser pesquisados: não
  há OCR. A importação avisa quando isso acontece.
- A busca é textual (palavras e expressões). Não há busca semântica: "conceitos" são encontrados
  pelos termos com que aparecem escritos.
- Palavras hifenizadas na quebra de linha são unidas na extração. Uma palavra composta partida
  exatamente no hífen ("decreto-" / "lei") também é unida; em caso de dúvida, confira no PDF.
- Cabeçalhos e títulos corridos da página podem aparecer dentro do trecho exibido.
- Em colunas, tabelas e notas de rodapé a ordem do texto extraído pode diferir da leitura.
- A importação é síncrona: um livro de cerca de 300 páginas leva alguns segundos.
- A aplicação foi feita para uso local por uma pessoa; não há autenticação.
