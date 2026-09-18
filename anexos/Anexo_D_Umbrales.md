# Anexo D Matriz de umbrales y unidades

Los límites de gases se relacionan con la ubicación y la unidad indicada en la fuente. La configuración constituye una aplicación parcial para laboratorio y no acredita cumplimiento integral del reglamento.

| Variable o parámetro | Regla de esta versión | Naturaleza |
| --- | --- | --- |
| CH₄ en N01 frente | Alarma desde 1,0 % vol. | Referencia: Decreto 1886 de 2015, art. 53. |
| CH₄ en N02 retorno principal | Alarma desde 1,0 % vol. | Misma referencia y ubicación correspondiente. |
| CH₄ en N03 retorno del tajo | Alarma desde 1,5 % vol. | Misma referencia; no es un límite universal. |
| Prealerta de CH₄ | Desde 0,5 % vol, antes de la alarma. | Elección de diseño para demostrar estados. |
| Oxígeno | Alarma por debajo de 19,5 o por encima de 23,5 % vol. | Referencia: Decreto 1886 de 2015, art. 38. |
| Temperatura ambiente | Prealerta desde 30 °C; alarma desde 35 °C. | Ejemplos de diseño; no representan una evaluación normativa de calor. |
| Humedad relativa | Registrar de 0 a 100 % HR; sin alarma. | Observación descriptiva. |
| Vigencia | Sin datos al cumplir 15 s. | Parámetro de software; no frecuencia normativa de monitoreo. |

## Referencias que condicionan el paso a hardware

El Decreto 944 de 2022 modifica exigencias sobre equipos, monitoreo y seguridad eléctrica del Decreto 1886. Sus artículos 9, 10 y 21 son relevantes para la selección de instrumentos, el seguimiento permanente y la aptitud de equipos en áreas clasificadas. La comparación con esas exigencias debe realizarse antes de un uso operacional.

## Reglas de interpretación

Porcentaje de volumen y porcentaje del límite inferior de explosividad son escalas diferentes. El programa recibe porcentaje de volumen de manera explícita; cualquier conversión debe ocurrir en un adaptador verificado. No interpreta un voltaje ni una lectura ADC como una concentración.

Las concentraciones de otros gases pueden requerir promedios de exposición y condiciones adicionales. Esta versión no calcula TWA o STEL. La temperatura y la humedad por sí solas tampoco caracterizan el estrés térmico. Estas limitaciones deben mantenerse visibles al explicar el alcance del prototipo.
