"""Gera os dashboards Grafana da stack de telemetria Cisco."""
import json, sys

OUT = sys.argv[1]
DS = {"type": "prometheus", "uid": "vm"}
# Paleta (modo escuro, validada) e cores de status
RX, TX = "#3987e5", "#d95926"
GOOD, WARN, SERIOUS, CRIT = "#0ca30c", "#fab219", "#ec835a", "#d03b3b"
NEUTRAL = "#8e8d86"
R = 'source=~"$router"'
PHYS = 'interface_name=~".*GigE[0-9/]+"'          # portas físicas (sem subinterface/bundle)
IFSEL = 'interface_name=~"$interface"'

_id = [0]
def nid():
    _id[0] += 1
    return _id[0]

def tgt(expr, legend="", ref="A", instant=False, fmt=None):
    t = {"refId": ref, "datasource": DS, "expr": expr, "legendFormat": legend}
    if instant:
        t["instant"] = True; t["range"] = False
    if fmt:
        t["format"] = fmt
    return t

def thresholds(*steps):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for v, c in steps]}

def stat(title, expr, x, y, w=3, h=4, unit="none", th=None, decimals=None, desc="", color_mode="value", mappings=None, graph=True):
    d = {"unit": unit, "thresholds": th or thresholds((None, NEUTRAL)), "color": {"mode": "thresholds"}}
    if decimals is not None: d["decimals"] = decimals
    if mappings: d["mappings"] = mappings
    return {"id": nid(), "type": "stat", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "fieldConfig": {"defaults": d, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": color_mode, "graphMode": "area" if graph else "none",
                        "textMode": "value", "justifyMode": "center", "wideLayout": True},
            "targets": [tgt(expr)]}

def ts(title, targets, x, y, w=12, h=8, unit="none", desc="", overrides=None, stack=False,
       fill=12, legend_calcs=("mean", "max", "lastNotNull"), legend_mode="table", min0=True, draw="line"):
    d = {"unit": unit, "color": {"mode": "palette-classic"},
         "custom": {"lineWidth": 2, "fillOpacity": fill, "gradientMode": "opacity", "showPoints": "never",
                    "drawStyle": draw, "spanNulls": 60000, "axisSoftMin": 0 if min0 else None,
                    "stacking": {"mode": "normal" if stack else "none"}, "axisBorderShow": False}}
    return {"id": nid(), "type": "timeseries", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "fieldConfig": {"defaults": d, "overrides": overrides or []},
            "options": {"legend": {"displayMode": legend_mode, "placement": "bottom" if legend_mode != "table" else "right",
                                   "calcs": list(legend_calcs), "sortBy": "Max", "sortDesc": True},
                        "tooltip": {"mode": "multi", "sort": "desc"}},
            "targets": targets}

def fixed_color(name, color):
    return {"matcher": {"id": "byName", "options": name},
            "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": color}}]}

