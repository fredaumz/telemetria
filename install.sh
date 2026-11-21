#!/usr/bin/env bash
# Instala/restaura a stack de telemetria Cisco numa VM Debian/Ubuntu.
#  - Docker (repositório oficial)
#  - fuso UTC + NTP a.ntp.br / b.ntp.br
#  - copia o projeto para /opt/telemetria e sobe a stack
#  - firewall (SSH/Grafana/coletor) persistente via systemd
#
# Uso:  sudo ./install.sh
# Variáveis opcionais:
#   SKIP_FIREWALL=1   não aplica o firewall (ex.: testes)
#   SKIP_HOST=1       não mexe em fuso/NTP
set -euo pipefail
DEST=/opt/telemetria
SRC="$(cd "$(dirname "$0")" && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "Rode como root: sudo $0"; exit 1; }
. /etc/os-release

# ---------------------------------------------------------------- Docker
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  echo ">> Instalando Docker para $ID $VERSION_CODENAME"
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/$ID $VERSION_CODENAME stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi
apt-get install -y jq bsdextrautils iptables tcpdump >/dev/null 2>&1 || apt-get install -y jq iptables

# ---------------------------------------------------------------- Host: UTC + NTP
if [ "${SKIP_HOST:-0}" != 1 ]; then
  echo ">> Fuso UTC e NTP (a.ntp.br, b.ntp.br)"
  timedatectl set-timezone UTC
  if [ -d /etc/chrony/sources.d ]; then
    # chrony (Ubuntu): só NTP.br; pools padrão desativados
    install -m 644 "$SRC/host/ntp-br.sources" /etc/chrony/sources.d/ntp-br.sources
    for f in /etc/chrony/sources.d/*.sources; do
      [ "$(basename "$f")" = ntp-br.sources ] || mv "$f" "$f.disabled"
    done
    systemctl restart chrony || systemctl restart chronyd || true
  else
    # systemd-timesyncd (Debian)
    install -d /etc/systemd/timesyncd.conf.d
    install -m 644 "$SRC/host/ntp-br.conf" /etc/systemd/timesyncd.conf.d/ntp-br.conf
    systemctl restart systemd-timesyncd || true
  fi
  timedatectl set-ntp true || true
fi

# ---------------------------------------------------------------- Projeto
echo ">> Copiando projeto para $DEST"
mkdir -p "$DEST"
if [ "$SRC" != "$DEST" ]; then
  # .env existente é preservado (senha do Grafana); .git não vai para produção
  tar -C "$SRC" --exclude=.env --exclude=.git -cf - . | tar -C "$DEST" -xf -
fi
chmod +x "$DEST"/install.sh "$DEST"/tools/*.sh "$DEST"/tools/*.py

if [ ! -f "$DEST/.env" ]; then
  PASS=$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 20)
  printf 'GRAFANA_ADMIN_PASSWORD=%s\n' "$PASS" > "$DEST/.env"
  chmod 600 "$DEST/.env"
  echo ">> Senha do Grafana gerada em $DEST/.env"
fi

cd "$DEST"
docker compose pull
docker compose up -d
docker compose ps

# ---------------------------------------------------------------- Firewall
if [ "${SKIP_FIREWALL:-0}" != 1 ]; then
  echo ">> Firewall (lista em $DEST/firewall-allow.txt e $DEST/firewall-routers.txt)"
  install -m 644 "$DEST/host/telemetria-firewall.service" /etc/systemd/system/telemetria-firewall.service
  systemctl daemon-reload
  systemctl enable telemetria-firewall.service
  systemctl restart telemetria-firewall.service
fi

echo
echo ">> Pronto. Grafana: http://<IP>:3000 (usuário admin; senha: sudo cat $DEST/.env)"
echo ">> Roteadores: dial-out gRPC para <IP>:57000 (ver router/)"
echo ">> Saúde: sudo $DEST/tools/check.sh"
