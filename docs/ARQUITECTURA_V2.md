# Arquitectura V2

La experiencia principal pasa de un buscador a una cartera empresarial. La unidad longitudinal sigue siendo el caso; cada estado/fase corresponde a una observación de un reporte. Un acontecimiento y un compromiso son unidades distintas, con fuentes y fechas propias.

`service.py` retiene originales, páginas/secciones, hashes, versiones, consumo y lotes en SQLite. `portfolio.py` lee fichas `.caso-card` de HTML oficial, reconoce menciones empresariales y arma carteras. Mantiene los códigos de investigación históricos separados de los códigos oficiales. Selecciona la última versión por período y no usa fases editoriales para rellenar datos ausentes. `config/case_annotations.json` contiene síntesis y acuerdos revisados de una versión concreta, anclada a SHA; un cambio invalida esas lecturas.

`web.py` expone GET cartera/geografía/reporte/estado y POST actualización/interpretación, sólo en127.0.0.1. Valida Host, Origin y tamaño/tipo de solicitud. No devuelve rutas de la laptop. Los perfiles demo son contextos públicos, no autenticación ni aislamiento de clientes. `web/` usa módulosJS, escapes HTML, rutas de fuente seguras, MapLibre y SVG. Datos y secretos permanecen en Python; sólo se sirve evidencia pública seleccionada.

`reports.py` genera un HTML portable con mapa vectorial referencial, fases, serie temporal, lectura editorial y evidencia; no depende de servicios de mapas para susSVG. `cli.py` puede capturar y regenerar reportes periódicamente, con exclusión de trabajadores simultáneos. No garantiza disponibilidad de sitios, ejecución con laptop apagada ni revisión automática de todos los contenidos nuevos.

Las geometrías se filtraron localmente y normalizaron a EPSG4326 con GeoPandas/pyogrio. Se conservaron fechas de carreteras2018/pozos2020 y precisiones. Los puntos distritales o de polígonos comunales no equivalen a incidentes geocodificados. Se detectó una diferencia jurisdiccional Huancuire entre capa y reporte y se conserva como discrepancia.

Para producción: PostgreSQL/PostGIS con publicación/versión/observación/evento/compromiso/evidencia separados; originales inmutables, colas, permisos por cliente, autenticación real, evaluaciones y conciliación humana. Añadir conectores propios de cada organismo con licencia y prueba de actualización; reconciliar empresas/activos y fechas. El correo requiere destinatarios, consentimiento y registro de entregas. La capacidad preparada de un conector de IA no sustituye probarlo con clave, costo y muestra anotada.