def bargauge(title, expr, legend, x, y, w=12, h=9, unit="none", th=None, desc=""):
    return {"id": nid(), "type": "bargauge", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "fieldConfig": {"defaults": {"unit": unit, "min": 0, "color": {"mode": "thresholds"},
                                         "thresholds": th or thresholds((None, RX))}, "overrides": []},
            "options": {"orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True,
                        "valueMode": "color", "namePlacement": "left", "sizing": "manual", "minVizHeight": 16,
                        "maxVizHeight": 22,
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
            "targets": [tgt(expr, legend, instant=True)]}

def row(title, y, collapsed=False):
    return {"id": nid(), "type": "row", "title": title, "collapsed": collapsed,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []}

def var_router():
    return {"name": "router", "label": "Roteador", "type": "query", "datasource": DS,
            "query": {"query": "label_values(ifstats_bytes_received, source)", "refId": "r"},
            "definition": "label_values(ifstats_bytes_received, source)", "refresh": 2, "sort": 1,
            "multi": False, "includeAll": False}

STATE_MAP = [{"type": "value", "options": {
    "1": {"text": "UP", "color": GOOD}, "0": {"text": "DOWN", "color": CRIT},
    "2": {"text": "ADMIN DOWN", "color": NEUTRAL}, "3": {"text": "OUTRO", "color": WARN}}}]

def dashboard(uid, title, panels, templating, tags, links=None):
    return {"uid": uid, "title": title, "tags": tags, "timezone": "utc", "schemaVersion": 39,
            "editable": True, "graphTooltip": 1, "refresh": "30s", "time": {"from": "now-1h", "to": "now"},
            "timepicker": {"refresh_intervals": ["10s", "30s", "1m", "5m", "15m"]},
            "templating": {"list": templating}, "links": links or [], "panels": panels}

LINKS = [{"title": "Dashboards de telemetria", "type": "dashboards", "tags": ["cisco"], "asDropdown": False,
          "includeVars": True, "keepTime": True}]

# =====================================================================
# 1) Visão geral do roteador
# =====================================================================
_id[0] = 0
P = []
y = 0
P.append(row("Saúde", y)); y += 1
P += [
    stat("Telemetria", f'time() - max(timestamp(ifstats_bytes_received{{{R}}}))', 0, y, unit="s", decimals=0,
         th=thresholds((None, GOOD), (60, WARN), (180, CRIT)), graph=False,
         desc="Segundos desde o último dado recebido do roteador. Verde = chegando normalmente."),
    stat("CPU (5 min)", f'max(cpu_total_cpu_five_minute{{{R}}})', 3, y, unit="percent",
         th=thresholds((None, GOOD), (60, WARN), (80, CRIT)), desc="Uso total de CPU do RP, média de 5 minutos."),
    stat("Memória usada", f'100 * (1 - sum(mem_free_physical_memory{{{R}}}) / sum(mem_ram_memory{{{R}}}))', 6, y,
         unit="percent", decimals=1, th=thresholds((None, GOOD), (75, WARN), (90, CRIT))),
    stat("Tráfego RX", f'sum(rate(ifstats_bytes_received{{{R},{PHYS}}}[$__rate_interval])) * 8', 9, y, unit="bps",
         th=thresholds((None, RX)), desc="Soma das portas físicas."),
    stat("Tráfego TX", f'sum(rate(ifstats_bytes_sent{{{R},{PHYS}}}[$__rate_interval])) * 8', 12, y, unit="bps",
         th=thresholds((None, TX)), desc="Soma das portas físicas."),
    stat("Portas físicas UP", f'count(ifbrief_line_state{{{R},{PHYS}}} == 1)', 15, y, graph=False,
         th=thresholds((None, GOOD)), desc="Requer o sensor-path interface-briefs no roteador."),
    stat("Portas DOWN", f'count(ifbrief_line_state{{{R},{PHYS}}} == 0 and ifbrief_state{{{R},{PHYS}}} != 2) or vector(0)', 18, y,
         graph=False, th=thresholds((None, GOOD), (1, CRIT)),
         desc="Portas físicas com protocolo down (exclui admin-down). Requer interface-briefs."),
    stat("Alertas ativos", 'count(ALERTS{alertstate="firing",' + R + '}) or vector(0)', 21, y, graph=False,
         th=thresholds((None, GOOD), (1, CRIT))),
]
y += 4
P += [
    stat("Erros CRC no período", f'sum(increase_prometheus(ifstats_crc_errors{{{R}}}[$__range])) or vector(0)', 0, y, w=6, h=3,
         graph=False, decimals=0, th=thresholds((None, GOOD), (1, CRIT))),
    stat("Erros de entrada no período", f'sum(increase_prometheus(ifstats_input_errors{{{R}}}[$__range])) or vector(0)', 6, y, w=6, h=3,
         graph=False, decimals=0, th=thresholds((None, GOOD), (1, WARN), (1000, CRIT))),
    stat("Drops no período (entrada + saída)",
         f'sum(increase_prometheus(ifstats_input_drops{{{R}}}[$__range])) + sum(increase_prometheus(ifstats_output_drops{{{R}}}[$__range])) or vector(0)',
         12, y, w=6, h=3, graph=False, decimals=0, unit="short", th=thresholds((None, GOOD), (1, WARN), (100000, SERIOUS))),
    stat("Flaps no período", f'sum(increase_prometheus(ifstats_carrier_transitions{{{R}}}[$__range])) or vector(0)', 18, y, w=6, h=3,
         graph=False, decimals=0, th=thresholds((None, GOOD), (1, WARN), (10, CRIT)),
         desc="Transições de carrier (link caindo/voltando) em todas as interfaces."),
]
y += 3

P.append(row("Tráfego", y)); y += 1
P.append(ts("Tráfego total (portas físicas)", [
    tgt(f'sum(rate(ifstats_bytes_received{{{R},{PHYS}}}[$__rate_interval])) * 8', "RX", "A"),
    tgt(f'sum(rate(ifstats_bytes_sent{{{R},{PHYS}}}[$__rate_interval])) * 8', "TX", "B"),
], 0, y, w=24, h=8, unit="bps", overrides=[fixed_color("RX", RX), fixed_color("TX", TX)], legend_mode="list",
   legend_calcs=("mean", "max", "lastNotNull")))
y += 8
P.append(bargauge("Top 10 interfaces — RX", f'topk(10, rate(ifstats_bytes_received{{{R},{PHYS}}}[5m]) * 8)',
                  "{{interface_name}}", 0, y, unit="bps", th=thresholds((None, RX))))
P.append(bargauge("Top 10 interfaces — TX", f'topk(10, rate(ifstats_bytes_sent{{{R},{PHYS}}}[5m]) * 8)',
                  "{{interface_name}}", 12, y, unit="bps", th=thresholds((None, TX))))
y += 9
P.append(bargauge("Utilização das portas (maior entre RX e TX)",
                  f'topk(15, 100 * max by (interface_name) ('
                  f'label_replace(rate(ifstats_bytes_received{{{R},{PHYS}}}[5m]),"d","rx","","") or '
                  f'label_replace(rate(ifstats_bytes_sent{{{R},{PHYS}}}[5m]),"d","tx","","")) * 8 '
                  f'/ on(interface_name) (max by (interface_name) (ifbrief_bandwidth{{{R},{PHYS}}}) * 1000))',
                  "{{interface_name}}", 0, y, w=24, h=6, unit="percent",
                  th=thresholds((None, GOOD), (70, WARN), (85, SERIOUS), (95, CRIT)),
                  desc="Percentual da capacidade da porta. Requer o sensor-path interface-briefs (bandwidth)."))
P[-1]["fieldConfig"]["defaults"]["max"] = 100
y += 6

P.append(row("Interfaces", y)); y += 1
tbl_targets = [
    tgt(f'max by (interface_name) (rate(ifstats_bytes_received{{{R}}}[5m]) * 8)', ref="RX", instant=True, fmt="table"),
    tgt(f'max by (interface_name) (rate(ifstats_bytes_sent{{{R}}}[5m]) * 8)', ref="TX", instant=True, fmt="table"),
    tgt(f'max by (interface_name) (ifbrief_bandwidth{{{R}}} * 1000)', ref="BW", instant=True, fmt="table"),
    tgt(f'max by (interface_name) (ifbrief_line_state{{{R}}})', ref="ST", instant=True, fmt="table"),
    tgt(f'sum by (interface_name) (increase_prometheus(ifstats_input_errors{{{R}}}[$__range]))', ref="ERR", instant=True, fmt="table"),
    tgt(f'sum by (interface_name) (increase_prometheus(ifstats_crc_errors{{{R}}}[$__range]))', ref="CRC", instant=True, fmt="table"),
    tgt(f'sum by (interface_name) (increase_prometheus(ifstats_input_drops{{{R}}}[$__range]))', ref="DIN", instant=True, fmt="table"),
    tgt(f'sum by (interface_name) (increase_prometheus(ifstats_output_drops{{{R}}}[$__range]))', ref="DOUT", instant=True, fmt="table"),
    tgt(f'sum by (interface_name) (increase_prometheus(ifstats_carrier_transitions{{{R}}}[$__range]))', ref="FLAP", instant=True, fmt="table"),
]

def col(name, props):
    return {"matcher": {"id": "byName", "options": name}, "properties": props}

def cell_bg(th):
    return [{"id": "custom.cellOptions", "value": {"type": "color-text"}}, {"id": "thresholds", "value": th},
            {"id": "color", "value": {"mode": "thresholds"}}]

err_th = thresholds((None, "text"), (1, SERIOUS))
P.append({
    "id": nid(), "type": "table", "title": "Todas as interfaces (clique no nome para detalhar)", "datasource": DS,
    "gridPos": {"x": 0, "y": y, "w": 24, "h": 14},
    "targets": tbl_targets,
    "transformations": [
        {"id": "merge", "options": {}},
        {"id": "organize", "options": {
            "excludeByName": {"Time": True},
            "renameByName": {"interface_name": "Interface", "Value #RX": "RX", "Value #TX": "TX", "Value #BW": "Capacidade",
                             "Value #ST": "Estado", "Value #ERR": "Erros entrada", "Value #CRC": "CRC",
                             "Value #DIN": "Drops entrada", "Value #DOUT": "Drops saída", "Value #FLAP": "Flaps"},
            "indexByName": {"interface_name": 0, "Value #ST": 1, "Value #BW": 2, "Value #RX": 3, "Value #TX": 4,
                            "Value #CRC": 5, "Value #ERR": 6, "Value #DIN": 7, "Value #DOUT": 8, "Value #FLAP": 9}}},
        {"id": "calculateField", "options": {"mode": "binary", "alias": "Uso RX %",
                                             "binary": {"left": "RX", "operator": "/", "right": "Capacidade"}, "replaceFields": False}},
    ],
    "fieldConfig": {"defaults": {"custom": {"align": "auto", "filterable": True, "cellOptions": {"type": "auto"}},
                                 "decimals": 0},
                    "overrides": [
                        col("Interface", [{"id": "links", "value": [{"title": "Detalhar interface",
                            "url": "/d/cisco-ifaces/cisco-interfaces?var-router=${router}&var-interface=${__value.raw:percentencode}&${__url_time_range}"}]},
                            {"id": "custom.width", "value": 260}]),
                        col("RX", [{"id": "unit", "value": "bps"}, {"id": "decimals", "value": 1}]),
                        col("TX", [{"id": "unit", "value": "bps"}, {"id": "decimals", "value": 1}]),
                        col("Capacidade", [{"id": "unit", "value": "bps"}]),
                        col("Uso RX %", [{"id": "unit", "value": "percentunit"}, {"id": "decimals", "value": 1},
                                      {"id": "max", "value": 1}, {"id": "min", "value": 0},
                                      {"id": "custom.cellOptions", "value": {"type": "gauge", "mode": "basic", "valueDisplayMode": "text"}},
                                      {"id": "thresholds", "value": thresholds((None, GOOD), (0.7, WARN), (0.85, SERIOUS), (0.95, CRIT))},
                                      {"id": "color", "value": {"mode": "thresholds"}}]),
                        col("Estado", [{"id": "mappings", "value": STATE_MAP},
                                       {"id": "custom.cellOptions", "value": {"type": "color-text"}}, {"id": "custom.width", "value": 110}]),
                        col("CRC", cell_bg(thresholds((None, "text"), (1, CRIT)))),
                        col("Erros entrada", cell_bg(err_th)),
                        col("Drops entrada", cell_bg(err_th)),
                        col("Drops saída", cell_bg(err_th)),
                        col("Flaps", cell_bg(thresholds((None, "text"), (1, WARN), (10, CRIT)))),
                    ]},
    "options": {"showHeader": True, "cellHeight": "sm", "sortBy": [{"displayName": "RX", "desc": True}],
                "footer": {"show": False}},
})
y += 14

P.append(row("Erros, drops e flaps", y)); y += 1
def errpanel(title, metric, x, yy, color_unit="short"):
    return ts(title, [tgt(f'topk(10, sum by (interface_name) (increase_prometheus(ifstats_{metric}{{{R}}}[$__rate_interval])) > 0)',
                          "{{interface_name}}")], x, yy, w=12, h=8, unit=color_unit, draw="bars", fill=60,
              legend_calcs=("sum", "max"))
P += [errpanel("Erros CRC", "crc_errors", 0, y), errpanel("Erros de entrada", "input_errors", 12, y)]
y += 8
P += [errpanel("Drops de entrada", "input_drops", 0, y), errpanel("Drops de saída", "output_drops", 12, y)]
y += 8
P += [errpanel("Flaps (carrier transitions)", "carrier_transitions", 0, y)]
P.append({"id": nid(), "type": "table", "title": "Alertas ativos", "datasource": DS,
          "gridPos": {"x": 12, "y": y, "w": 12, "h": 8},
          "targets": [tgt('ALERTS{alertstate="firing",' + R + '}', instant=True, fmt="table")],
          "transformations": [{"id": "organize", "options": {
              "excludeByName": {"Time": True, "Value": True, "__name__": True, "alertstate": True, "db": True,
                                "path": True, "subscription": True, "alertgroup": True, "source": True},
              "renameByName": {"alertname": "Alerta", "interface_name": "Interface", "severity": "Severidade"}}}],
          "fieldConfig": {"defaults": {}, "overrides": [
              col("Severidade", [{"id": "mappings", "value": [{"type": "value", "options": {
                  "critical": {"text": "CRÍTICO", "color": CRIT}, "warning": {"text": "ATENÇÃO", "color": WARN}}}]},
                  {"id": "custom.cellOptions", "value": {"type": "color-background"}}])]},
          "options": {"showHeader": True, "cellHeight": "sm"}})
y += 8

P.append(row("Sistema (CPU e memória)", y)); y += 1
P.append(ts("CPU total", [
    tgt(f'max(cpu_total_cpu_one_minute{{{R}}})', "1 min", "A"),
    tgt(f'max(cpu_total_cpu_five_minute{{{R}}})', "5 min", "B"),
    tgt(f'max(cpu_total_cpu_fifteen_minute{{{R}}})', "15 min", "C"),
], 0, y, w=12, h=8, unit="percent", legend_mode="list", fill=0,
   overrides=[fixed_color("1 min", "#9ec5f4"), fixed_color("5 min", RX), fixed_color("15 min", "#184f95")]))
P[-1]["fieldConfig"]["defaults"]["max"] = 100
P.append(ts("Memória", [
    tgt(f'sum(mem_ram_memory{{{R}}}) - sum(mem_free_physical_memory{{{R}}})', "Usada", "A"),
    tgt(f'sum(mem_free_physical_memory{{{R}}})', "Livre", "B"),
], 12, y, w=12, h=8, unit="bytes", stack=True, fill=40, legend_mode="list",
   overrides=[fixed_color("Usada", RX), fixed_color("Livre", NEUTRAL)]))
y += 8
P.append(bargauge("Top 15 processos por CPU (5 min)",
                  f'topk(15, max by (process_cpu_process_name) (cpu_process_cpu_process_cpu_five_minute{{{R},process_cpu_process_name!=""}}))',
                  "{{process_cpu_process_name}}", 0, y, w=24, h=9, unit="percent",
                  th=thresholds((None, RX), (20, WARN), (50, CRIT))))

overview = dashboard("cisco-overview", "Cisco - Visão Geral do Roteador", P, [var_router()], ["cisco"], LINKS)

# =====================================================================
# 2) Detalhe de interface
# =====================================================================
_id[0] = 0
P = []
y = 0
I = f'{R},{IFSEL}'

def estado_panel(x, y, w=6, h=4):
    """Uma interface: mostra UP/DOWN/ADMIN DOWN. Várias: contagem por estado."""
    LS = f'ifbrief_line_state{{{I}}}'
    ST = f'ifbrief_state{{{I}}}'
    single = f'(count({LS}) == 1)'
    multi = f'(count({LS}) > 1)'
    targets = [
        tgt(f'max({LS}) and on() {single}', "Estado", "A"),
        tgt(f'(count({LS} == 1) or vector(0)) and on() {multi}', "UP", "B"),
        tgt(f'(count(({LS} == 0) and ({ST} != 2)) or vector(0)) and on() {multi}', "DOWN", "C"),
        tgt(f'(count({ST} == 2) or vector(0)) and on() {multi}', "ADMIN DOWN", "D"),
    ]
    def ov(name, props): return {"matcher": {"id": "byName", "options": name}, "properties": props}
    return {"id": nid(), "type": "stat", "title": "Estado", "datasource": DS,
            "description": "Uma interface: estado do protocolo (UP / DOWN / ADMIN DOWN). "
                           "Várias interfaces ou All: quantas estão em cada estado. DOWN não inclui as desligadas com shutdown.",
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "fieldConfig": {"defaults": {"decimals": 0, "color": {"mode": "thresholds"},
                                         "thresholds": thresholds((None, NEUTRAL))},
                            "overrides": [
                                ov("Estado", [{"id": "mappings", "value": STATE_MAP}]),
                                ov("UP", [{"id": "thresholds", "value": thresholds((None, GOOD))}]),
                                ov("DOWN", [{"id": "thresholds", "value": thresholds((None, GOOD), (1, CRIT))}]),
                                ov("ADMIN DOWN", [{"id": "thresholds", "value": thresholds((None, NEUTRAL))}]),
                            ]},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "background", "graphMode": "none", "textMode": "value_and_name",
                        "justifyMode": "center", "orientation": "vertical", "wideLayout": True},
            "targets": targets}

