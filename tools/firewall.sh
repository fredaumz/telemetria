#!/usr/bin/env bash
# Restringe o acesso externo às portas publicadas pelo Docker (Grafana e coletor)
# aos IPs/redes listados em firewall-allow.txt. Aplicado no boot por telemetria-firewall.service.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
ALLOW="$DIR/firewall-allow.txt"
PORTS="${FW_PORTS:-3000,57000}"
IFACE="${FW_IFACE:-$(ip -4 route show default | awk '{print $5; exit}')}"

[ -f "$ALLOW" ] || { echo "Arquivo $ALLOW não encontrado"; exit 1; }
# Lê um arquivo de lista: ignora linhas vazias e comentários (inclusive no fim da linha)
lista() { sed 's/#.*//' "$1" | awk 'NF{print $1}'; }
iptables -N DOCKER-USER 2>/dev/null || true
iptables -F DOCKER-USER
iptables -A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
lista "$ALLOW" | while read -r net; do
  iptables -A DOCKER-USER -i "$IFACE" -p tcp -m multiport --dports "$PORTS" -s "$net" -j RETURN
done
# Roteadores: apenas a porta do coletor
ROUTERS="$DIR/firewall-routers.txt"
COLLECTOR_PORT="${FW_COLLECTOR_PORT:-57000}"
if [ -f "$ROUTERS" ]; then
  lista "$ROUTERS" | while read -r net; do
    iptables -A DOCKER-USER -i "$IFACE" -p tcp --dport "$COLLECTOR_PORT" -s "$net" -j RETURN
  done
fi
# Acesso somente ao Grafana (sem SSH e sem coletor)
GRAFANA="$DIR/firewall-grafana.txt"
GRAFANA_PORT="${FW_GRAFANA_PORT:-3000}"
if [ -f "$GRAFANA" ]; then
  lista "$GRAFANA" | while read -r net; do
    iptables -A DOCKER-USER -i "$IFACE" -p tcp --dport "$GRAFANA_PORT" -s "$net" -j RETURN
  done
fi
iptables -A DOCKER-USER -i "$IFACE" -p tcp -m multiport --dports "$PORTS" -j DROP
iptables -A DOCKER-USER -j RETURN

# SSH (porta do host, cadeia INPUT) com a mesma lista
SSH_PORT="${FW_SSH_PORT:-22}"
iptables -N TELEMETRIA-SSH 2>/dev/null || true
iptables -F TELEMETRIA-SSH
iptables -C INPUT -i "$IFACE" -p tcp --dport "$SSH_PORT" -j TELEMETRIA-SSH 2>/dev/null ||
  iptables -I INPUT 1 -i "$IFACE" -p tcp --dport "$SSH_PORT" -j TELEMETRIA-SSH
iptables -A TELEMETRIA-SSH -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
lista "$ALLOW" | while read -r net; do
  iptables -A TELEMETRIA-SSH -s "$net" -j RETURN
done
iptables -A TELEMETRIA-SSH -j DROP

echo "Firewall aplicado em $IFACE, portas $PORTS e SSH $SSH_PORT:"
iptables -S DOCKER-USER
iptables -S TELEMETRIA-SSH
