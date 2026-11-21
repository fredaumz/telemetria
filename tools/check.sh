#!/usr/bin/env bash
# Verifica a saúde da stack de telemetria.
set -u
VM="${VM_URL:-http://127.0.0.1:8428}"
STALE="${STALE_SECONDS:-60}"
cd "$(dirname "$0")/.." || exit 1

q() { curl -fsS --max-time 10 "$VM/api/v1/query" --data-urlencode "query=$1"; }

echo "== Containers =="
docker compose --profile sim ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'
echo

echo "== VictoriaMetrics =="
if curl -fsS --max-time 5 "$VM/health" >/dev/null; then echo "OK ($VM)"; else echo "FALHA: VictoriaMetrics não responde em $VM"; exit 1; fi
echo

echo "== Roteadores (última telemetria) =="
out=$(q 'time() - max by (source) (timestamp(ifstats_bytes_received))' |
  jq -r --argjson s "$STALE" '.data.result[] | [.metric.source, (.value[1]|tonumber|floor)] |
    "\(.[0])\t\(if .[1] <= $s then "OK" else "ATRASADO" end)\t(há \(.[1])s)"')
if [ -n "$out" ]; then echo "$out" | sort | column -t -s $'\t'; else echo "(nenhum roteador enviou telemetria)"; fi
echo

echo "== Servidores (host) =="
out=$(q 'time() - max by (host) (timestamp(cpu_usage_idle))' |
  jq -r --argjson s "$STALE" '.data.result[] | [.metric.host, (.value[1]|tonumber|floor)] |
    "\(.[0])\t\(if .[1] <= $s then "OK" else "ATRASADO" end)\t(há \(.[1])s)"')
if [ -n "$out" ]; then echo "$out" | sort | column -t -s $'\t'; else echo "(nenhum servidor)"; fi
echo

echo "== Alertas disparados =="
out=$(q 'ALERTS{alertstate="firing"}' |
  jq -r '.data.result[] | .metric | "\(.alertname)\t\(.source // .host // "-")\t\(.interface_name // "")"')
if [ -n "$out" ]; then echo "$out" | sort | column -t -s $'\t'; else echo "(nenhum)"; fi
