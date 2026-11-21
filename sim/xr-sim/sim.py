"""Simula roteadores IOS-XR enviando telemetria MDT (gRPC dial-out, kvGPB).

Cada roteador abre seu próprio stream gRPC para o coletor e envia os
generic-counters das interfaces a cada INTERVAL segundos. Algumas interfaces
geram erros CRC e drops de propósito, para disparar os alertas.
"""
import os
import random
import threading
import time

import grpc

import mdt_dialout_pb2 as dpb
import mdt_dialout_pb2_grpc as dgrpc
import telemetry_pb2 as tpb

TARGET = os.environ.get("TARGET", "telegraf:57000")
ROUTERS = os.environ.get("ROUTERS", "sim-router-1").split(",")
INTERVAL = float(os.environ.get("INTERVAL", "10"))
PATH = "Cisco-IOS-XR-infra-statsd-oper:infra-statistics/interfaces/interface/latest/generic-counters"
IFACES = ["HundredGigE0/0/0/0", "HundredGigE0/0/0/1", "TenGigE0/0/0/2", "TenGigE0/0/0/3"]


def u64(name, v):
    return tpb.TelemetryField(name=name, uint64_value=int(v))


class Router:
    def __init__(self, name, idx):
        self.name = name
        self.c = {i: dict.fromkeys(
            ["bytes-received", "bytes-sent", "packets-received", "packets-sent",
             "input-errors", "crc-errors", "input-drops", "output-drops",
             "output-errors"], 0) for i in IFACES}
        # Problemas injetados: CRC em uma interface, drops em outra
        self.crc_iface = IFACES[(idx + 2) % len(IFACES)]
        self.drop_iface = IFACES[(idx + 3) % len(IFACES)]

    def tick(self):
        for i, c in self.c.items():
            bps = random.uniform(2e8, 8e9)
            b = bps / 8 * INTERVAL
            c["bytes-received"] += b
            c["bytes-sent"] += b * random.uniform(0.6, 1.1)
            c["packets-received"] += b / 800
            c["packets-sent"] += b / 820
            if i == self.crc_iface:
                n = random.randint(5, 40)
                c["crc-errors"] += n
                c["input-errors"] += n
            if i == self.drop_iface:
                c["input-drops"] += random.randint(100, 600)
                c["output-drops"] += random.randint(100, 600)

    def message(self, collection_id):
        now = int(time.time() * 1000)
        rows = []
        for i, c in self.c.items():
            rows.append(tpb.TelemetryField(timestamp=now, fields=[
                tpb.TelemetryField(name="keys", fields=[
                    tpb.TelemetryField(name="interface-name", string_value=i)]),
                tpb.TelemetryField(name="content", fields=[u64(k, v) for k, v in c.items()]),
            ]))
        return tpb.Telemetry(
            node_id_str=self.name, subscription_id_str="sim", encoding_path=PATH,
            collection_id=collection_id, collection_start_time=now, msg_timestamp=now,
            collection_end_time=now, data_gpbkv=rows)


def run(router):
    req = 0
    while True:
        try:
            with grpc.insecure_channel(TARGET) as ch:
                stub = dgrpc.gRPCMdtDialoutStub(ch)

                def gen():
                    nonlocal req
                    while True:
                        router.tick()
                        req += 1
                        data = router.message(req).SerializeToString()
                        yield dpb.MdtDialoutArgs(ReqId=req, data=data)
                        time.sleep(INTERVAL)

                print(f"[{router.name}] conectando em {TARGET}", flush=True)
                for _ in stub.MdtDialout(gen()):
                    pass
        except Exception as e:  # reconecta sempre
            print(f"[{router.name}] erro: {e}; reconectando em 5s", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    for idx, name in enumerate(ROUTERS):
        threading.Thread(target=run, args=(Router(name.strip(), idx),), daemon=True).start()
    while True:
        time.sleep(3600)
