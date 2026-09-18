# Anexo C Matriz de requisitos y trazabilidad

La cobertura se refiere a esta versión académica. Un objetivo que incluye instrumentación física no se considera completado únicamente por disponer del software.

| ID | Requisito verificable | Evidencia o estado |
| --- | --- | --- |
| RF01 | Recibir mensajes de nodos registrados. | API y prueba de ingreso HTTP. |
| RF02 | Validar unidad, rango, fecha y calidad declarada. | Casos de campos y valores inválidos. |
| RF03 | Clasificar metano por ubicación del nodo. | Pruebas de N01 y N03 en la frontera. |
| RF04 | Mostrar O₂, temperatura y humedad. | Campos y controles del panel; revisión manual pendiente. |
| RF05 | Identificar datos ausentes, vencidos y en falla. | Pruebas de incompletitud, fallo y antigüedad. |
| RF06 | Conservar lecturas y transiciones. | Persistencia, duplicados y reinicio. |
| RF07 | Reconocer un evento sin eliminar la alarma. | Prueba de reconocimiento. |
| RF08 | Consultar y exportar lecturas. | API, paginación y CSV. |
| RN01 | Separar consulta e ingreso de telemetría. | Prueba de claves y roles. |
| RN02 | Evitar duplicados concurrentes. | Prueba con cuatro ingresos simultáneos. |
| RN03 | Preservar versión de reglas y respaldo. | Hash de configuración y prueba de integridad. |
| RN04 | Distinguir simulación de laboratorio. | Validación del origen configurado. |

| Objetivo | Cobertura de la entrega | Pendiente |
| --- | --- | --- |
| 1 Umbrales | Matriz de gases y parámetros documentados. | Revisión técnica del contexto real y otros contaminantes. |
| 2 Arquitectura | Diseño lógico y contrato implementados. | Ubicación física y caracterización de radio. |
| 3 Prototipo | Software ejecutable; ejemplo ESP32. | Driver e integración de sensores seleccionados. |
| 4 Validación | Software y serie HTTP sintética. | Metrología, hardware y aceptación de usuarios. |
