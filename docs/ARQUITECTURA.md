> **Documento histórico** (primera versión, mediodía del 10 de noviembre de 2026). El estado vigente está en el [README](../README.md) y el guion en [PRESENTACION.md](PRESENTACION.md).

# Arquitectura de PulsoTerritorial

## Sistema local implementado

`app.py` presenta cinco vistas de Streamlit. `pulso/service.py` valida descargas, extrae texto, conserva originales y consultas en SQLite. `pulso/cli.py` ejecuta lotes y el trabajador periódico. `config/watchlist.json` contiene consultas de ejemplo para boletines. No son suscripciones de clientes reales.

Tablas: `documents` (SHA-256, procedencia, período y cobertura), `pages` (texto original y método), `source_checks` (reintentos/versiones), `runs` (ejecuciones), `ai_usage` (reserva y uso) y `extractions` (JSON pendiente de revisión). Los documentos originales quedan en `data/raw`. El trabajador guarda `manifest.json` y boletines por consulta, con historia cuando cambia la evidencia. La memoria del chat de interfaz no sustituye el inventario persistente.

La descarga revisa dominios HTTPS y cada redirección, firma PDF, tamaño de 25MB y máximo400 páginas. El HTML debe tener contenido compatible con reporte. Un fallo queda registrado y no se presenta como cobertura. La deduplicación usa contenido, enriquece procedencia cuando un archivo local coincide con fuente oficial, y preserva otra versión si cambia una URL. La vinculación documental de versiones es por URL; todavía no hay entidad publicación independiente.

La búsqueda es léxica: requiere todos los términos útiles, ignora palabras comunes y normaliza acentos. Devuelve fragmentos originales con página PDF o sección HTML. No reconstruye los límites de los casos dentro de una página, por lo que un recorte puede contener texto de varios expedientes. El usuario debe revisar la fuente. Las secciones HTML se reproducen con el original conservado y esta versión de segmentación; no son anclas del sitio público.

## Contrato de evidencia

Un modelo sólo recibe los fragmentos seleccionados. Devuelve registros con tipo, afirmación, cita y fuente. Se comprueba que la cita exista literalmente después de normalizar espacios. La comprobación no prueba implicación semántica; el estado se mantiene pendiente de revisión. No se convierte automáticamente una demanda o un acuerdo reportado en una obligación vigente.

El presupuesto global diario se reserva con una transacción SQLite antes del envío. Una llamada fallida conserva la reserva y el estado. El día de uso es UTC; fechas de presentación siguen America/Lima. Se limita contexto y salida; los valores de cuota de la cuenta no se consultaron. Los modelos son configuración, y una API puede rechazar un nombre o una cuota aunque su documentación lo anuncie.

El OCR opcional produce candidatos en archivos separados y preserva el texto pypdf. No existe todavía una interfaz de aprobación ni una vista que indexe candidatos OCR aprobados. No se requiere instalar OCR para ejecutar el piloto sobre PDFs textuales.

## Evolución hacia el producto completo

El próximo modelo debe distinguir `publication`, `document_version`, `conflict_case`, `case_observation`, `event`, `organization`, `organization_alias`, `company_operation`, `commitment` y `evidence_span`. Una aparición mensual es una observación, no otro conflicto. Un compromiso requiere responsable, fecha prevista y estado reportado; su cumplimiento se documenta separadamente.

Primero auditar cobertura del corpus histórico existente y conservar sus identificadores; no importarlo directamente como verdad. Crear muestra manual de referencias por caso y mes, cotejar páginas y medir errores por campo. Resolver alias empresariales con revisión. Añadir conectores PCM/OEFA/MINAM uno por uno con contrato y prueba de actualización.

Después incorporar PostgreSQL/PostGIS, geometrías oficiales versionadas, UBIGEO, CRS y precisión de cada ubicación. Separar mención directa, proximidad geográfica y exposición logística verificada. Una distancia o un distrito compartido no prueban afectación. Para carreteras se requiere red vial y evidencia vigente de incidentes; una concesión no equivale a operación activa.

El servicio comercial necesita API, cola de trabajos, almacén de documentos, usuarios y permisos por cliente, auditoría, backups, evaluación de extracción y búsqueda, y alertas con un flujo de revisión. El correo requiere destinatarios confirmados, baja y deduplicación de entregas; no está implementado. Las recomendaciones normativas necesitan corpus normativo actualizado y revisión experta: no se generan en este piloto.

## Capas y etapas

| Etapa | Criterio de salida |
|---|---|
| Piloto documental local | Ingesta, consulta y boletín reales, con evidencia y funcionamiento sin API |
| IA validada | Llamada real por proveedor elegido, muestra revisada, abstención y costo medidos |
| Casos longitudinales | Identificadores estables, observaciones mensuales y acuerdos sin doble conteo |
| Territorio y logística | Capas verificadas, fechas, CRS, precisión y límites visibles |
| Servicio con clientes | Entrevistas, piloto pagado, permisos y entrega de alertas comprobados |

El alcance actual corresponde a la primera etapa, con adaptadores para la segunda. No implica preparación para producción ni cobertura histórica completa.
