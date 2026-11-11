# Presentación: 3 minutos con el software en vivo

**Abrir antes de empezar** (tres pestañas):

1. https://alexnoblejas.github.io/pulso-territorial/?company=mineria
2. https://alexnoblejas.github.io/pulso-territorial/?company=hidrocarburos
3. https://github.com/AlexNoblejas/pulso-territorial/actions, como prueba de que corre solo cada día

Si cae internet: `.\iniciar.ps1` y http://127.0.0.1:8765 (todo funciona sin red, salvo el relieve del mapa), o el video de respaldo.

## Guion

| Tiempo | Qué se ve en pantalla | Qué decir | Sesión del curso |
|---|---|---|---|
| 0:00–0:25 | Resumen de minería, con las alertas arriba | "Una minera como Las Bambas tiene conflictos en varias comunidades. La Defensoría, la PCM, el MINEM, el OEFA, la policía y la prensa hablan de ellos, cada uno desde su función y en su formato. Si su equipo no ve a tiempo un plazo vencido o un paro, la operación se detiene. PulsoTerritorial lee todo eso solo, cada día, y le dice qué gestionar." | — |
| 0:00–0:25 (en paralelo) | Ingresar como *Antamina*, tu nombre y contraseña `2026`; Lore saluda | (mientras hablas del problema, la pantalla muestra el ingreso de un analista real) | — |
| 0:25–0:50 | **Alertas** | "Hoy hay cuatro alertas. Por ejemplo, la reunión en Mara del 20 de noviembre y un compromiso con Chuicuni del 16 de octubre del que ninguna fuente volvió a informar. Cada alerta dice qué regla la activó y abre su evidencia. No es una predicción: son reglas que se pueden auditar." | 05 Dashboards |
| 0:50–1:30 | **Conflictos → Fuerabamba → Línea de tiempo por actor**: clic en un punto de setiembre y luego en uno del Ejecutivo | "Esta es la historia del conflicto por actor: Defensoría, Ejecutivo, fiscalizadores, policía, empresa y prensa. Hago clic en un mes y veo qué dijo cada uno, con el encuadre de esa fuente. Los pasajes salen solos de los PDF de la Defensoría, de los informes del MINAM y de la revista de la PCM, con su página: lo hace pypdf." | 03 Scraping · 10 Document AI |
| 1:30–1:55 | Bajar a **Contexto territorial** y luego **Territorio**: activar *Concesiones de Minera Las Bambas* y *Comunidades campesinas (MIDAGRI)* en 3D | "El territorio sale en vivo de GEOPERÚ, el mismo geoservidor de mi MCP de la tarea 4. Muestra las 42 concesiones de la empresa, las comunidades tituladas y los pasivos ambientales. Huancuire se superpone con la concesión BAMBAS 17. Y cuando la ubicación es solo distrital, el sistema lo dice en vez de inventar una comunidad." | 04 MCP · 06 GeoPandas |
| 1:55–2:20 | **Hidrocarburos → Sinchi Roca → Interpretar esta selección** | "La IA, Groq con salida JSON estricta, lee el caso. Toda afirmación sin cita literal se descarta. Así detecta que la Defensoría fecha el derrame el 19 de febrero y el MINAM el 19 de marzo: un error de comunicación que conviene aclarar antes de reunirse con la comunidad." | 08 Salidas estructuradas |
| (si sobra tiempo) | **Conflictos del país** y preguntarle a **Lore** «¿Con quién gestiono Llata?» | "Además ve todo el país, los departamentos de la operación y quince años de historia; y Lore responde con los datos, citando la fuente." | 05 · 03 |
| 2:20–2:35 | **Estado del sistema** y luego la pestaña de GitHub Actions | "Para que vean que funciona solo: cada mañana a las 7:00, GitHub Actions corre las ocho etapas y vuelve a publicar el sitio. Aquí está la bitácora de cada fuente con su resultado." | 12 Despliegue |
| 2:35–3:00 | Volver al resumen | "Quién paga: el área de relaciones comunitarias de la minera o la petrolera, o su consultora. Piloto a S/ 299 al mes por cartera. La IA cuesta menos de un dólar al mes y el hosting es gratis. Lo que sigue: probarlo con equipos de gestión social y enviar las alertas por correo." | — |

## Si el profesor pregunta por las herramientas del curso

| Herramienta del curso | Dónde está | Archivo |
|---|---|---|
| 03 Scraping y APIs | Defensoría, buscador de gob.pe (PCM, MINEM, MINAM, OEFA, ANA, PNP), SINIA, PCM y RSS de prensa (tarea 1) | `pulso/service.py`, `pulso/sources.py`, `pulso/news.py` |
| 10 Document AI | Pasajes con página extraídos de PDF oficiales y verificación del corpus | `pulso/sources.py`, `pulso/corpus.py` |
| 08 Salidas estructuradas | Groq con esquema JSON y validador de citas | `pulso/service.py` |
| 04 MCP / 06 GeoPandas | GEOPERÚ por ArcGIS REST (tarea 4) y contexto territorial con shapely | `pulso/geoperu.py` |
| 05 Dashboards | Alertas, línea de tiempo por actor, pulso de medios y reporte mensual | `web/app.js`, `pulso/reports.py` |
| 12 Despliegue | Ciclo diario en Actions, Pages y bitácora | `pulso/pipeline.py`, `.github/workflows/pages.yml` |

## Partes del código para explicar si lo piden

- **Reglas de alerta:** función `compute()` en `pulso/alerts.py`. Cada regla está escrita en el diccionario `RULES`.
- **Homónimos:** `ANCHORS` y `classify()` en `pulso/news.py`. Sinchi Roca también es una comunidad de Huánuco y un parque de Comas.
- **Pasajes de PDF:** función `_pdf_passages()` en `pulso/sources.py`.
- **Contexto territorial:** función `context()` en `pulso/geoperu.py`. Usa el polígono comunal si existe y, si no, avisa que el punto es distrital.
- **Rechazo de lo que inventa la IA:** función `validate_records()` en `pulso/service.py`.

## Lo que no hay que afirmar

- Que hubo entrevistas o clientes.
- Que una nota de prensa o una cercanía en el mapa prueban un hecho o una afectación.
- Que las alertas predicen conflictos: son reglas sobre lo ya reportado.
- Que hay un parte policial directo: la PNP entra por sus notas en gob.pe y por la prensa.
