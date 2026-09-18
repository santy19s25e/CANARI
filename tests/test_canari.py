import copy
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from core import InputError, Store, load_config, utc_iso
from server import create_server
from simulator import sample

ROOT = Path(__file__).resolve().parents[1]
BASE = 1800000000.0


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = load_config(ROOT / "config.json")
        self.store = Store(Path(self.tmp.name) / "test.sqlite3", self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def reading(self, ch4=.2, node="N01", sid="s1", when=BASE):
        p = sample(node, scenario="normal")
        p.update(sample_id=sid, captured_at=utc_iso(when))
        p["values"]["ch4_vol_pct"] = ch4
        return p

    def state(self, when=BASE):
        return self.store.snapshot(when)["nodes"][0]["level"]

    def test_no_samples_never_looks_normal(self):
        self.assertEqual(self.state(), "SIN_DATOS")

    def test_warning_exact_boundary(self):
        self.store.ingest(self.reading(.5), BASE)
        self.assertEqual(self.state(), "PRECAUCION")

    def test_below_warning(self):
        self.store.ingest(self.reading(.4999), BASE)
        self.assertEqual(self.state(), "SIN_ALERTA")

    def test_alarm_at_front_boundary(self):
        self.store.ingest(self.reading(1.0), BASE)
        self.assertEqual(self.state(), "ALARMA")

    def test_location_specific_threshold(self):
        self.store.ingest(self.reading(1.0, "N03"), BASE)
        self.assertEqual(self.store.snapshot(BASE)["nodes"][2]["level"], "PRECAUCION")
        self.store.ingest(self.reading(1.5, "N03", "s2", BASE+1), BASE+1)
        self.assertEqual(self.store.snapshot(BASE+1)["nodes"][2]["level"], "ALARMA")

    def test_oxygen_boundaries(self):
        for i, (oxygen, expected) in enumerate([(19.49,"ALARMA"),(19.5,"SIN_ALERTA"),(23.5,"SIN_ALERTA"),(23.51,"ALARMA")]):
            p=self.reading(sid=f"o{i}",when=BASE+i);p["values"]["o2_vol_pct"]=oxygen
            self.store.ingest(p,BASE+i)
            self.assertEqual(self.state(BASE+i),expected)

    def test_thermal_demonstration_rules(self):
        for i,(temp,expected) in enumerate([(29.9,"SIN_ALERTA"),(30,"PRECAUCION"),(35,"ALARMA")]):
            p=self.reading(sid=f"t{i}",when=BASE+i);p["values"]["temperature_c"]=temp
            self.store.ingest(p,BASE+i);self.assertEqual(self.state(BASE+i),expected)

    def test_missing_measurement_is_incomplete(self):
        self.store.ingest(self.reading(None), BASE)
        self.assertEqual(self.state(), "INCOMPLETO")

    def test_alarm_not_hidden_by_missing_variable(self):
        p=self.reading(1.2);p["values"]["humidity_pct"]=None
        self.store.ingest(p,BASE);self.assertEqual(self.state(),"ALARMA")

    def test_sensor_fault(self):
        p=self.reading();p["device_status"]="fault"
        self.store.ingest(p,BASE);self.assertEqual(self.state(),"FALLO")

    def test_stale_at_exact_expiry(self):
        self.store.ingest(self.reading(),BASE)
        self.assertEqual(self.state(BASE+14.99),"SIN_ALERTA")
        self.assertEqual(self.state(BASE+15),"SIN_DATOS")
        self.store.sweep(BASE+15)
        self.assertTrue(any(e["level"]=="SIN_DATOS" and e["node_id"]=="N01" for e in self.store.events()))

    def test_recent_receipt_does_not_refresh_old_capture(self):
        self.store.ingest(self.reading(when=BASE-20),BASE)
        self.assertEqual(self.state(),"SIN_DATOS")

    def test_delayed_message_does_not_replace_latest(self):
        self.store.ingest(self.reading(1.2),BASE)
        result=self.store.ingest(self.reading(.2,sid="old",when=BASE-2),BASE+1)
        self.assertTrue(result["historical"])
        self.assertEqual(self.state(BASE+1),"ALARMA")

    def test_duplicate_is_idempotent(self):
        p=self.reading();self.store.ingest(p,BASE)
        self.assertTrue(self.store.ingest(p,BASE+1)["duplicate"])
        self.assertEqual(len(self.store.history()),1)

    def test_duplicate_with_changed_payload_conflicts(self):
        self.store.ingest(self.reading(),BASE)
        with self.assertRaises(InputError) as e:self.store.ingest(self.reading(2),BASE)
        self.assertEqual(e.exception.status,409)

    def test_concurrent_duplicate_is_atomic(self):
        p=self.reading()
        with ThreadPoolExecutor(max_workers=4) as ex:
            results=list(ex.map(lambda _:self.store.ingest(p,BASE),range(4)))
        self.assertEqual(sum(not r["duplicate"] for r in results),1)
        self.assertEqual(len(self.store.history()),1)

    def test_invalid_values_rejected(self):
        for v in [True,"1",float("nan"),float("inf"),-1,101]:
            with self.subTest(value=str(v)),self.assertRaises(InputError):self.store.ingest(self.reading(v),BASE)
        self.assertEqual(len(self.store.history()),0)

    def test_unknown_node_source_and_fields_rejected(self):
        cases=[]
        for k,v in [("node_id","N99"),("source","laboratory"),("unexpected",42)]:
            p=self.reading();p[k]=v;cases.append(p)
        for p in cases:
            with self.assertRaises(InputError):self.store.ingest(p,BASE)

    def test_invalid_timestamp_rejected(self):
        for when in ["2026-09-18T10:00:00",utc_iso(BASE+6),utc_iso(BASE-86401),"invalid"]:
            p=self.reading();p["captured_at"]=when
            with self.assertRaises(InputError):self.store.ingest(p,BASE)

    def test_laboratory_requires_calibration_reference(self):
        self.cfg["nodes"][0]["source"]="laboratory"
        p=self.reading();p["source"]="laboratory"
        with self.assertRaises(InputError):self.store.ingest(p,BASE)
        p["device_status"]="uncalibrated"
        self.store.ingest(p,BASE);self.assertEqual(self.state(),"FALLO")

    def test_acknowledgement_does_not_clear_alarm(self):
        self.store.ingest(self.reading(1.2),BASE)
        event=self.store.events()[0];self.store.acknowledge(event["id"])
        self.assertIsNotNone(self.store.events()[0]["acknowledged_ts"])
        self.assertEqual(self.state(),"ALARMA")

    def test_restart_preserves_data_and_acknowledgement(self):
        self.store.ingest(self.reading(1.2),BASE)
        self.store.acknowledge(self.store.events()[0]["id"])
        other=Store(self.store.path,self.cfg)
        self.assertEqual(len(other.history()),1)
        self.assertIsNotNone(other.events()[0]["acknowledged_ts"])

    def test_backup_integrity(self):
        self.store.ingest(self.reading(),BASE)
        target=Path(self.tmp.name)/"backup.sqlite3";self.store.backup(target)
        with sqlite3.connect(target) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM readings").fetchone()[0],1)

    def test_bad_configuration_rejected(self):
        cfg=copy.deepcopy(self.cfg);cfg["stale_after_seconds"]=1
        path=Path(self.tmp.name)/"bad.json";path.write_text(json.dumps(cfg))
        with self.assertRaises(ValueError):load_config(path)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.store=Store(Path(cls.tmp.name)/"http.sqlite3",load_config(ROOT/"config.json"))
        cls.keys={"operator":"test-operator-only-not-a-real-key", "ingest":"test-ingest-only-not-a-real-key"}
        cls.server=create_server(cls.store,cls.keys,port=0)
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()

    def request(self,path,key=None,data=None,method=None,raw=False):
        headers={}
        if key:headers["Authorization"]="Bearer "+key
        if data is not None:
            headers["Content-Type"]="application/json"
            data=data if raw else json.dumps(data).encode()
        req=Request(self.base+path,data,headers,method=method)
        try:
            with urlopen(req,timeout=5) as r:return r.status,r.headers,r.read()
        except HTTPError as e:return e.code,e.headers,e.read()

    def test_authentication_and_role_separation(self):
        self.assertEqual(self.request("/api/status")[0],401)
        self.assertEqual(self.request("/api/status",self.keys["ingest"])[0],401)
        self.assertEqual(self.request("/api/telemetry",self.keys["operator"],sample())[0],401)
        self.assertEqual(self.request("/api/status",self.keys["operator"])[0],200)

    def test_end_to_end_ingestion_and_export(self):
        self.assertEqual(self.request("/api/telemetry",self.keys["ingest"],sample())[0],201)
        code,headers,body=self.request("/api/export.csv?node_id=N01&limit=100",self.keys["operator"])
        self.assertEqual(code,200);self.assertIn("text/csv",headers["Content-Type"])
        self.assertIn("simulation",body.decode("utf-8-sig"))

    def test_bad_json_and_pagination(self):
        self.assertEqual(self.request("/api/telemetry",self.keys["ingest"],b'{"x": NaN}',raw=True)[0],400)
        self.assertEqual(self.request("/api/readings?limit=10001",self.keys["operator"])[0],400)
        self.assertEqual(self.request("/api/readings?node_id=N99",self.keys["operator"])[0],400)

    def test_private_files_not_served(self):
        for path in ["/config.json","/data/operator.key","/../core.py"]:
            self.assertNotEqual(self.request(path)[0],200)
        code,headers,_=self.request("/")
        self.assertEqual(code,200);self.assertIn("frame-ancestors 'none'",headers["Content-Security-Policy"])


if __name__=="__main__":unittest.main(verbosity=2)
