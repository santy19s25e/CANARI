import argparse
import csv
import io
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from core import InputError, METRICS, Store, load_config, timestamp, utc_iso

ROOT = Path(__file__).resolve().parent


def read_keys(data_dir):
    data_dir.mkdir(parents=True, exist_ok=True)
    keys = {}
    for role in ("operator", "ingest"):
        path = data_dir / f"{role}.key"
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(secrets.token_urlsafe(32))
        keys[role] = path.read_text(encoding="utf-8").strip()
        if len(keys[role]) < 24:
            raise ValueError("Clave demasiado corta")
    return keys


def create_server(store, keys, host="127.0.0.1", port=8000):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CanariLab/1.0"

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, fmt, *args):
            pass

        def send(self, status, body, content_type="application/json; charset=utf-8", extra=None):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def authenticate(self, role):
            supplied = self.headers.get("Authorization", "")
            if not secrets.compare_digest(supplied, "Bearer " + keys[role]):
                raise InputError("Clave ausente o inválida", 401)

        def json_body(self):
            if self.headers.get("Transfer-Encoding"):
                raise InputError("Transfer-Encoding no soportado")
            if self.headers.get_content_type() != "application/json":
                raise InputError("Se requiere Content-Type application/json", 415)
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise InputError("Content-Length inválido")
            if not 0 < length <= 8192:
                raise InputError("Cuerpo ausente o mayor que 8192 bytes", 413)
            def bad_constant(value):
                raise ValueError(value)
            try:
                return json.loads(self.rfile.read(length), parse_constant=bad_constant)
            except (ValueError, UnicodeDecodeError):
                raise InputError("JSON inválido; no se permiten NaN ni Infinity")

        def do_GET(self):
            try:
                url = urlsplit(self.path)
                public = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}
                if url.path in public:
                    suffix = {"/": "text/html", "/app.js": "text/javascript", "/style.css": "text/css"}[url.path]
                    return self.send(200, (ROOT / "web" / public[url.path]).read_bytes(), suffix + "; charset=utf-8")
                if url.path == "/health":
                    return self.send(200, {"service": "CANARI", "mode": "laboratory"})
                self.authenticate("operator")
                q = parse_qs(url.query)
                if url.path == "/api/status":
                    return self.send(200, store.snapshot())
                if url.path == "/api/events":
                    return self.send(200, store.events())
                if url.path in ("/api/readings", "/api/export.csv"):
                    try:
                        limit = int(q.get("limit", ["100"])[0])
                        before = int(q["before_id"][0]) if "before_id" in q else None
                        if not 1 <= limit <= 10000 or (before is not None and before < 1):
                            raise ValueError()
                    except ValueError:
                        raise InputError("limit debe estar entre 1 y 10000; before_id debe ser positivo")
                    node = q.get("node_id", [None])[0]
                    if node and node not in {n["id"] for n in store.cfg["nodes"]}:
                        raise InputError("Nodo no registrado")
                    since = timestamp(q["since"][0]) if "since" in q else None
                    rows = store.history(node, limit, before, since)
                    if url.path.endswith(".csv"):
                        out = io.StringIO(newline="")
                        fields = ["id", "node_id", "sample_id", "captured_at", "received_at", "source", "device_status", *METRICS,
                                  "level", "calibration_ref", "config_hash"]
                        writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
                        writer.writeheader()
                        for row in rows:
                            row.update(captured_at=utc_iso(row["captured_ts"]), received_at=utc_iso(row["received_ts"]))
                            # Evita fórmulas al abrir texto externo en una hoja de cálculo.
                            for k in ("calibration_ref", "node_id", "sample_id"):
                                if row[k].startswith(("=", "+", "-", "@", "\t", "\r")):
                                    row[k] = "'" + row[k]
                            writer.writerow(row)
                        return self.send(200, out.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", {"Content-Disposition": 'attachment; filename="canari_lecturas.csv"'})
                    return self.send(200, {"readings": rows, "next_before_id": rows[-1]["id"] if len(rows) == limit else None})
                raise InputError("Ruta no encontrada", 404)
            except InputError as e:
                self.send(e.status, {"error": str(e)})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.send(500, {"error": "Error interno de almacenamiento o servidor"})

        def do_POST(self):
            try:
                path = urlsplit(self.path).path
                if path == "/api/telemetry":
                    self.authenticate("ingest")
                    result = store.ingest(self.json_body())
                    return self.send(200 if result["duplicate"] else 201, result)
                if path.startswith("/api/events/") and path.endswith("/ack"):
                    self.authenticate("operator")
                    try:
                        event_id = int(path.split("/")[3])
                    except (ValueError, IndexError):
                        raise InputError("Identificador de evento inválido")
                    store.acknowledge(event_id)
                    return self.send(200, {"acknowledged": True, "note": "Reconocer no elimina la condición de alarma"})
                raise InputError("Ruta no encontrada", 404)
            except InputError as e:
                self.send(e.status, {"error": str(e)})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.send(500, {"error": "Error interno de almacenamiento o servidor"})

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description="CANARI - demostración local de monitoreo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--demo", action="store_true", help="Generar datos simulados cada 3 segundos")
    args = parser.parse_args()
    cfg = load_config(args.config)
    store = Store(args.data_dir / "canari.sqlite3", cfg)
    keys = read_keys(args.data_dir)
    server = create_server(store, keys, args.host, args.port)
    stop = threading.Event()
    def monitor():
        while not stop.is_set():
            try:
                store.sweep()
            except Exception as exc:
                print("No se pudo registrar el estado:", type(exc).__name__, flush=True)
            stop.wait(1)
    threading.Thread(target=monitor, daemon=True).start()
    if args.demo:
        from simulator import demo_loop
        threading.Thread(target=demo_loop, args=(store, stop), daemon=True).start()
    print(f"CANARI laboratorio: http://{args.host}:{args.port}", flush=True)
    print("Clave de operador (pegar en el panel):", keys["operator"], flush=True)
    print("Claves guardadas en:", args.data_dir.resolve(), flush=True)
    print("Datos simulados. No utilizar para decisiones de seguridad minera.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Cerrando CANARI")
    finally:
        stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