P += [
    estado_panel(0, y, w=6),
    stat("Capacidade", f'(sum(ifbrief_bandwidth{{{I}}} and on(interface_name) ifbrief_line_state{{{I}}} == 1) or sum(ifbrief_bandwidth{{{I}}})) * 1000', 6, y, w=3, unit="bps", graph=False),
    stat("RX agora", f'sum(rate(ifstats_bytes_received{{{I}}}[$__rate_interval])) * 8', 9, y, w=4, unit="bps", th=thresholds((None, RX))),
    stat("TX agora", f'sum(rate(ifstats_bytes_sent{{{I}}}[$__rate_interval])) * 8', 13, y, w=4, unit="bps", th=thresholds((None, TX))),
    stat("Uso máx. (RX/TX)", f'100 * 8 * max(label_replace(sum(rate(ifstats_bytes_received{{{I}}}[5m])),"d","rx","","") '
         f'or label_replace(sum(rate(ifstats_bytes_sent{{{I}}}[5m])),"d","tx","","")) / ((sum(ifbrief_bandwidth{{{I}}} and on(interface_name) ifbrief_line_state{{{I}}} == 1) or sum(ifbrief_bandwidth{{{I}}})) * 1000)',
         17, y, w=4, unit="percent", decimals=1, th=thresholds((None, GOOD), (70, WARN), (85, SERIOUS), (95, CRIT))),
    stat("Problemas no período", f'sum(increase_prometheus(ifstats_input_errors{{{I}}}[$__range])) + sum(increase_prometheus(ifstats_input_drops{{{I}}}[$__range])) '
         f'+ sum(increase_prometheus(ifstats_output_drops{{{I}}}[$__range])) + sum(increase_prometheus(ifstats_carrier_transitions{{{I}}}[$__range]))',
         21, y, w=3, graph=False, decimals=0, th=thresholds((None, GOOD), (1, WARN)),
         desc="Soma de erros de entrada, drops e flaps no período selecionado."),
]
y += 4
P.append(ts("Tráfego total das interfaces selecionadas", [
    tgt(f'sum(rate(ifstats_bytes_received{{{I}}}[$__rate_interval])) * 8', "RX", "A"),
    tgt(f'sum(rate(ifstats_bytes_sent{{{I}}}[$__rate_interval])) * 8', "TX", "B"),
    tgt(f'sum(ifbrief_bandwidth{{{I}}}) * 1000 and on() (count(ifbrief_line_state{{{I}}}) == 1)', "Capacidade", "C"),
], 0, y, w=24, h=9, unit="bps", legend_mode="list",
   overrides=[fixed_color("RX", RX), fixed_color("TX", TX), fixed_color("Capacidade", NEUTRAL),
              {"matcher": {"id": "byName", "options": "Capacidade"},
               "properties": [{"id": "custom.fillOpacity", "value": 0}, {"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [8, 6]}},
                              {"id": "custom.lineWidth", "value": 1}]}]))
y += 9
P.append(ts("RX por interface (top 10 das selecionadas)", [
    tgt(f'topk(10, sum by (interface_name) (rate(ifstats_bytes_received{{{I}}}[$__rate_interval])) * 8)', "{{interface_name}}")],
    0, y, w=12, h=9, unit="bps", fill=0, legend_calcs=("mean", "max", "lastNotNull")))
P.append(ts("TX por interface (top 10 das selecionadas)", [
    tgt(f'topk(10, sum by (interface_name) (rate(ifstats_bytes_sent{{{I}}}[$__rate_interval])) * 8)', "{{interface_name}}")],
    12, y, w=12, h=9, unit="bps", fill=0, legend_calcs=("mean", "max", "lastNotNull")))
y += 9
P.append(ts("Pacotes por segundo", [
    tgt(f'sum(rate(ifstats_packets_received{{{I}}}[$__rate_interval]))', "RX", "A"),
    tgt(f'sum(rate(ifstats_packets_sent{{{I}}}[$__rate_interval]))', "TX", "B"),
], 0, y, w=12, h=8, unit="pps", legend_mode="list", overrides=[fixed_color("RX", RX), fixed_color("TX", TX)]))
P.append(ts("Tamanho médio de pacote", [
    tgt(f'sum(rate(ifstats_bytes_received{{{I}}}[5m])) / sum(rate(ifstats_packets_received{{{I}}}[5m]))', "RX", "A"),
    tgt(f'sum(rate(ifstats_bytes_sent{{{I}}}[5m])) / sum(rate(ifstats_packets_sent{{{I}}}[5m]))', "TX", "B"),
], 12, y, w=12, h=8, unit="decbytes", legend_mode="list", fill=0, overrides=[fixed_color("RX", RX), fixed_color("TX", TX)]))
y += 8
def by_if(metric, label, ref):
    return tgt(f'sum by (interface_name) (increase_prometheus(ifstats_{metric}{{{I}}}[$__rate_interval])) > 0',
               "{{interface_name}} · " + label, ref)
P.append(ts("Erros por interface (origem)", [
    by_if("crc_errors", "CRC", "A"), by_if("input_errors", "erro entrada", "B"),
    by_if("output_errors", "erro saída", "C"), by_if("giant_packets_received", "giant (maior que MTU)", "D"),
    by_if("runt_packets_received", "runt", "E"),
], 0, y, w=12, h=9, draw="bars", fill=70, legend_calcs=("sum", "max"),
   desc="Cada barra mostra a interface e o tipo de erro. Giant = quadro maior que o MTU (normalmente MTU diferente do vizinho). "
        "Runt = quadro menor que o mínimo. CRC = corrupção física (fibra, óptico, conector)."))
P.append(ts("Drops por interface (origem)", [
    by_if("input_drops", "entrada", "A"), by_if("output_drops", "saída", "B"),
    by_if("input_queue_drops", "fila entrada", "C"), by_if("output_queue_drops", "fila saída", "D"),
], 12, y, w=12, h=9, draw="bars", fill=70, legend_calcs=("sum", "max"),
   desc="Drops de entrada acompanham erros/giants/VLAN desconhecida. Drops de saída e de fila indicam congestionamento ou QoS."))
y += 9
P.append(ts("Flaps por interface (carrier transitions)", [by_if("carrier_transitions", "flap", "A")],
    0, y, w=12, h=7, draw="bars", fill=70, legend_calcs=("sum",)))
P.append(ts("Broadcast / Multicast (pps)", [
    tgt(f'sum(rate(ifstats_broadcast_packets_received{{{I}}}[$__rate_interval]))', "Broadcast RX", "A"),
    tgt(f'sum(rate(ifstats_multicast_packets_received{{{I}}}[$__rate_interval]))', "Multicast RX", "B"),
], 12, y, w=12, h=7, unit="pps", legend_mode="list", fill=0,
   overrides=[fixed_color("Broadcast RX", "#6250d6"), fixed_color("Multicast RX", "#1baf7a")]))

var_if = {"name": "interface", "label": "Interface", "type": "query", "datasource": DS,
          "query": {"query": 'label_values(ifstats_bytes_received{source=~"$router"}, interface_name)', "refId": "i"},
          "definition": 'label_values(ifstats_bytes_received{source=~"$router"}, interface_name)',
          "refresh": 2, "sort": 1, "multi": True, "includeAll": True,
          "allValue": ".*GigE[0-9/]+",
          "current": {"selected": True, "text": ["All"], "value": ["$__all"]}}
detail = dashboard("cisco-ifaces", "Cisco - Interfaces", P, [var_router(), var_if], ["cisco"], LINKS)


# =====================================================================
# 3) CPU e memória
# =====================================================================
_id[0] = 0
P = []
y = 0
PROC = f'cpu_process_cpu_process_cpu_{{w}}_minute{{{{{R},process_cpu_process_name!=""}}}}'
MEMUSED = f'(sum(mem_ram_memory{{{R}}}) - sum(mem_free_physical_memory{{{R}}}))'
def gauge(title, expr, x, yy, w=4, h=6, unit="percent", th=None, desc="", mx=100):
    return {"id": nid(), "type": "gauge", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": yy, "w": w, "h": h},
            "fieldConfig": {"defaults": {"unit": unit, "min": 0, "max": mx, "decimals": 1,
                                         "color": {"mode": "thresholds"},
                                         "thresholds": th or thresholds((None, GOOD), (60, WARN), (80, CRIT))}, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "showThresholdMarkers": True, "showThresholdLabels": False, "minVizHeight": 75},
            "targets": [tgt(expr)]}
P.append(row("Processador", y)); y += 1
P += [
    gauge("CPU — 1 min", f'max(cpu_total_cpu_one_minute{{{R}}})', 0, y),
    gauge("CPU — 5 min", f'max(cpu_total_cpu_five_minute{{{R}}})', 4, y),
    gauge("CPU — 15 min", f'max(cpu_total_cpu_fifteen_minute{{{R}}})', 8, y),
]
P.append(ts("CPU total ao longo do tempo", [
    tgt(f'max(cpu_total_cpu_one_minute{{{R}}})', "1 min", "A"),
    tgt(f'max(cpu_total_cpu_five_minute{{{R}}})', "5 min", "B"),
    tgt(f'max(cpu_total_cpu_fifteen_minute{{{R}}})', "15 min", "C"),
], 12, y, w=12, h=6, unit="percent", legend_mode="list", fill=0,
   overrides=[fixed_color("1 min", "#9ec5f4"), fixed_color("5 min", RX), fixed_color("15 min", "#184f95")]))
P[-1]["fieldConfig"]["defaults"]["max"] = 100
y += 6
P.append(ts("Top 10 processos — CPU (média 1 min)", [
    tgt('topk(10, max by (process_cpu_process_name) (' + PROC.format(w="one") + '))', "{{process_cpu_process_name}}")],
    0, y, w=24, h=9, unit="percent", fill=0, legend_calcs=("mean", "max", "lastNotNull")))
y += 9
P.append(bargauge("Top 15 processos agora (média 5 min)",
                  'topk(15, max by (process_cpu_process_name) (' + PROC.format(w="five") + '))',
                  "{{process_cpu_process_name}}", 0, y, w=10, h=12, unit="percent",
                  th=thresholds((None, RX), (20, WARN), (50, CRIT))))
P.append({"id": nid(), "type": "table", "title": f"Todos os processos (clique no cabeçalho para ordenar)", "datasource": DS,
          "gridPos": {"x": 10, "y": y, "w": 14, "h": 12},
          "targets": [tgt('max by (process_cpu_process_name) (' + PROC.format(w=w) + ')', ref=w.upper()[:3], instant=True, fmt="table")
                      for w in ("one", "five", "fifteen")],
          "transformations": [{"id": "merge", "options": {}},
                              {"id": "organize", "options": {"excludeByName": {"Time": True},
                               "renameByName": {"process_cpu_process_name": "Processo", "Value #ONE": "1 min",
                                                "Value #FIV": "5 min", "Value #FIF": "15 min"}}}],
          "fieldConfig": {"defaults": {"unit": "percent", "decimals": 0, "custom": {"filterable": True},
                                       "color": {"mode": "thresholds"},
                                       "thresholds": thresholds((None, "text"), (20, WARN), (50, CRIT))},
                          "overrides": [{"matcher": {"id": "byName", "options": "Processo"},
                                         "properties": [{"id": "unit", "value": "string"}, {"id": "custom.width", "value": 280}]}]},
          "options": {"showHeader": True, "cellHeight": "sm", "sortBy": [{"displayName": "1 min", "desc": True}]}})
for o in P[-1]["fieldConfig"]["overrides"]: pass
P[-1]["fieldConfig"]["defaults"]["custom"]["cellOptions"] = {"type": "color-text"}
y += 12

P.append(row("Memória", y)); y += 1
P += [
    gauge("Memória usada", f'100 * {MEMUSED} / sum(mem_ram_memory{{{R}}})', 0, y,
          th=thresholds((None, GOOD), (75, WARN), (90, CRIT))),
    stat("Total", f'sum(mem_ram_memory{{{R}}})', 4, y, w=4, h=3, unit="bytes", graph=False, decimals=1),
    stat("Usada", MEMUSED, 8, y, w=4, h=3, unit="bytes", graph=False, decimals=1, th=thresholds((None, RX))),
    stat("Livre (física)", f'sum(mem_free_physical_memory{{{R}}})', 4, y + 3, w=4, h=3, unit="bytes", graph=False, decimals=1,
         th=thresholds((None, GOOD))),
    stat("Livre p/ aplicações", f'sum(mem_free_application_memory{{{R}}})', 8, y + 3, w=4, h=3, unit="bytes",
         graph=False, decimals=1, th=thresholds((None, GOOD)),
         desc="Memória disponível para processos do IOS-XR."),
]
P.append(ts("Memória ao longo do tempo", [
    tgt(MEMUSED, "Usada", "A"),
    tgt(f'sum(mem_free_physical_memory{{{R}}})', "Livre", "B"),
], 12, y, w=12, h=6, unit="bytes", stack=True, fill=40, legend_mode="list",
   overrides=[fixed_color("Usada", RX), fixed_color("Livre", NEUTRAL)]))
y += 6

resources = dashboard("cisco-resources", "Cisco - CPU e Memória", P, [var_router()], ["cisco"], LINKS)

for name, d in [("cisco-overview.json", overview), ("cisco-interfaces.json", detail), ("cisco-resources.json", resources)]:
    with open(f"{OUT}/{name}", "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
print("ok")
