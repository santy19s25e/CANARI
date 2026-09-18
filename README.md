# CANARI

Prototipo académico ejecutable de monitoreo ambiental. Incluye servidor Python,
base de datos SQLite, panel web, reglas de alertas por nodo, historial, exportación
CSV, simulador y pruebas reproducibles. No requiere instalar paquetes de pip.

## Inicio en Windows

1. Instala Python 3.10 o posterior si aún no lo tienes. La ejecución adjunta se hizo con Python 3.12.14.
2. Extrae completamente el ZIP. No ejecutes los archivos desde la vista comprimida.
3. Abre `INICIAR_WINDOWS.bat`. También puedes abrir una terminal dentro de `canari` y ejecutar:

```bat
py -3 server.py --demo
```

4. Abre `http://127.0.0.1:8000` en un navegador moderno.
5. Copia la **clave de operador** que aparece en la consola, pégala en el panel y pulsa **Conectar**.
6. Verás tres nodos con registros identificados como simulados. Los escenarios cambian cada cinco muestras.
7. Para cerrar, vuelve a la terminal y presiona `Ctrl+C`.

En macOS o Linux usa `python3 server.py --demo`. Si Windows no reconoce `py`,
prueba `python server.py --demo` después de instalar Python y volver a abrir la terminal.

## Qué está implementado

- CH4 en % de volumen, O2 en % de volumen, temperatura en °C y humedad en % HR.
- Alarmas por CH4 específicas del nodo, O2 fuera de rango y temperatura de demostración.
- Prealerta, dato faltante, falla del sensor y muestra vencida.
- Clave de operador separada de la clave de ingreso de telemetría.
- Historial persistente, reconocimiento de eventos y exportación de hasta 10 000 filas por solicitud.
- Prevención de duplicados y tratamiento de muestras que llegan fuera de orden.
- Copia de respaldo coherente de SQLite y registro de la configuración aplicada.
- Simulación sin hardware y ejemplo ESP32 de telemetría Wi-Fi simulada.

## Alcance de la validación

`evidencias/resultados.json` contiene el entorno y resultados de una ejecución real:
28 pruebas automatizadas y 30 envíos HTTP sintéticos. `pruebas_software.txt` conserva
la salida de las pruebas y `ensayo_http_sintetico.csv` las 30 observaciones.
Los tiempos corresponden a solicitudes locales HTTP, no al tiempo físico de detección
de gas ni al refresco completo del navegador. No hay resultados de mina, sensores,
radio, certificación ni encuestas a usuarios. El firmware se entrega como ejemplo
sin compilación ni prueba en una placa física. La interfaz requiere comprobación
manual en el equipo de presentación.

Para repetir:

```bat
py -3 verify.py
```

La ejecución reemplaza los tres archivos de evidencia con sus nuevos resultados.

## Uso sin el simulador automático

Primera terminal:

```bat
py -3 server.py
```

Segunda terminal, en la misma carpeta:

```bat
py -3 simulator.py --node N01 --scenario alarm --count 10
```

Escenarios: `normal`, `warning`, `alarm`, `oxygen`, `missing` y `cycle`.
`--count` es el número de muestras; `--interval` son segundos entre muestras.
Detén los envíos y espera 15 segundos: el nodo debe indicar **Sin datos**. El
refresco del panel puede tardar hasta 3 segundos adicionales en mostrar el cambio.

## Umbrales y unidades

Modifica `config.json` con el servidor detenido y vuelve a iniciarlo.

| Parámetro | Valor inicial | Interpretación |
|---|---:|---|
| CH4 en N01 y N02 | 1.0 % vol | Alarma a partir del umbral del lugar configurado |
| CH4 en N03 | 1.5 % vol | Retorno de tajo |
| Prealerta de CH4 | 0.5 % vol | Elección de diseño del prototipo |
| O2 | 19.5–23.5 % vol | Alarma fuera del intervalo |
| Temperatura | 30 / 35 °C | Ejemplos de prealerta y alarma, no límites normativos |
| Humedad | Sin alarma | Variable descriptiva |
| Antigüedad máxima | 15 s | Muestra vencida a partir de ese tiempo |

Referencia de gases: Decreto 1886 de 2015, artículos 38 y 53:
https://www.alcaldiabogota.gov.co/sisjur/normas/Norma1.jsp?i=63072

El monitoreo parcial no acredita calidad integral del aire. No se miden CO, CO2,
H2S, polvo ni velocidad del aire; no se calculan exposiciones TWA/STEL ni estrés
térmico. Las unidades % vol y % LEL no son intercambiables.

## Estructura y API

| Archivo | Función |
|---|---|
| `server.py` | HTTP, autorización, rutas y supervisión de antigüedad |
| `core.py` | Validación, reglas, transacciones y consultas |
| `config.json` | Nodos, ubicaciones, origen y parámetros |
| `simulator.py` | Escenarios didácticos y emisor HTTP |
| `web/` | HTML, CSS y JavaScript del panel |
| `tests/test_canari.py` | Pruebas unitarias y de integración |
| `verify.py` | Ejecución y reporte de evidencia |
| `backup.py` | Copia coherente de la base de datos |
| `firmware/esp32_demo/` | Ejemplo ESP32 sin sensores físicos |
| `anexos/` | Instrumentos para validación posterior |
| `data/` | Datos y claves creados al iniciar, excluidos de esta entrega |

Todas las rutas `/api/` requieren `Authorization: Bearer CLAVE`.

