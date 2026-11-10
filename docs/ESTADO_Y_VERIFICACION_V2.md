> **Documento histórico** (primera versión, mediodía del 10 de noviembre de 2026). El estado vigente está en el [README](../README.md) y el guion en [PRESENTACION.md](PRESENTACION.md).

# Estado guardado de PulsoTerritorial V2

Autor: Alexander Noblejas. Construido el 10 de noviembre de 2026, America/Lima.

## Experiencia implementada

- Plataforma web empresarial en Python y frontend propio, con dos perfiles demo, sidebar y cinco vistas: resumen, territorio, conflictos, fuentes y reportes.
- Minería / Las Bambas: cuatro casos estructurados del RCS271. Petroperú: dos casos con mención empresarial expresa, ONP/Pijuayal y empresas comunales/Altamesa-Lote192. Un actor mencionado no prueba que opere hoy el activo.
- Fases oficiales, diálogo separado y lectura ejecutiva editorial con citas vinculadas. Agenda de seis compromisos reportados en minería; se distingue programación de cumplimiento verificado.
- MapLibre con relieve Mapterhorn/Copernicus y base OpenFreeMap/OSM. Capas locales normalizadas a EPSG4326: distritos, comunidades, yacimientos, pozos y red vial2018. Puntos distritales/comunales referenciales, sin distancias de afectación inventadas. Dos casos comparten coordenada y se agrupan.
- Siete publicaciones vinculadas a la cartera hidrocarburos: Defensoría, dos OEFA, MINAM/OGASA, ANA, Vivienda y prensa. Se muestran discrepancias de fecha y alcances distintos de actuaciones y reclamos.
- Tres notas MINEM se muestran como contexto adicional de otras comunidades, sin fusionarlas con los cuatro expedientes de Defensoría. No hay parte PNP directo incorporado ni un conector GeoPerú productivo; se identifican esas fuentes y la procedencia local de las capas.
- Base histórica encontrada:33845 observaciones y1073IDs de investigación,340provisionales. Se seleccionaron7casos/655observaciones con procedencia. La interfaz usa3antecedentes mineros/288observaciones y2antecedentes Petroperú/216observaciones; no atribuye Lotes8/192 de otros operadores actuales a Petroperú por proximidad. Se cotejaron dos pasajes PDF, no todo el archivo.
- Reportes HTML portables con tres visuales SVG: mapa referencial, fases y tendencia; imprimir/guardar PDF desde navegador. El envío de correo no está activado.
- Modo periódico de captura y generación de reportes preparado con iniciar.ps1 -Automatizar (cada24horas, laptop encendida y proceso activo). No se instaló una tarea Windows ni se observó aún una espera de24horas. Las comunicaciones complementarias son curadas y no se anuncian como feeds diarios completos.

## Comprobaciones

36 pruebas Python aprobadas (26 del núcleo/contratos OCR y10 del modelo/API de cartera), más verificaciones JS contra las dos carteras reales. Cubren versiones, negación de diálogo, fuenteperiodo, tipo de fuente, privacidad de rutas, Host/Origin, JSON inválido, preservación de cero/null, filtros y agrupación de coordenadas sin desplazamientos.

Se comprobó en navegador el ingreso en ambas carteras, mapa3D real, capas de carreteras/comunidades, expediente Pijuayal y fuentes. Se verificaron los endpoints de cartera, geografía y reporte; cada reporte genera tresSVG. Las síntesis y comparaciones editoriales se invalidan si cambia el SHA de su fuente. No se probaron llamadas autenticadas a IA ni PaddleOCR real.

## Pendientes reales

Credencial y evaluación real de IA; importación/auditoría del corpus completo; normalización integral de compromisos y entidades; nuevos conectores por organismo; georreferencias exactas de operaciones/ONP verificadas; autenticación y permisos SaaS; correo; despliegue externo; entrevistas y video. El autor confirmó que presentará sin entrevistas; no se inventaron.

## Arranque

```powershell
.\iniciar.ps1
# o, con trabajador periódico:
.\iniciar.ps1 -Automatizar
```

URL local: http://127.0.0.1:8765 . Se conserva el prototipo anterior como legacy_streamlit.py; el punto de entrada principal es ahora python app.py o python -m pulso.web.
