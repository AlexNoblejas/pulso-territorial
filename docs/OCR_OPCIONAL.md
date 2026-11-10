# OCR opcional: alcance y activación

El adaptador está implementado y probado con respuestas simuladas. **No se instaló ni ejecutó PaddleOCR real en esta laptop.** No contabilizarlo como herramienta demostrada hasta validar una página escaneada y cotejarla visualmente con el original.

Usa `PaddleOCR.predict(input=ruta_png)` y normaliza los campos `rec_texts` y `rec_scores` desde `result.json`. Sólo propone OCR para páginas PDF con menos de 40 caracteres normalizados. Conserva el texto pypdf y la huella del PDF; produce candidatos pendientes de revisión, sin modificar la base. [API oficial PaddleOCR](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html).

## Instalación separada en Windows CPU

Usar Python 3.10 de 64 bits y CPU x64 compatible con AVX/MKL. La guía oficial contempla Python 3.10 en Windows x64. [Requisitos Windows](https://paddlepaddle-static.cdn.bcebos.com/documentation/docs/en/install/pip/windows-pip_en.html).

Desde StarUp, crear un entorno separado evita alterar la demostración básica:

```powershell
python -m venv .venv-ocr
.\.venv-ocr\Scripts\python.exe -m pip install --upgrade pip
.\.venv-ocr\Scripts\python.exe -m pip install "paddlepaddle>=3.3,<4" -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
.\.venv-ocr\Scripts\python.exe -m pip install -r requirements.txt -r requirements-ocr.txt
.\.venv-ocr\Scripts\python.exe -c "import paddle; paddle.utils.run_check()"
```

Paddle publica instalación CPU con índice oficial. [Instrucciones Paddle](https://paddlepaddle.github.io/PaddleX/latest/en/installation/paddlepaddle_install.html). Los rangos anteriores son una configuración candidata, no un conjunto validado en esta máquina. Tras una prueba real exitosa, conservar `pip freeze` y el nombre de los modelos utilizados. La primera inicialización puede descargar pesos y tardar; no estrenarla durante la exposición.

## Integración propuesta

Importar `recognize_pending`, entregar bytes del PDF original y las filas de `pages` correspondientes. Guardar cada resultado en una tabla separada, por ejemplo `ocr_candidates(document_id,page,original_sha256,created_at,payload,review_status)`. Mantener `pages.text` y `pages.method=pypdf` como originales. Sólo tras revisión explícita, usar una vista que seleccione la versión OCR aprobada y muestre método `paddleocr3`; no sobrescribir silenciosamente la evidencia original.

`status=candidate` significa que hubo texto, no que sea correcto. Los scores son señales internas del reconocedor; ni un valor alto certifica exactitud ni uno bajo acredita falsedad. El umbral 0.8 únicamente destaca líneas para revisar. Un fallo o salida vacía conserva el pendiente OCR. Las tablas, orden de lectura y nombres propios requieren inspección específica.

## Ejecución del adaptador incluido

Después de instalar y verificar Paddle, consultar el identificador en Estado o manifest.json y ejecutar desde StarUp:

```powershell
.\.venv-ocr\Scripts\python.exe -m pulso.ocr_optional IDENTIFICADOR_DOCUMENTO --limit 2
```

Guarda candidatos en data/ocr_candidates. No modifica ni aprueba el texto de la biblioteca; la indexación de OCR revisado es una ampliación pendiente. Si no hay páginas elegibles, genera una lista vacía.
