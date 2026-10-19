#!/usr/bin/env bash
# Publica o JurisFind deste computador num endereço https temporário (Cloudflare Tunnel).
# Uso: ./tunel.sh        Encerrar: Ctrl+C (o endereço deixa de funcionar).
set -euo pipefail
cd "$(dirname "$0")"

PORT="${JURISFIND_TUNNEL_PORT:-8020}"
ENV_FILE="backend/.env"
PY="backend/.venv/bin/python"

[ -x "$PY" ] || { echo "Ambiente Python não encontrado: crie backend/.venv (veja o README)."; exit 1; }

# 1. Sem senha o túnel não abre: o endereço é público.
if ! grep -q '^JURISFIND_ACCESS_PASSWORD=..........' "$ENV_FILE" 2>/dev/null; then
  PASSWORD="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(12))')"
  touch "$ENV_FILE"; chmod 600 "$ENV_FILE"
  sed -i '/^JURISFIND_ACCESS_PASSWORD=/d' "$ENV_FILE"
  echo "JURISFIND_ACCESS_PASSWORD=$PASSWORD" >> "$ENV_FILE"
  echo "Senha de acesso criada e gravada em $ENV_FILE."
fi

# 2. Interface compilada (a API passa a servir tudo numa porta só).
if [ ! -f frontend/dist/frontend/browser/index.html ] || [ -n "$(find frontend/src -newer frontend/dist/frontend/browser/index.html -print -quit)" ]; then
  echo "Compilando a interface..."
  (cd frontend && npm run build --silent)
fi

# 3. cloudflared: usa o instalado ou baixa o binário oficial para .tools/ (sem sudo).
CLOUDFLARED="$(command -v cloudflared || true)"
if [ -z "$CLOUDFLARED" ]; then
  CLOUDFLARED=".tools/cloudflared"
  if [ ! -x "$CLOUDFLARED" ]; then
    case "$(uname -m)" in x86_64) ARCH=amd64 ;; aarch64) ARCH=arm64 ;; *) echo "Arquitetura não suportada."; exit 1 ;; esac
    echo "Baixando o cloudflared (github.com/cloudflare/cloudflared)..."
    mkdir -p .tools
    curl -fL --progress-bar -o "$CLOUDFLARED" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$ARCH"
    chmod +x "$CLOUDFLARED"
  fi
fi

# 4. Sobe uma instância própria, só local, protegida pela senha, e abre o túnel para ela.
(cd backend && exec .venv/bin/uvicorn main:app --host 127.0.0.1 --port "$PORT" --log-level warning) &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
sleep 2

echo
echo "Usuário: qualquer nome     Senha: a de JURISFIND_ACCESS_PASSWORD em $ENV_FILE"
echo "O endereço https://....trycloudflare.com aparece logo abaixo. Ctrl+C encerra."
echo
"$CLOUDFLARED" tunnel --no-autoupdate --url "http://127.0.0.1:$PORT"
