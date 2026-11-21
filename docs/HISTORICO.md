# Histórico e decisões

## 2026-11-21 — montagem inicial (servidor 208.89.72.166, Debian 13)

- Stack criada direto no servidor; validada com simulador (sim-router-1..3, srv-simulado) e dados de teste apagados depois.
- Firewall: 22/3000/57000 restritos a `firewall-allow.txt`; roteadores só na 57000 (`firewall-routers.txt`).
- VM e containers em UTC; NTP em a.ntp.br / b.ntp.br; Grafana com fuso padrão UTC.
- Dashboards: Visão Geral do Roteador, Interfaces (seletor All/múltiplas), CPU e Memória; período padrão 1h.

### Problemas resolvidos (não repetir)

1. **Origem da telemetria.** Com `source-interface Bundle-Ether6.3274` (201.76.196.9, link PNI) nada chegava:
   a rota para a VM sai pela Bundle-Ether5.200. A telemetria funciona saindo com **38.104.72.131**.
   O roteador mostrava `State: NA` no `show telemetry model-driven destination`.
2. **Nome do contador de CRC.** No IOS-XR real é `crc-errors` → métrica `ifstats_crc_errors`
   (não `input_crc_errors`).
3. **Falsos aumentos de contador.** `increase()` do VictoriaMetrics conta o primeiro valor como aumento;
   alertas usam `x - x offset 5m` e dashboards usam `increase_prometheus()`.
4. **Estado das interfaces.** O plugin `cisco_telemetry_mdt` entrega campos com `_` (`line_state`), não `-`.
   O `processors.enum` precisa usar os nomes com `_`. Sempre validar o telegraf.conf antes de aplicar:
   `docker run --rm -v $PWD/telegraf/telegraf.conf:/t.conf:ro telegraf:1.32 telegraf --config /t.conf --test --test-wait 1`
   (uma config inválida deixou a coleta parada ~3 min).
5. **Capacidade com "All".** Somar a banda de todas as portas (inclusive down) dava 8.940 Gbps e achatava o gráfico;
   capacidade agora soma só portas UP, e a linha de capacidade só aparece com uma interface.
6. **Achado real:** FourHundredGigE0/0/0/1 (membro do Bundle-Ether8) recebendo pacotes *giant* → verificar MTU do vizinho.

## 2026-11-21 — servidor reinstalado

O servidor foi reinstalado (Ubuntu 26.04) e os arquivos se perderam, pois não havia cópia fora dele.
O projeto foi reconstruído a partir do histórico da sessão de montagem e passou a ser versionado neste repositório.
O histórico de métricas anterior foi perdido.
