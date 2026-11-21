# Telemetria Cisco

Coleta de telemetria model-driven (MDT) de roteadores Cisco IOS-XR, com dashboards no Grafana.

```
Roteador IOS-XR ──gRPC dial-out :57000──► Telegraf ──► VictoriaMetrics (:8428, só localhost, 30 dias)
                                                            │
                                              vmalert ◄─────┤ (alertas CRC / drops / telemetria parada)
                                              Grafana ◄─────┘ (:3000)
```

Servidor atual: **208.89.72.166** (Ubuntu). Roteadores: **CISCO8200-60-HUDSON** (origem 38.104.72.131), **cisco-la1** (origem 217.20.52.129) e **cisco-seattle** (origem 217.20.54.48).

## Estrutura

| Caminho | O que é |
|---|---|
| `install.sh` | Instala/restaura tudo: Docker, UTC + NTP, stack em `/opt/telemetria`, firewall |
| `docker-compose.yml` | Telegraf, VictoriaMetrics, vmalert, Grafana (+ simuladores no profile `sim`) |
| `telegraf/telegraf.conf` | Coletor MDT, aliases dos sensor-paths, conversão de estado das interfaces |
| `vmalert/rules.yml` | Regras de alerta |
| `grafana/dashboards/*.json` | Dashboards **gerados** por `tools/gen_dashboards.py` (não editar à mão) |
| `grafana/provisioning/` | Datasource e pasta "Telemetria" |
| `tools/gen_dashboards.py` | Gera os 4 dashboards (Visão Geral, Interfaces, CPU e Memória, Qualidade da Coleta) |
| `tools/check.sh` | Saúde da stack: containers, roteadores, alertas |
| `tools/firewall.sh` | Aplica o firewall a partir das listas |
| `firewall-allow.txt` | IPs com acesso a SSH (22), Grafana (3000) e coletor (57000) |
| `firewall-routers.txt` | IPs dos roteadores — só porta 57000 |
| `host/` | Serviço systemd do firewall e config de NTP |
| `router/` | Configuração aplicada em cada roteador |
| `sim/` | Simulador de roteador e servidor para testes |
| `docs/HISTORICO.md` | Decisões e problemas já resolvidos |

O que **não** fica no git: `/opt/telemetria/.env` (senha do Grafana) e os dados do VictoriaMetrics
(volume docker `telemetria_vmdata`).

## Restaurar num servidor novo

```
git clone <URL-DO-REPO> telemetria-cisco
cd telemetria-cisco
sudo ./install.sh
sudo cat /opt/telemetria/.env      # senha do Grafana (usuário admin)
sudo /opt/telemetria/tools/check.sh
```

Se o IP do servidor mudar, atualize o `destination-group` no roteador (`router/`).

> O firewall fecha o SSH para quem não está em `firewall-allow.txt`. Confira a lista antes de rodar.
> Para instalar sem firewall: `sudo SKIP_FIREWALL=1 ./install.sh`.

## Fluxo de alteração

Edite no repositório, aplique e faça commit:

```
# dashboards
python3 tools/gen_dashboards.py grafana/dashboards
# aplicar qualquer mudança no servidor (preserva .env e dados)
sudo ./install.sh
git add -A && git commit -m "..." && git push
```

Só mudar o firewall: editar `firewall-allow.txt` / `firewall-routers.txt`, `sudo ./install.sh`
(ou copiar para `/opt/telemetria/` e rodar `sudo /opt/telemetria/tools/firewall.sh`).

## Teste com dados simulados

```
cd /opt/telemetria
sudo docker compose --profile sim up -d --build
# aguarde ~4 min
sudo tools/check.sh
sudo docker compose --profile sim stop xr-sim server-sim
sudo docker compose --profile sim rm -f xr-sim server-sim
```

## Métricas

Prefixos: `ifstats_` (contadores de interface, ex. `ifstats_crc_errors`), `ifbrief_` (estado/capacidade;
estado 1=up 0=down 2=admin-down), `cpu_total_*`, `cpu_process_*`, `mem_*`.
Labels: `source` (hostname do roteador) e `interface_name`.

## Segurança

- 8428 (VictoriaMetrics) não tem autenticação e está ligado só em 127.0.0.1. Use túnel SSH.
- 22, 3000 e 57000 restritos por `tools/firewall.sh` (cadeias `DOCKER-USER` e `TELEMETRIA-SSH`).
