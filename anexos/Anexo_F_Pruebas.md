# Anexo F Registro de pruebas de software

Ejecución registrada en 2026-09-18, con Python 3.12.14. Resultado: 28 pruebas aprobadas, cero fallas y cero errores. Los casos usan bases temporales independientes de los datos del usuario.

| Caso | Comportamiento verificado | Resultado |
| --- | --- | --- |
| P01 | Autenticación y separación de claves | Aprobado |
| P02 | Rechazo de JSON y paginación inválidos | Aprobado |
| P03 | Ingreso HTTP y exportación CSV | Aprobado |
| P04 | Bloqueo de acceso a archivos privados | Aprobado |
| P05 | Reconocimiento conserva la alarma | Aprobado |
| P06 | Alarma exacta en el frente | Aprobado |
| P07 | Alarma prevalece ante dato ausente | Aprobado |
| P08 | Integridad de la copia de respaldo | Aprobado |
| P09 | Rechazo de configuración inconsistente | Aprobado |
| P10 | Valor debajo de la prealerta | Aprobado |
| P11 | Duplicación concurrente atómica | Aprobado |
| P12 | Lectura atrasada no reemplaza la vigente | Aprobado |
| P13 | Duplicado idéntico no se repite | Aprobado |
| P14 | Duplicado modificado produce conflicto | Aprobado |
| P15 | Fechas inválidas y sin zona rechazadas | Aprobado |
| P16 | Valores no numéricos y fuera de rango | Aprobado |
| P17 | Referencia de calibración en laboratorio | Aprobado |
| P18 | Umbral distinto según ubicación | Aprobado |
| P19 | Medición ausente produce incompletitud | Aprobado |
| P20 | Inicio sin muestras produce Sin datos | Aprobado |
| P21 | Fronteras inferior y superior de oxígeno | Aprobado |
| P22 | Captura antigua sigue vencida al recibirse | Aprobado |
| P23 | Persistencia después de reiniciar | Aprobado |
| P24 | Falla declarada por el dispositivo | Aprobado |
| P25 | Vencimiento exacto y registro del evento | Aprobado |
| P26 | Reglas térmicas de demostración | Aprobado |
| P27 | Origen nodo y campos desconocidos | Aprobado |
| P28 | Prealerta exacta de metano | Aprobado |

Evidencia reproducible: evidencias/pruebas_software.txt y evidencias/resultados.json. Los identificadores técnicos completos se conservan en esos archivos.

# Anexo F Ensayo HTTP y análisis de resultados

## F 1 Serie de clasificación

Se realizaron 30 envíos secuenciales al nodo N01. Se probaron seis concentraciones de metano cinco veces cada una, manteniendo las demás variables dentro de los rangos sin alerta. El estado esperado se fijó previamente y se comparó con la respuesta del servidor.

| CH₄ en % vol | Estado esperado | Repeticiones | Coincidencias |
| --- | --- | --- | --- |
| 0,2000 | Sin alerta | 5 | 5 |
| 0,4999 | Sin alerta | 5 | 5 |
| 0,5000 | Precaución | 5 | 5 |
| 0,9999 | Precaución | 5 | 5 |
| 1,0000 | Alarma | 5 | 5 |
| 1,0100 | Alarma | 5 | 5 |

Las 30 respuestas coincidieron con el estado previsto. Este resultado demuestra concordancia en el conjunto ejecutado; no corresponde a una exactitud metrológica de 100 % ni prueba que el sistema pueda detectar todas las situaciones de una mina.

## F 2 Tiempo de respuesta observado

| Medida | Resultado local |
| --- | --- |
| Mediana de ida y vuelta HTTP | 1,610 ms |
| Percentil 95 | 3,828 ms |
| Máximo | 5,747 ms |

Se utilizó perf_counter desde el inicio del envío hasta la lectura de la respuesta. El P95 se calculó mediante el rango más próximo sobre 30 observaciones. El servidor y el cliente operaron en el mismo equipo. Los tiempos varían entre equipos y no incluyen sensor, radio ni refresco del navegador.

## F 3 Verificaciones restantes

Antes de la sustentación, ejecutar el recorrido del anexo B y registrar capturas del panel sin claves visibles. Posteriormente, compilar el ejemplo ESP32, documentar el enlace Wi-Fi, integrar instrumentos reales y realizar las mediciones físicas. Las encuestas y observaciones de uso requieren participantes efectivos. Estos resultados deben anexarse con fecha y condiciones, sin sustituirlos por los datos de simulación.
