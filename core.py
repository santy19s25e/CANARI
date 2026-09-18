from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

METRICS = {
    "ch4_vol_pct": (0, 100), "o2_vol_pct": (0, 100),
    "temperature_c": (-40, 125), "humidity_pct": (0, 100),
}
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class InputError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def utc_iso(ts=None):
    return datetime.fromtimestamp(time.time() if ts is None else ts, timezone.utc).isoformat(timespec="milliseconds")


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise InputError("captured_at debe ser ISO 8601 con zona horaria")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if d.tzinfo is None:
            raise ValueError("sin zona")
        return d.timestamp()
    except (ValueError, OverflowError):
        raise InputError("Fecha inválida o sin zona horaria")


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    if cfg.get("schema_version") != 1:
        raise ValueError("Versión de configuración no soportada")
    positive = ["sample_interval_seconds", "stale_after_seconds", "ch4_warning_vol_pct",
                "o2_min_vol_pct", "o2_max_vol_pct", "temperature_warning_c", "temperature_alarm_c"]
    if any(not finite_number(cfg.get(k)) or cfg[k] <= 0 for k in positive):
        raise ValueError("Los parámetros deben ser números finitos positivos")
    if not 0 < cfg["sample_interval_seconds"] < cfg["stale_after_seconds"] <= 3600:
        raise ValueError("El vencimiento debe ser mayor al intervalo y no superar 3600 s")
    if not 0 < cfg["o2_min_vol_pct"] < cfg["o2_max_vol_pct"] <= 100:
        raise ValueError("Rango de oxígeno inválido")
    if cfg["temperature_warning_c"] >= cfg["temperature_alarm_c"]:
        raise ValueError("Prealerta térmica debe ser menor que alarma")
    if not isinstance(cfg.get("nodes"), list) or not 1 <= len(cfg["nodes"]) <= 100:
        raise ValueError("Configure entre 1 y 100 nodos")
    seen = set()
    for node in cfg["nodes"]:
        nid = node.get("id", "")
        if not isinstance(nid, str) or not ID_RE.fullmatch(nid) or nid in seen:
            raise ValueError("Identificador de nodo inválido o repetido")
        seen.add(nid)
        if not isinstance(node.get("label"), str) or not 1 <= len(node["label"]) <= 80:
            raise ValueError("Etiqueta inválida")
        if node.get("source") not in ("simulation", "laboratory"):
            raise ValueError("source debe ser simulation o laboratory")
        alarm = node.get("ch4_alarm_vol_pct")
        if not finite_number(alarm) or not cfg["ch4_warning_vol_pct"] < alarm <= 100:
            raise ValueError("Umbral de metano inválido")
    return cfg


def validate(data, cfg, now):
    if not isinstance(data, dict):
        raise InputError("Se requiere un objeto JSON")
    allowed = {"node_id", "sample_id", "captured_at", "source", "device_status", "calibration_ref", "values"}
    if set(data) - allowed:
        raise InputError("Campos desconocidos en la muestra")
    for key in ("node_id", "sample_id"):
        if not isinstance(data.get(key), str) or not ID_RE.fullmatch(data[key]):
            raise InputError(f"{key} inválido")
    node = next((n for n in cfg["nodes"] if n["id"] == data["node_id"]), None)
    if not node:
        raise InputError("Nodo no registrado")
    if data.get("source") != node["source"]:
        raise InputError("El origen no coincide con la configuración del nodo")
    if data.get("device_status") not in ("ok", "fault", "uncalibrated"):
        raise InputError("device_status debe ser ok, fault o uncalibrated")
    cal = data.get("calibration_ref", "")
    if not isinstance(cal, str) or len(cal) > 100:
        raise InputError("Referencia de calibración inválida")
    if data["source"] == "laboratory" and data["device_status"] == "ok" and not cal.strip():
        raise InputError("Lectura de laboratorio ok requiere referencia de calibración declarada")
    captured = timestamp(data.get("captured_at"))
    if captured > now + 5 or captured < now - 86400:
        raise InputError("La fecha debe estar entre hace 24 h y 5 s en el futuro")
    values = data.get("values")
    if not isinstance(values, dict) or set(values) != set(METRICS):
        raise InputError("values debe contener ch4_vol_pct, o2_vol_pct, temperature_c y humidity_pct")
    for name, (lo, hi) in METRICS.items():
        value = values[name]
        if value is not None and (not finite_number(value) or not lo <= value <= hi):
            raise InputError(f"{name} fuera de rango o no numérico; use null para dato ausente")
    return node, captured


