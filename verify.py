import csv
import io
import json
import platform
import statistics
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from core import Store, load_config, utc_iso
from server import create_server
from simulator import sample

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"evidencias"


class DetailedResult(unittest.TextTestResult):
    records=[]
    def startTest(self,test):
        super().startTest(test);self.started=time.perf_counter()
    def addSuccess(self,test):
        super().addSuccess(test)
        self.records.append({"test":test.id(),"result":"PASS","seconds":round(time.perf_counter()-self.started,6)})
    def addFailure(self,test,err):
        super().addFailure(test,err);self.records.append({"test":test.id(),"result":"FAIL"})
    def addError(self,test,err):
        super().addError(test,err);self.records.append({"test":test.id(),"result":"ERROR"})


def main():
    OUT.mkdir(exist_ok=True)
    suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"))
    log=io.StringIO()
    result=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=DetailedResult).run(suite)
    (OUT/"pruebas_software.txt").write_text(log.getvalue(),encoding="utf-8")
    report={"executed_at_utc":utc_iso(),"python":platform.python_version(),"platform":platform.platform(),
            "tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"tests":result.records,
            "scope":"Pruebas de software con muestras sintéticas. No validan precisión de sensores, radio, mina ni aceptación de usuarios."}
    with tempfile.TemporaryDirectory() as tmp:
        store=Store(Path(tmp)/"experiment.sqlite3",load_config(ROOT/"config.json"))
        keys={"operator":"experiment-local-operator-not-secret","ingest":"experiment-local-ingest-not-secret"}
        server=create_server(store,keys,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        rows=[]
        try:
            for i in range(30):
                value,expected=[(.2,"SIN_ALERTA"),(.4999,"SIN_ALERTA"),(.5,"PRECAUCION"),(.9999,"PRECAUCION"),(1.,"ALARMA"),(1.01,"ALARMA")][i%6]
                data=sample("N01",i,scenario="normal");data["values"]["ch4_vol_pct"]=value
                request=Request(f"http://127.0.0.1:{server.server_port}/api/telemetry",json.dumps(data).encode(),
                    {"Content-Type":"application/json","Authorization":"Bearer "+keys["ingest"]})
                start=time.perf_counter()
                with urlopen(request,timeout=5) as response:body=json.loads(response.read())
                elapsed=(time.perf_counter()-start)*1000
                rows.append({"sample":i+1,"node_id":"N01","source":"simulation","ch4_vol_pct":value,"expected":expected,"observed":body["level"],"match":expected==body["level"],"http_round_trip_ms":round(elapsed,3)})
        finally:
            server.shutdown();server.server_close();thread.join()
        timings=sorted(r["http_round_trip_ms"] for r in rows)
        report["experiment"]={"samples":len(rows),"matching_states":sum(r["match"] for r in rows),
            "median_http_ms":statistics.median(timings),"p95_http_ms":timings[28],"max_http_ms":max(timings),
            "method":"30 solicitudes POST secuenciales en loopback; perf_counter desde envío hasta lectura de respuesta; P95 por rango más próximo. Sin sensor ni interfaz gráfica."}
        with (OUT/"ensayo_http_sintetico.csv").open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (OUT/"resultados.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(log.getvalue());print(json.dumps({k:v for k,v in report.items() if k!="tests"},ensure_ascii=False,indent=2))
    raise SystemExit(0 if result.wasSuccessful() and all(r["match"] for r in rows) else 1)


if __name__=="__main__":main()
