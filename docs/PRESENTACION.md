# Presentación: 3 minutos con el software en vivo

**Abrir antes de empezar** (dos pestañas):

1. https://alexnoblejas.github.io/pulso-territorial/?company=mineria
2. https://alexnoblejas.github.io/pulso-territorial/?company=hidrocarburos

Si cae internet: `.\iniciar.ps1` y http://127.0.0.1:8765 (todo funciona sin red, salvo el relieve del mapa), o el video de respaldo.

## Guion

| Tiempo | Qué se ve en pantalla | Qué decir | Sesión del curso |
|---|---|---|---|
| 0:00–0:30 | Resumen de la cartera minera | "Un equipo de relaciones comunitarias de una minera tiene que reconstruir cada mes qué dicen la Defensoría, la PCM, el MINAM, el OEFA y la prensa sobre sus comunidades. Son PDF, HTML y notas sueltas, con fechas que no coinciden. PulsoTerritorial lo junta en un solo lugar y cada frase lleva a su fuente." | — |
| 0:30–1:00 | **Territorio → 3D**, activar *Comunidades* y *Red vial* | "Este es el territorio real de Las Bambas: relieve, distritos, comunidades y vías procesados con GeoPandas. Cada punto es un conflicto del reporte de la Defensoría, que el sistema descarga y lee solo." | 06 GeoPandas · 03 Scraping |
| 1:00–1:35 | **Conflictos → Fuerabamba**, bajar a la línea de tiempo, clic en **"Ver pasaje · p. 38 del PDF"** | "El expediente cruza la ficha de la Defensoría con la PCM y un antecedente de MINEM de 2016. Este enlace abre el informe oficial en la página exacta. Python comprueba con pypdf que la cita está literal en esa página y que el PDF no cambió; si alguien altera una cifra, la cita desaparece." | 10 Document AI · 03 |
| 1:35–2:05 | Cambiar a **hidrocarburos → Sinchi Roca → Interpretar esta selección** | "La IA, Groq con gpt-oss, lee la ficha y los pasajes y devuelve JSON con un esquema estricto. Toda afirmación sin cita literal se descarta: aquí aceptó 3 y descartó 2. Y encontró algo útil: la Defensoría fecha el derrame el 19 de febrero y el MINAM el 19 de marzo." | 08 LLMs con salidas estructuradas |
| 2:05–2:30 | **Resumen → Pulso de medios** y luego **Reporte mensual** | "Entre reportes oficiales, el sistema lee cada día los RSS de El Comercio, La República, Andina y Google News, con el scraper de mi tarea 1. Por ejemplo, la PNP interviniendo robos de crudo en el Oleoducto esta semana. Todo se regenera solo cada mañana con GitHub Actions y produce este reporte mensual." | 03 Scraping · 05 Dashboards · 12 Despliegue |
| 2:30–3:00 | Mantener el reporte en pantalla | "Quién paga: el área de relaciones comunitarias de una minera o una petrolera, o su consultora. Piloto a S/ 299 al mes por cartera. La IA cuesta menos de un dólar al mes por cartera y el hosting es gratis. Lo que sigue: entrevistar a equipos de gestión social, sumar más fuentes como OEFA en línea y PNP, y enviar el reporte por correo." | — |

## Si el profesor pregunta por las herramientas del curso

| Herramienta del curso | Dónde está en el producto | Archivo |
|---|---|---|
| 03 Scraping y APIs | Reportes de la Defensoría (HTML) y RSS de 4 medios más Google News | `pulso/service.py`, `pulso/news.py` |
| 05 Dashboards | Portal con KPIs, fases, pulso de medios y reporte mensual | `web/app.js`, `pulso/reports.py` |
| 06 GeoPandas | Capas EPSG:4326 por cartera y mapa 3D con MapLibre | `demo_data/geography_*.json` |
| 08 LLMs con salidas estructuradas | Groq con esquema JSON estricto y validador de citas | `pulso/service.py` |
| 10 Document AI | pypdf: extracción y verificación de pasajes en PDF oficiales | `pulso/corpus.py` |
| 12 Despliegue | GitHub Pages con regeneración diaria en Actions | `pulso/export.py`, `.github/workflows/pages.yml` |

Las **dos herramientas principales** que pide la consigna son **08** (salidas estructuradas) y **10** (Document AI). El scraping (03) es lo que hace el producto automático.

## Partes del código para explicar si lo piden

- **Verificación de una cita:** función `load()` en `pulso/corpus.py`. Compara el hash del PDF y busca el texto sin espacios en la página, porque pypdf a veces parte palabras.
- **Rechazo de lo que inventa la IA:** función `validate_records()` en `pulso/service.py`.
- **Notas de prensa:** funciones `parse()` y `classify()` en `pulso/news.py`. Solo se leen RSS y se guarda el titular, el medio, la fecha y el enlace.

## Lo que no hay que afirmar

- Que hubo entrevistas o clientes: no los hubo.
- Que una nota de prensa prueba un hecho: es una señal y se contrasta con la ficha oficial.
- Que la cercanía en el mapa prueba afectación.