def classify(values, device_status, cfg, node):
    """No equipara ausencia de alarma con atmósfera segura."""
    if device_status != "ok":
        return "FALLO", ["Sensor en falla o sin calibración declarada"]
    missing = [k for k in METRICS if values[k] is None]
    critical, warnings = [], []
    ch4, o2, temp = (values[k] for k in ("ch4_vol_pct", "o2_vol_pct", "temperature_c"))
    if ch4 is not None:
        if ch4 >= node["ch4_alarm_vol_pct"]:
            critical.append("Metano en umbral de alarma del nodo")
        elif ch4 >= cfg["ch4_warning_vol_pct"]:
            warnings.append("Prealerta de metano configurada")
    if o2 is not None and not cfg["o2_min_vol_pct"] <= o2 <= cfg["o2_max_vol_pct"]:
        critical.append("Oxígeno fuera del intervalo configurado")
    if temp is not None:
        if temp >= cfg["temperature_alarm_c"]:
            critical.append("Temperatura en alarma de demostración")
        elif temp >= cfg["temperature_warning_c"]:
            warnings.append("Prealerta de temperatura de demostración")
    missing_reason = ["Datos ausentes: " + ", ".join(missing)] if missing else []
    if critical:
        return "ALARMA", critical + warnings + missing_reason
    if missing:
        return "INCOMPLETO", warnings + missing_reason
    if warnings:
        return "PRECAUCION", warnings
    return "SIN_ALERTA", ["Sin umbrales superados en las variables disponibles"]


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS readings (
 id INTEGER PRIMARY KEY, node_id TEXT NOT NULL, sample_id TEXT NOT NULL,
 captured_ts REAL NOT NULL, received_ts REAL NOT NULL, source TEXT NOT NULL,
 device_status TEXT NOT NULL, calibration_ref TEXT NOT NULL,
 ch4_vol_pct REAL, o2_vol_pct REAL, temperature_c REAL, humidity_pct REAL,
 level TEXT NOT NULL, reasons TEXT NOT NULL, config_hash TEXT NOT NULL,
 payload_hash TEXT NOT NULL, UNIQUE(node_id, sample_id));
CREATE INDEX IF NOT EXISTS readings_latest ON readings(node_id, captured_ts DESC, id DESC);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, node_id TEXT NOT NULL, created_ts REAL NOT NULL,
 level TEXT NOT NULL, reasons TEXT NOT NULL, reading_id INTEGER,
 acknowledged_ts REAL, acknowledged_by TEXT,
 FOREIGN KEY(reading_id) REFERENCES readings(id));
