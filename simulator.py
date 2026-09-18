import argparse
import json
import math
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen
from core import utc_iso


def sample(node_id="N01", step=0, scenario="cycle", session=None):
    cycle = (step // 5) % 5 if scenario == "cycle" else {"normal": 0, "warning": 1, "alarm": 2, "oxygen": 3, "missing": 4}[scenario]
    ch4 = [0.2, 0.7, 1.6, 0.2, None][cycle]
    return {"node_id": node_id, "sample_id": f"{session or uuid.uuid4().hex}_{step}", "captured_at": utc_iso(),
            "source": "simulation", "device_status": "ok", "calibration_ref": "",
            "values": {"ch4_vol_pct": ch4, "o2_vol_pct": 18.8 if cycle == 3 else 20.9,
                       "temperature_c": round(24 + math.sin(step / 4), 2), "humidity_pct": round(65 + 3 * math.cos(step / 3), 2)}}


def demo_loop(store, stop):
    step, session = 0, uuid.uuid4().hex
    while not stop.is_set():
        for i, node in enumerate(store.cfg["nodes"]):
            if node["source"] == "simulation":
                store.ingest(sample(node["id"], step + i * 5, session=session))
        step += 1
        stop.wait(store.cfg["sample_interval_seconds"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--key-file", type=Path, default=Path(__file__).resolve().parent / "data" / "ingest.key")
    parser.add_argument("--node", default="N01")
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--interval", type=float, default=3)
    parser.add_argument("--scenario", choices=["cycle", "normal", "warning", "alarm", "oxygen", "missing"], default="cycle")
    args = parser.parse_args()
    if args.count < 1 or args.interval < 0:
        parser.error("count debe ser positivo e interval no negativo")
    key = args.key_file.read_text().strip()
    session = uuid.uuid4().hex
    for step in range(args.count):
        payload = sample(args.node, step, args.scenario, session)
        req = Request(args.url.rstrip("/") + "/api/telemetry", json.dumps(payload).encode(),
                      {"Content-Type": "application/json", "Authorization": "Bearer " + key})
        with urlopen(req, timeout=10) as r:
            print(r.status, r.read().decode())
        if step + 1 < args.count:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
