> **Documento histórico** (primera versión, mediodía del 10 de noviembre de 2026). El estado vigente está en el [README](../README.md) y el guion en [PRESENTACION.md](PRESENTACION.md).

# Verificación de PulsoTerritorial

Autor: Alexander Noblejas. Fecha: 10 de noviembre de 2026, America/Lima.

## Comprobado

- Descarga real de tres reportes oficiales de la Defensoría: 201 páginas PDF y68 secciones HTML. Catálogo:257 enlaces descubiertos, sin afirmar descarga de todos ellos.
- Persistencia de originales, SHA-256 y SQLite; períodos2026-03,2026-04,2026-09.
- 26 pruebas automatizadas aprobadas en la ejecución final (1.84segundos): 17 del núcleo y9 del adaptador OCR simulado. Incluyen PDF real generado como fixture, duplicados/procedencia, formato HTML, cita inválida, presupuesto antes de envío, proveedor simulado, versión corregida y reanudación tras fallo.
- Interfaz Streamlit con la biblioteca oficial, sin simular el servicio: filtro por PDF y HTML, período, búsqueda y boletín. Resultado de referencia:7 secciones HTML para Las Bambas y8 páginas PDF con límite8. El boletín de esa prueba mide13396 caracteres.
- Recorrido visible en navegador: búsqueda Las Bambas, apertura de referencia, generación de boletín y revisión de cobertura. Capturas guardadas. Servidor local http://127.0.0.1:8501.
- Cotejo visual de la página38 del reporte266: el pasaje de Huancuire/Las Bambas está en la página; también hay otro caso en ella. Los recortes no se interpretan como expedientes consolidados.
- Generación automática por consultas de ejemplo en config/watchlist.json, con archivos e historia de cambios de evidencia. El modo periódico se ejecuta con iniciar.ps1 -Automatizar o automatizar.ps1; no se instaló tarea de Windows.

## Implementado sin prueba real completa

- Adaptadores Groq, Gemini y NVIDIA: ninguna clave configurada ni llamada autenticada. La prueba simulada no verifica cuenta, modelo disponible, latencia, cuota o exactitud real.
- PaddleOCR3 opcional: nueve pruebas simuladas de contrato; motor y pesos no instalados. Los candidatos no sustituyen automáticamente evidencia original.
- Modo de ejecución periódica: lógica y comandos incluidos, generación de boletines comprobada; no se ha observado una espera real de seis horas ni recuperación tras reinicio de Windows.
- Dependencias declaradas y flujo CI preparado. El entorno local reutiliza bibliotecas ya instaladas mediante un entorno virtual; no se validó un despliegue limpio en otro equipo.

## Pendiente del producto completo

Corpus histórico completo; expedientes longitudinales; resolución de empresas; geometrías, operaciones y carreteras; correo; multiusuario; validación semántica y medición de calidad.

## Pendiente de la entrega

El autor confirmó que no tiene tres conversaciones reales y presentará sin esa validación. Repositorio público, despliegue público, video y publicación del enlace en el issue204 no se realizaron. No se inventaron entrevistas ni commits anteriores. No se atribuye una nota probable.
