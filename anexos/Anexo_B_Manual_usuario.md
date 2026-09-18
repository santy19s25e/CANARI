# Anexo B Manual de usuario

## B 1 Acceso y consulta

Abra INICIAR_WINDOWS.bat y mantenga la consola abierta. Ingrese a http://127.0.0.1:8000, copie la clave de operador que muestra el programa, péguela en el campo correspondiente y pulse Conectar. Aparecerán las tarjetas de los nodos y el indicador de conexión al servidor.

Cada tarjeta muestra el identificador del punto, el origen de los datos, el metano, el oxígeno, la temperatura, la humedad y la antigüedad de la muestra. La etiqueta SIMULADO identifica una demostración; no corresponde a una lectura tomada en una mina. Una conexión activa con el servidor no garantiza que todos los nodos estén transmitiendo.

## B 2 Interpretación de estados

| Estado | Significado y actuación en la demostración |
| --- | --- |
| Sin alerta | No se superaron las reglas configuradas. Revisar origen y vigencia; no significa atmósfera segura. |
| Precaución | Se alcanzó una prealerta. Consultar variable, nodo y tendencia. |
| Alarma | Se activó una regla de gas o temperatura. Revisar el evento y su causa. |
| Incompleto | Falta alguna variable. Identificar el campo sin medición. |
| Fallo | El emisor declaró falla o falta de calibración. |
| Sin datos | No existen muestras vigentes. Revisar emisor, red y fecha. |

## B 3 Tendencias y eventos

Seleccione el nodo y la variable en Tendencia por nodo. El gráfico usa las últimas 100 muestras recibidas de ese nodo y las ordena por captura. Los datos ausentes o en falla interrumpen la línea. La tabla inferior muestra hasta 25 lecturas de la consulta.

En Registro de eventos se conservan los últimos 100 cambios consultados. Pulse Reconocer cuando haya leído un evento. La marca permanece en el registro y no apaga una alarma activa. Activar sonido habilita una señal breve ante nuevos eventos relevantes; requiere que el navegador permita audio y mantenga la página abierta.

# Anexo B Demostración y solución de problemas

## B 4 Recorrido de demostración

1. Inicie el modo --demo y conecte el panel. Observe que los escenarios cambian cada cinco muestras. Compruebe que cada tarjeta conserva su identificación y muestra el origen simulado.

2. Elija N01 para consultar metano y reconozca un evento de alarma. Verifique que la tarjeta continúa en alarma mientras la condición persiste. Exporte el CSV y compruebe que contiene nodo, fechas, valores, origen y estado.

3. Para demostrar la pérdida de comunicación, detenga el programa y reinícielo sin --demo. En otra terminal ejecute:

```
py -3 simulator.py --node N01 --scenario normal --count 3
```

Una vez terminen los tres envíos, espere al menos 15 segundos. N01 pasará a Sin datos en la siguiente actualización. El panel puede tardar hasta tres segundos adicionales en reflejarlo. Vuelva a enviar muestras para observar la recuperación.

## B 5 Exportación y cierre

Exportar CSV descarga hasta las últimas 10 000 lecturas del nodo seleccionado. Para conjuntos mayores, el programador debe usar la paginación de la API. Los archivos se abren en una hoja de cálculo; los valores ausentes se conservan vacíos. Pulse Salir para retirar la clave de la sesión del navegador. Cierre el servidor con Ctrl+C; los registros permanecen guardados.

| Problema | Qué revisar |
| --- | --- |
| No abre la dirección local | Mantener la consola abierta y comprobar el puerto 8000. |
| El comando py no existe | Comprobar Python e intentar python server.py --demo. |
| Clave inválida | Copiar la clave de operador, sin confundirla con ingest.key. |
| Nodo sin datos | Revisar si existe un emisor, su ID, la red y la fecha de captura. |
| Puerto ocupado | Iniciar con --port 8001 y abrir la misma dirección con ese puerto. |
| No se escucha sonido | Pulsar Activar sonido; revisar volumen y permisos del navegador. |
| ESP32 obtiene HTTP 400 | Revisar formato, origen y sincronización de fecha; leer el contrato del anexo A. |