CREATE TABLE IF NOT EXISTS node_state (
 node_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS configurations (
 hash TEXT PRIMARY KEY, created_ts REAL NOT NULL, body TEXT NOT NULL);
"""


class Store:
    def __init__(self, path, cfg):
        self.path, self.cfg = str(path), cfg
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(cfg, sort_keys=True, ensure_ascii=False)
        self.config_hash = hashlib.sha256(body.encode()).hexdigest()
        with self.db() as db:
            db.executescript(SCHEMA)
            db.execute("INSERT OR IGNORE INTO configurations VALUES(?,?,?)", (self.config_hash, time.time(), body))

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def latest(self, db, node_id):
        return db.execute("SELECT * FROM readings WHERE node_id=? ORDER BY captured_ts DESC,id DESC LIMIT 1", (node_id,)).fetchone()

    def state(self, row, node, now):
        if row is None:
            return "SIN_DATOS", ["Todavía no se han recibido muestras"]
        if now - row["captured_ts"] >= self.cfg["stale_after_seconds"] or now - row["received_ts"] >= self.cfg["stale_after_seconds"]:
            return "SIN_DATOS", ["Muestra vencida o comunicación interrumpida"]
        return classify(dict(row), row["device_status"], self.cfg, node)

    def transition(self, db, node, row, now):
        level, reasons = self.state(row, node, now)
        fingerprint = json.dumps([level, reasons], ensure_ascii=False)
        old = db.execute("SELECT fingerprint FROM node_state WHERE node_id=?", (node["id"],)).fetchone()
        if old is None or old[0] != fingerprint:
            db.execute("INSERT INTO events(node_id,created_ts,level,reasons,reading_id) VALUES(?,?,?,?,?)",
                       (node["id"], now, level, json.dumps(reasons, ensure_ascii=False), row["id"] if row else None))
            db.execute("INSERT INTO node_state VALUES(?,?) ON CONFLICT(node_id) DO UPDATE SET fingerprint=excluded.fingerprint",
                       (node["id"], fingerprint))
        return level, reasons

    def ingest(self, data, now=None):
        now = time.time() if now is None else now
        node, captured = validate(data, self.cfg, now)
        payload_hash = hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT id,payload_hash FROM readings WHERE node_id=? AND sample_id=?", (node["id"], data["sample_id"])).fetchone()
            if existing:
                if existing["payload_hash"] != payload_hash:
                    raise InputError("sample_id repetido con contenido diferente", 409)
                return {"id": existing["id"], "duplicate": True}
            level, reasons = classify(data["values"], data["device_status"], self.cfg, node)
            values = [data["values"][k] for k in METRICS]
            cur = db.execute("""INSERT INTO readings(node_id,sample_id,captured_ts,received_ts,source,device_status,
                calibration_ref,ch4_vol_pct,o2_vol_pct,temperature_c,humidity_pct,level,reasons,config_hash,payload_hash)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (node["id"], data["sample_id"], captured, now, data["source"],
                data["device_status"], data.get("calibration_ref", ""), *values, level,
                json.dumps(reasons, ensure_ascii=False), self.config_hash, payload_hash))
            latest = self.latest(db, node["id"])
            self.transition(db, node, latest, now)
            return {"id": cur.lastrowid, "duplicate": False, "level": level, "historical": latest["id"] != cur.lastrowid}

    def sweep(self, now=None):
        now = time.time() if now is None else now
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            for node in self.cfg["nodes"]:
                self.transition(db, node, self.latest(db, node["id"]), now)

    def snapshot(self, now=None):
        now = time.time() if now is None else now
        nodes = []
        with self.db() as db:
            for node in self.cfg["nodes"]:
                row = self.latest(db, node["id"])
                level, reasons = self.state(row, node, now)
                nodes.append({**node, "level": level, "reasons": reasons,
                    "latest": dict(row) if row else None,
                    "age_seconds": round(max(0, now-row["captured_ts"]), 1) if row else None})
        return {"server_time": utc_iso(now), "nodes": nodes, "config": self.cfg, "config_hash": self.config_hash}

    def history(self, node_id=None, limit=100, before_id=None, since=None):
        conditions, args = [], []
        for cond, val in [("node_id=?", node_id), ("id<?", before_id), ("captured_ts>=?", since)]:
            if val is not None:
                conditions.append(cond); args.append(val)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM readings" + where + " ORDER BY id DESC LIMIT ?", (*args, limit))]

    def events(self, limit=100):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))]

    def acknowledge(self, event_id):
        with self.db() as db:
            cur = db.execute("UPDATE events SET acknowledged_ts=?,acknowledged_by='operador_local' WHERE id=? AND acknowledged_ts IS NULL", (time.time(), event_id))
            if not cur.rowcount and not db.execute("SELECT 1 FROM events WHERE id=?", (event_id,)).fetchone():
                raise InputError("Evento no encontrado", 404)

    def backup(self, destination):
        with self.db() as source, sqlite3.connect(str(destination)) as target:
            source.backup(target)
