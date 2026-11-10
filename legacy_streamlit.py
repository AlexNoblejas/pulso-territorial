"""Interfaz de PulsoTerritorial. Ejecutar con streamlit run app.py."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from pulso import service


st.set_page_config(page_title="PulsoTerritorial", page_icon="◉", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: #f5f7fa; }
    [data-testid="stSidebar"] { background: #102a43; }
    [data-testid="stSidebar"] * { color: #eef5f9; }
    [data-testid="stSidebar"] hr { border-color: #395569; }
    .pulso-hero { padding: 1.5rem 1.7rem; background: #102a43;
      border-radius: 14px; color: white; margin-bottom: 1.2rem; }
    .pulso-hero h1 { color: white; font-size: 2.25rem; padding: 0; margin: .3rem 0; }
    .pulso-hero p { color: #d7e7ef; max-width: 850px; margin: .5rem 0 0; }
    .pulso-eyebrow { color: #70dfb1; letter-spacing: .13em; font-size: .75rem; font-weight: 700; }
    div[data-testid="stMetric"] { background: white; padding: 1rem 1.2rem;
      border-radius: 10px; border: 1px solid #e1e8ee; }
    .stButton > button[kind="primary"] { background: #087f5b; border-color: #087f5b; }
    .stTabs [data-baseweb="tab-list"] { gap: 1.3rem; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; }
    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


def error_message(exc: Exception, action: str) -> None:
    """Evitar volcar respuestas de proveedores o credenciales en pantalla."""
    if isinstance(exc, ValueError):
        st.error(f"No pudimos {action}. {str(exc)[:500]}")
    else:
        st.error(f"No pudimos {action}. {type(exc).__name__}: revisa la configuración y vuelve a intentarlo.")


def source_label(hit: dict, index: int, ai: bool = False) -> str:
    location = "sección de extracción HTML" if hit.get("method") == "html_section" else "página PDF"
    source_id = f"E{index}" if ai else str(index)
    return f"[{source_id}] {hit.get('title', 'Documento')} · {location} {hit.get('page', '?')}"


def show_hit(hit: dict, index: int, expanded: bool = False, ai: bool = False) -> None:
    with st.expander(source_label(hit, index, ai=ai), expanded=expanded):
        st.text(hit.get("text", ""))
        cols = st.columns([3, 2])
        if hit.get("url", "").startswith("https://"):
            source_url = hit["url"]
            if hit.get("method") != "html_section":
                source_url += f"#page={hit.get('page', 1)}"
            cols[0].markdown(f"[Consultar documento original]({source_url})")
        else:
            cols[0].caption("Documento cargado desde esta computadora.")
        cols[1].caption(f"Método: {hit.get('method', 'texto PDF')} · evidencia documental")


try:
    service.init_db()
    counts = service.stats()
    documents = service.list_documents()
    configured = service.provider_status()
except Exception as exc:
    error_message(exc, "abrir la biblioteca")
    st.stop()

for key, default in {
    "hits": [], "last_query": "", "last_company": "", "ai_answer": None,
    "ai_extract": None, "bulletin_text": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

with st.sidebar:
    st.markdown("## ◉ PulsoTerritorial")
    st.caption("INTELIGENCIA SOCIOAMBIENTAL")
    st.markdown("Evidencia pública para comprender los territorios y dar seguimiento a lo reportado.")
    st.divider()
    st.markdown("**Tu biblioteca**")
    st.write(f"{counts.get('documents', 0)} documentos · {counts.get('pages', 0)} páginas/secciones")
    st.markdown("**Asistentes disponibles**")
    provider_names = {"groq": "Groq", "gemini": "Gemini", "nvidia": "NVIDIA"}
    for provider, label in provider_names.items():
        st.caption(f"{'●' if configured.get(provider) else '○'} {label} · {'configurado' if configured.get(provider) else 'sin configurar'}")
    st.divider()
    st.caption("Puedes buscar y generar boletines sin una API de inteligencia artificial.")
    st.caption("Piloto documental. La cobertura corresponde exclusivamente a los archivos incorporados.")

st.markdown(
    """<div class="pulso-hero"><div class="pulso-eyebrow">DE LOS REPORTES A LA EVIDENCIA</div>
    <h1>PulsoTerritorial</h1><p>Encuentra menciones de empresas y territorios, consulta sus fuentes
    y prepara un boletín de seguimiento.</p></div>""",
    unsafe_allow_html=True,
)
metrics = st.columns(3)
metric_slots = [column.empty() for column in metrics]


def refresh_metrics(current_counts: dict) -> None:
    metric_slots[0].metric("Reportes incorporados", current_counts.get("documents", 0))
    metric_slots[1].metric("Páginas y secciones", current_counts.get("pages", 0))
    metric_slots[2].metric("Unidades sin texto suficiente", current_counts.get("ocr_pending", 0))


refresh_metrics(counts)
st.caption("Una coincidencia textual no prueba afectación a una empresa. Los reportes describen información atribuida a su fuente y período.")

explore, ingest, assistant, newsletter, health = st.tabs(
    ["Explorar evidencia", "Incorporar reportes", "Asistente IA", "Boletín", "Estado"]
)

with explore:
    st.subheader("Busca en la biblioteca")
    st.write("Consulta una empresa, una operación, una localidad o una demanda. Los resultados conservan su documento y su página PDF o sección de extracción HTML.")
    periods = sorted({str(doc.get("period", "")) for doc in documents if doc.get("period")}, reverse=True)
    left, right = st.columns(2)
    period_label = left.selectbox("Período del reporte", ["Todos los períodos"] + periods)
    period = "" if period_label == "Todos los períodos" else period_label
    period_docs = [doc for doc in documents if not period or str(doc.get("period", "")) == period]
    doc_map = {str(doc["id"]): doc for doc in period_docs}
    document_options = {f"{doc['title']} · {str(doc['id'])[:10]}": str(doc["id"]) for doc in period_docs}
    selected_label = right.selectbox("Documento", ["Todos los documentos del período"] + list(document_options))
    selected_doc = document_options.get(selected_label, "")
    with st.form("search_form"):
        company_col, territory_col = st.columns(2)
        company = company_col.text_input("Empresa, operación o tema", placeholder="Por ejemplo: Las Bambas")
        territory = territory_col.text_input("Territorio o término adicional", placeholder="Por ejemplo: Apurímac")
        limit = st.slider("Máximo de fragmentos a mostrar", 3, 20, 8)
        submitted = st.form_submit_button("Buscar evidencia", type="primary", disabled=not documents)
    if not documents:
        st.info("Primero incorpora un PDF o descarga los reportes oficiales en la pestaña «Incorporar reportes».")
    if submitted:
        query = " ".join(value.strip() for value in (company, territory) if value.strip())
        if not query:
            st.warning("Escribe al menos un término para buscar.")
        else:
            try:
                with st.spinner("Consultando páginas y fuentes…"):
                    if selected_doc:
                        hits = service.search(query, document_id=selected_doc, limit=limit)
                    elif period:
                        hits = []
                        for doc in period_docs:
                            hits.extend(service.search(query, document_id=str(doc["id"]), limit=limit))
                        hits = sorted(hits, key=lambda item: item.get("score", 0), reverse=True)[:limit]
                    else:
                        hits = service.search(query, limit=limit)
                st.session_state.hits = hits
                st.session_state.last_query = query
                st.session_state.last_company = company.strip()
                st.session_state.ai_answer = None
                st.session_state.ai_extract = None
                st.session_state.bulletin_text = ""
                st.session_state.pop("selected_evidence", None)
            except Exception as exc:
                error_message(exc, "completar la búsqueda")
    if st.session_state.last_query:
        st.markdown(f"**Última consulta:** {st.session_state.last_query}")
        st.caption(f"{len(st.session_state.hits)} fragmentos recuperados. Búsqueda textual; comprueba el contexto en la fuente.")
        if not st.session_state.hits:
            st.info("No encontramos coincidencias. Prueba con otra denominación. La ausencia de resultados no demuestra ausencia de conflictos.")
    for idx, hit in enumerate(st.session_state.hits, 1):
        show_hit(hit, idx, expanded=idx == 1)

with ingest:
    st.subheader("Incorpora fuentes verificables")
    load_col, sync_col = st.columns(2)
    with load_col:
        st.markdown("#### Desde tu computadora")
        st.write("Carga un reporte PDF. El archivo y sus páginas se conservarán en la biblioteca local.")
        upload = st.file_uploader("Selecciona el reporte", type=["pdf"], accept_multiple_files=False)
        upload_period = st.text_input("Período reportado (opcional)", placeholder="2026-09", key="upload_period")
        if st.button("Incorporar PDF", disabled=upload is None, type="primary"):
            try:
                with st.spinner("Extrayendo y registrando el documento…"):
                    result = service.ingest_upload(upload.getvalue(), upload.name, period=upload_period.strip())
                counts = service.stats()
                documents = service.list_documents()
                refresh_metrics(counts)
                st.success(f"Documento PDF registrado: {result.get('pages', '?')} páginas. Abre «Estado» para revisar la cobertura.")
            except Exception as exc:
                error_message(exc, "incorporar el PDF")
        st.caption("Un PDF escaneado puede necesitar OCR antes de ser consultable. La carga no se envía a proveedores de IA.")
    with sync_col:
        st.markdown("#### Desde fuentes oficiales")
        st.write("Revisa las fuentes configuradas, descarga archivos nuevos y evita duplicados mediante su huella digital.")
        sync_limit = st.number_input("Máximo de descargas en esta revisión", min_value=1, max_value=10, value=2, step=1)
        if st.button("Revisar y descargar reportes"):
            try:
                with st.spinner("Revisando las fuentes oficiales…"):
                    sync_result = service.sync_sources(limit=int(sync_limit))
                st.session_state["sync_result"] = sync_result
                counts = service.stats()
                documents = service.list_documents()
                refresh_metrics(counts)
            except Exception as exc:
                error_message(exc, "revisar las fuentes")
        if st.session_state.get("sync_result"):
            result = st.session_state.sync_result
            st.success(f"Descargados: {result.get('downloaded', 0)} · ya registrados: {result.get('existing', 0)}")
            st.caption(f"Enlaces descubiertos: {result.get('discovered', 0)}. Esta revisión no acredita la descarga del archivo histórico completo.")
            for issue in result.get("errors", []):
                st.warning(str(issue))

with assistant:
    st.subheader("Pregunta con evidencia a la vista")
    st.write("Selecciona hasta cuatro fragmentos recuperados y un proveedor. La respuesta se construye a partir de esos fragmentos; revisa sus citas antes de utilizarla.")
    provider_label = st.selectbox("Proveedor de inteligencia artificial", list(provider_names.values()))
    provider = next(key for key, label in provider_names.items() if label == provider_label)
    ready = bool(configured.get(provider))
    if not ready:
        st.info("Este proveedor aún no tiene una clave configurada. Añádela al archivo de configuración local; no la publiques ni la pegues en el chat.")
    hits = st.session_state.hits
    if not hits:
        st.info("Busca primero una empresa o un territorio en «Explorar evidencia».")
    evidence_options = {source_label(hit, index + 1): hit for index, hit in enumerate(hits)}
    selected = st.multiselect(
        "Fragmentos que se enviarán al proveedor", options=list(evidence_options),
        default=list(evidence_options)[:3], key="selected_evidence", max_selections=4,
    )
    evidence = [evidence_options[label] for label in selected]
    st.caption(f"{len(evidence)} de 4 fragmentos seleccionados. Solo su texto y tu pregunta se envían al proveedor elegido. Revisa que el contenido sea apropiado para compartir.")
    question = st.text_area("Tu pregunta", placeholder="¿Qué demandas y acuerdos aparecen en estos fragmentos? Distingue lo reportado de lo que no consta.", height=95)
    ask_col, extract_col = st.columns(2)
    if ask_col.button("Responder con fuentes", type="primary", disabled=not ready or not evidence or not question.strip()):
        try:
            with st.spinner("Preparando respuesta documentada…"):
                result = service.ask(question.strip(), evidence, provider)
                result["_evidence"] = evidence
                st.session_state.ai_answer = result
        except Exception as exc:
            error_message(exc, "obtener la respuesta")
    if extract_col.button("Estructurar hechos y compromisos", disabled=not ready or not evidence):
        try:
            with st.spinner("Extrayendo registros y comprobando sus citas…"):
                result = service.extract(evidence, provider)
                result["_evidence"] = evidence
                st.session_state.ai_extract = result
        except Exception as exc:
            error_message(exc, "estructurar la evidencia")
    answer = st.session_state.ai_answer
    if answer:
        st.markdown("#### Respuesta asistida")
        st.markdown(answer.get("answer", ""))
        st.caption(f"Modelo: {answer.get('model', 'no informado')} · Uso: {answer.get('usage', {})}")
        st.markdown("**Fuentes enviadas para esta respuesta**")
        for index, hit in enumerate(answer.get("_evidence", []), 1):
            show_hit(hit, index, ai=True)
    extracted = st.session_state.ai_extract
    if extracted:
        st.markdown("#### Registros extraídos")
        st.caption("La validación de una cita comprueba respaldo textual; no equivale a una revisión humana del hecho ni del cumplimiento de un compromiso.")
        if extracted.get("records"):
            st.json(extracted["records"])
        else:
            st.info("No se aceptaron registros con evidencia suficiente.")
        for rejection in extracted.get("rejected", []):
            st.warning(str(rejection))
        st.caption(f"Modelo: {extracted.get('model', 'no informado')} · Uso: {extracted.get('usage', {})}")
        st.markdown("**Fuentes enviadas para esta extracción**")
        for index, hit in enumerate(extracted.get("_evidence", []), 1):
            show_hit(hit, index, ai=True)

with newsletter:
    st.subheader("Prepara un boletín de seguimiento")
    st.write("Genera un documento con los resultados de tu última búsqueda y referencias a la evidencia. Funciona sin una API de IA.")
    st.caption(f"Consulta utilizada: {st.session_state.last_query or 'aún no hay una consulta'} · {len(st.session_state.hits)} fragmentos")
    if st.button("Generar borrador de boletín", type="primary", disabled=not st.session_state.hits):
        try:
            st.session_state.bulletin_text = service.bulletin(st.session_state.hits, company=st.session_state.last_company)
        except Exception as exc:
            error_message(exc, "generar el boletín")
    if st.session_state.bulletin_text:
        st.markdown(st.session_state.bulletin_text)
        st.download_button(
            "Descargar boletín", data=st.session_state.bulletin_text,
            file_name=f"PulsoTerritorial_{datetime.now():%Y%m%d}.md", mime="text/markdown",
        )
    st.info("El boletín es un borrador descargable. Esta pantalla no envía correos ni registra suscriptores.")

with health:
    st.subheader("Cobertura y trazabilidad")
    st.write("Esta tabla muestra los documentos realmente incorporados. Un reporte de otro período puede cambiar o actualizar la información.")
    if documents:
        rows = [
            {
                "Reporte": doc.get("title", ""), "Período": doc.get("period", ""),
                "Páginas / secciones": doc.get("pages", 0), "Sin texto suficiente": doc.get("ocr_pending", 0),
                "Incorporado": doc.get("ingested_at", ""), "Fuente": doc.get("url", "Carga local"),
                "Huella SHA-256": doc.get("sha256", ""),
            }
            for doc in documents
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("La biblioteca todavía está vacía.")
    st.markdown("#### Cómo interpretar los resultados")
    st.markdown(
        "- Un fragmento encontrado es evidencia documental, no un conflicto único.\n"
        "- Las secciones HTML son unidades de extracción; no son páginas ni localizadores del documento original.\n"
        "- Una mención no demuestra responsabilidad ni afectación operativa.\n"
        "- Un acuerdo reportado no se considera cumplido o incumplido sin evidencia posterior.\n"
        "- La falta de menciones no demuestra ausencia de acontecimientos.\n"
        "- Las páginas sin texto suficiente requieren OCR y pueden quedar fuera de la búsqueda."
    )
    st.caption("La conexión con mapas, carreteras y servicios de correo requiere integraciones y verificaciones adicionales.")