| Método y ruta | Clave | Resultado |
|---|---|---|
| `GET /health` | No requiere | Disponibilidad del proceso, no salud de sensores |
| `GET /api/status` | Operador | Estado actual y configuración |
| `GET /api/readings` | Operador | Historial; filtros `node_id`, `limit`, `before_id`, `since` |
| `GET /api/events` | Operador | Últimos 100 eventos |
| `POST /api/events/ID/ack` | Operador | Marca de lectura sin suprimir la alarma |
| `GET /api/export.csv` | Operador | CSV; mismos filtros, máximo 10 000 registros |
| `POST /api/telemetry` | Ingreso | Inserta una muestra validada |

En `since`, usa ISO 8601 con zona y codifica el signo `+` como `%2B` si aparece en la URL.
El historial está ordenado por ID de recepción descendente. Para consultar todo,
usa `next_before_id` como `before_id` en la siguiente página hasta que sea null.
La lectura actual se elige por fecha de captura; una lectura antigua no reemplaza
una más reciente. Un `sample_id` repetido debe conservar exactamente el mismo contenido.

Ejemplo de mensaje (la fecha debe reemplazarse por UTC actual):

```json
{
  "node_id": "N01",
  "sample_id": "sesionA_001",
  "captured_at": "2026-09-18T04:00:00Z",
  "source": "simulation",
  "device_status": "ok",
  "calibration_ref": "",
  "values": {
    "ch4_vol_pct": 0.2,
    "o2_vol_pct": 20.9,
    "temperature_c": 24.0,
    "humidity_pct": 65.0
  }
}
```

`device_status`: `ok`, `fault`, `uncalibrated`. Use JSON `null` para valores ausentes,
nunca cero como sustituto. Un nodo configurado con `source: laboratory` exige el mismo
origen en la muestra y una referencia de calibración para estado `ok`. La referencia
es declarativa: el programa no autentica un certificado de calibración.

Errores: 400 datos inválidos, 401 clave incorrecta, 404 recurso inexistente,
409 muestra duplicada con contenido distinto, 413 cuerpo fuera del tamaño permitido,
415 tipo de contenido incorrecto. Los valores booleanos, NaN e infinitos no se admiten.

## Modelo de datos

`readings` guarda valores, captura, recepción, origen, calidad declarada y versión
de reglas. `events` conserva transiciones y reconocimientos; puede referenciar
una lectura o representar ausencia de datos. `node_state` guarda el último estado
para evitar repetir el mismo evento. `configurations` conserva cada configuración
identificada por SHA-256. No se borran registros de forma automática.

## Respaldo y restauración

```bat
py -3 backup.py
```

Se crea un archivo en `backups/`. Para restaurar, detén el servidor, conserva una
copia de toda la carpeta `data` y crea una carpeta nueva para la restauración.
Copia el respaldo allí con el nombre `canari.sqlite3` y arranca con
`py -3 server.py --data-dir carpeta_restaurada`. Se crearán nuevas claves si esa carpeta
no las tiene. Usa la configuración correspondiente a esa sesión. No copies únicamente
el archivo principal de una base activa, porque puede tener cambios en su archivo WAL.

## Ejemplo ESP32

1. Usa una placa ESP32 en mesa de laboratorio y Arduino IDE con el core ESP32 instalado.
2. Abre `firmware/esp32_demo/esp32_demo.ino`.
3. Configura red, contraseña, URL del computador y contenido de `data/ingest.key`.
4. Inicia el servidor **sin** `--demo`, ligado a la IP privada del equipo, por ejemplo:
   `py -3 server.py --host 192.168.1.10` (reemplaza esa IP por la de tu equipo).
5. Usa una red de laboratorio aislada. El equipo y la placa deben poder comunicarse;
   la placa necesita NTP para sincronizar su fecha. No se deben abrir puertos a Internet.
6. Compila para la placa correcta, carga el ejemplo y revisa el monitor serial a 115200 baudios.
7. El ejemplo envía N03 con `source: simulation`. No usa sensores MQ ni convierte ADC a ppm.

Para conectar un instrumento físico se necesita un driver acorde con su interfaz y
ficha técnica, confirmar sus unidades, calibración y lectura de fallas, y configurar
un nodo `laboratory`. Esto requiere conocer el modelo real del instrumento.

## Límites de esta versión

Es una demostración de software en laboratorio. El servidor estándar de Python no
está diseñado como servicio de producción; usa HTTP sin TLS, claves locales y un
solo rol de operador, no cuentas individuales. No hay LoRa, SMS, control de ventiladores,
evacuación automática, GPS, chatbot, conexión con el frontend anterior ni instalador .exe.
El ESP32 común y este programa no acreditan certificación para atmósferas explosivas.
No realizar pruebas caseras liberando gases inflamables o tóxicos. La evaluación física
debe quedar a cargo de un laboratorio competente, con equipo apropiado.

## Fuentes técnicas

- Decreto 1886 de 2015: https://www.alcaldiabogota.gov.co/sisjur/normas/Norma1.jsp?i=63072
- Decreto 944 de 2022: https://www.alcaldiabogota.gov.co/sisjur/normas/Norma1.jsp?i=124217
- CDIO: https://www.cdio.org/implementing-cdio/standards/12-cdio-standards
- Python HTTP: https://docs.python.org/3/library/http.server.html
- Python SQLite: https://docs.python.org/3/library/sqlite3.html
- ESP32 Wi-Fi: https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html
