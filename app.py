"""Interfaz web para el sistema multiagente de estudio de mercado."""

from __future__ import annotations

import hmac
import json
import os
import queue
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from agentes.base_agent import AgentResult
from orquestador import cargar_configuracion, ejecutar_estudio


ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "informes" / "informe_mercado.md"
CACHE_DIR = ROOT / "informes" / "cache"
AGENT_META = {
    1: (
        "Cambios de la Industria",
        "¿Cuáles son los cambios más significativos en mi industria en los últimos 3-6 meses?",
    ),
    2: (
        "Voz del Cliente",
        "¿Qué necesidades no satisfechas o frustraciones emergentes expresan los clientes?",
    ),
    3: (
        "Soluciones Innovadoras",
        "¿Qué nuevos actores o productos están resolviendo estas necesidades de manera no obvia?",
    ),
    4: (
        "Formatos y Propuestas de Valor",
        "¿Qué formatos de producto, modelos de entrega o propuestas ganan tracción?",
    ),
    5: (
        "Riesgos y Brechas Propias",
        "¿Qué riesgos o brechas existen en mi enfoque actual?",
    ),
    6: (
        "Ideas Obsoletas",
        "¿Qué ideas o tendencias han perdido relevancia?",
    ),
    7: (
        "Hipótesis Estratégica",
        "¿Cuál es una hipótesis estratégica de alto impacto que debería probar?",
    ),
}
WINDOW_OPTIONS = {
    "3 meses": "últimos 3 meses",
    "6 meses": "últimos 6 meses",
    "12 meses": "últimos 12 meses",
}
CONFIDENCE_LEVELS = {"Bajo": 1, "Medio": 2, "Alto": 3}


def _read_secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except Exception:
        return None
    return str(value) if value else None


def _load_saved_config() -> dict[str, Any]:
    try:
        return cargar_configuracion(str(ROOT / "config.yaml"))
    except (SystemExit, OSError, ValueError):
        return {
            "industria": "",
            "descripcion_negocio": "",
            "pais": "",
            "ventana_analisis": "últimos 6 meses",
        }


def _config_identity(config: dict[str, Any]) -> dict[str, str]:
    return {
        key: str(config.get(key, ""))
        for key in ("industria", "descripcion_negocio", "pais", "ventana_analisis")
    }


def _cache_path(agent_id: int) -> Path:
    return CACHE_DIR / f"agente_{agent_id}.json"


def _safe_error_text(error: str | None, secrets_to_redact: list[str] | None = None) -> str | None:
    if not error:
        return error
    safe_error = error
    for secret in secrets_to_redact or []:
        if secret:
            safe_error = safe_error.replace(secret, "[CLAVE OCULTA]")
    return safe_error


def _save_cached_result(result: AgentResult, config: dict[str, Any], secret_values: list[str]):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "config": _config_identity(config),
        "result": asdict(result),
    }
    payload["result"]["error"] = _safe_error_text(
        payload["result"].get("error"), secret_values
    )
    target = _cache_path(result.agente_id)
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def _load_cached_results(config: dict[str, Any] | None = None) -> list[AgentResult]:
    results = []
    expected_config = _config_identity(config) if config else None
    for agent_id in AGENT_META:
        try:
            payload = json.loads(_cache_path(agent_id).read_text(encoding="utf-8"))
            if expected_config and payload.get("config") != expected_config:
                continue
            results.append(AgentResult(**payload["result"]))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            continue
    return results


@contextmanager
def _temporary_credentials(credentials: dict[str, str]):
    previous = {key: os.environ.get(key) for key in credentials}
    try:
        for key, value in credentials.items():
            if not os.environ.get(key):
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _launch_study(
    config: dict[str, Any],
    mock_mode: bool,
    only_agent: int | None,
    seed_results: list[AgentResult],
    credentials: dict[str, str],
    secret_values: list[str],
):
    events: queue.Queue = queue.Queue()
    st.session_state["study_events"] = events
    st.session_state["study_running"] = True
    st.session_state["study_done"] = False
    st.session_state["study_quota_wait"] = None
    st.session_state["study_config"] = config
    st.session_state["study_report"] = None
    st.session_state["study_results"] = {
        result.agente_id: result for result in seed_results
    }
    st.session_state["study_status"] = {
        agent_id: "pendiente" for agent_id in AGENT_META
    }
    for result in seed_results:
        st.session_state["study_status"][result.agente_id] = (
            "falló" if result.error else "truncado" if result.aviso_corte else "éxito"
        )

    def publish_event(event: dict[str, Any]):
        if event.get("type") == "result":
            result = event["result"]
            _save_cached_result(result, config, secret_values)
            events.put(event)
        else:
            events.put(event)

    def worker():
        try:
            output_path = (
                str(CACHE_DIR / "simulacion.md")
                if mock_mode
                else str(REPORT_PATH)
            )
            with _temporary_credentials(credentials):
                results, report = ejecutar_estudio(
                    config=config,
                    mock_mode=mock_mode,
                    output_path=output_path,
                    only_agent=only_agent,
                    previous_results=seed_results,
                    on_event=publish_event,
                )
            events.put({"type": "finished", "results": results, "report": report})
        except Exception as error:
            events.put(
                {
                    "type": "fatal",
                    "message": _safe_error_text(str(error), secret_values)
                    or "No se pudo completar el estudio.",
                }
            )

    thread = threading.Thread(target=worker, name="market-study", daemon=True)
    thread.start()


def _auth_gate() -> bool:
    password = _read_secret("APP_PASSWORD")
    if not password:
        return True
    if st.session_state.get("authenticated", False):
        return True

    st.title("Acceso protegido")
    with st.form("login_form"):
        entered = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar", type="primary")
    if submitted:
        if hmac.compare_digest(entered, password):
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("La contraseña no es correcta.")
    st.stop()


def _render_agent_status():
    events = st.session_state.get("study_events")
    if events:
        while True:
            try:
                event = events.get_nowait()
            except queue.Empty:
                break
            event_type = event.get("type")
            if event_type == "status":
                st.session_state["study_status"][event["agent_id"]] = event["status"]
            elif event_type == "phase":
                st.session_state["study_phase"] = event["phase"]
            elif event_type == "wait":
                wait_seconds = float(event.get("seconds", 0))
                st.session_state["study_quota_wait"] = {
                    "seconds": wait_seconds,
                    "reason": event.get("reason", "Límite de cuota"),
                    "until": time.monotonic() + min(wait_seconds, 600),
                    "daily_limit": wait_seconds > 600,
                }
            elif event_type == "result":
                result = event["result"]
                st.session_state["study_results"][result.agente_id] = result
            elif event_type == "finished":
                st.session_state["study_results"] = {
                    result.agente_id: result for result in event["results"]
                }
                st.session_state["study_report"] = event["report"]
                st.session_state["study_running"] = False
                st.session_state["study_done"] = True
            elif event_type == "fatal":
                st.session_state["study_running"] = False
                st.session_state["study_done"] = True
                st.session_state["study_fatal"] = event["message"]

    results = st.session_state.get("study_results", {})
    statuses = st.session_state.get("study_status", {})
    failures = [
        result for result in results.values()
        if result.error or result.aviso_corte
    ]
    if failures and (st.session_state.get("study_running") or st.session_state.get("study_done")):
        st.warning(
            f"El informe está incompleto: {sum(bool(result.error) for result in failures)} agente(s) fallido(s) "
            f"y {sum(bool(result.aviso_corte) for result in failures)} sección(es) truncada(s)."
        )
    wait = st.session_state.get("study_quota_wait")
    if wait and wait["daily_limit"]:
        st.error(
            f"Cuota diaria de Gemini agotada. El servicio solicita esperar "
            f"{wait['seconds']:.0f} segundos; se detuvo el reintento y se conservan los resultados ya generados."
        )
    elif wait and st.session_state.get("study_running"):
        seconds_left = max(0, wait["until"] - time.monotonic())
        st.info(f"{wait['reason']}: esperando {seconds_left:.0f} segundos por el límite de cuota.")

    phase = st.session_state.get("study_phase", 1)
    phase_names = ["Investigación exterior", "Diagnóstico interno", "Hipótesis estratégica"]
    phase_cols = st.columns(3)
    for index, name in enumerate(phase_names, start=1):
        state = "En curso" if st.session_state.get("study_running") and phase == index else (
            "Lista" if phase > index or st.session_state.get("study_done") else "Pendiente"
        )
        phase_cols[index - 1].metric(f"Fase {index}: {name}", state)

    for agent_id, (name, question) in AGENT_META.items():
        result = results.get(agent_id)
        status = statuses.get(agent_id, "pendiente")
        with st.container(border=True):
            st.markdown(f"**Agente {agent_id}: {name}** · {_status_label(status)}")
            if status == "falló":
                st.error("Estado: falló")
            elif status == "truncado":
                st.warning("Estado: truncado")
            elif status == "trabajando":
                st.info("Estado: trabajando")
            elif status == "éxito":
                st.success("Estado: éxito")
            st.caption(question)
            if result:
                detail_cols = st.columns(3)
                detail_cols[0].metric("Tiempo", f"{result.tiempo_ejecucion_segundos:.2f} s")
                detail_cols[1].metric("Fuentes", len(result.fuentes))
                detail_cols[2].metric("Confianza", result.nivel_confianza)
                if result.error:
                    st.error("SECCIÓN NO GENERADA")
                    with st.expander("Ver detalle técnico"):
                        st.code(_safe_error_text(result.error), language="text")
                elif result.aviso_corte:
                    st.warning("RESPUESTA TRUNCADA")


@st.fragment(run_every="1s")
def _render_live_progress():
    if st.session_state.get("study_running"):
        with st.status("Estudio en ejecución", expanded=True, state="running"):
            st.caption("El trabajo continúa en segundo plano; el progreso se actualiza automáticamente.")
    _render_agent_status()


def _status_label(status: str) -> str:
    icons = {
        "pendiente": "Pendiente",
        "trabajando": "Trabajando",
        "éxito": "Éxito",
        "falló": "Falló",
        "truncado": "Truncado",
    }
    return icons.get(status, "Pendiente")


def _render_summary(results: dict[int, AgentResult]):
    rows = []
    for agent_id, (name, _) in AGENT_META.items():
        result = results.get(agent_id)
        rows.append(
            {
                "Agente": f"{agent_id}. {name}",
                "Resumen": result.resumen_3_lineas.replace("\n", " ") if result else "Sin resultado",
                "Confianza": result.nivel_confianza if result else "—",
                "Estado": (
                    "Falló" if result and result.error else
                    "Truncado" if result and result.aviso_corte else
                    "Éxito" if result else "Pendiente"
                ),
            }
        )
    st.dataframe(rows, hide_index=True)


def _render_agent_details(results: dict[int, AgentResult]):
    for agent_id, (name, question) in AGENT_META.items():
        result = results.get(agent_id)
        with st.expander(f"Agente {agent_id}: {name}", expanded=False):
            st.caption(question)
            if not result:
                st.info("Este agente todavía no tiene resultados en caché.")
                continue
            if result.error:
                st.error("SECCIÓN NO GENERADA")
                with st.expander("Ver detalle técnico"):
                    st.code(_safe_error_text(result.error), language="text")
                continue
            if result.aviso_corte:
                st.warning("RESPUESTA TRUNCADA")
            st.markdown(f"**Resumen:** {result.resumen_3_lineas}")
            st.markdown(result.contenido_completo)
            st.markdown(f"**Confianza:** {result.nivel_confianza}")
            if result.fuentes:
                st.markdown("**Fuentes**")
                for source in result.fuentes:
                    date_text = source.get("date") or "fecha no verificada"
                    st.markdown(
                        f"- [{source.get('title', 'Fuente')}]({source.get('url', '')}) "
                        f"— {date_text}"
                    )


def _render_hypothesis(results: dict[int, AgentResult]):
    result = results.get(7)
    if not result or result.error:
        st.info("La hipótesis estará disponible cuando termine el Agente 7.")
        return
    content = result.contenido_completo
    content = re.sub(
        r"(?i)(\bSupuesto a validar\b)",
        r"**🟨 \1**",
        content,
    )
    st.markdown(content)
    st.markdown("### Plan por semanas")
    report = st.session_state.get("study_report", "")
    match = re.search(
        r"## 🗓️ PLAN DE ACCIÓN OPERATIVO A 30 DÍAS.*?(?=\n## 📚 ANEXO:|\Z)",
        report,
        flags=re.DOTALL,
    )
    if match:
        st.markdown(match.group(0))
    else:
        st.info("El plan del informe todavía no está disponible.")


def _render_sources(results: dict[int, AgentResult]):
    used_by: dict[str, dict[str, Any]] = {}
    for agent_id, result in results.items():
        for source in result.fuentes:
            url = source.get("url", "").strip()
            if not url:
                continue
            entry = used_by.setdefault(
                url,
                {
                    "Título": source.get("title", "Fuente"),
                    "Enlace": url,
                    "Fecha": source.get("date") or "fecha no verificada",
                    "Agentes": [],
                },
            )
            if AGENT_META[agent_id][0] not in entry["Agentes"]:
                entry["Agentes"].append(AGENT_META[agent_id][0])
    if used_by:
        st.dataframe(
            [
                {**entry, "Agentes": ", ".join(entry["Agentes"])}
                for entry in used_by.values()
            ],
            hide_index=True,
            column_config={
                "Enlace": st.column_config.LinkColumn("Enlace", display_text="Abrir fuente")
            },
        )
    else:
        st.info("No hay fuentes guardadas para mostrar.")


def main():
    st.set_page_config(
        page_title="Estudio de mercado multiagente",
        page_icon=":material/insights:",
        layout="wide",
    )
    if not _auth_gate():
        st.stop()

    config_yaml = _load_saved_config()
    st.title("Estudio de mercado multiagente")
    st.caption("Análisis reutilizando el orquestador y los siete agentes del proyecto.")

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    search_name = "Tavily"
    password_configured = bool(_read_secret("APP_PASSWORD"))
    with st.sidebar:
        st.header("Configuración")
        with st.form("study_form"):
            industry = st.text_input("Industria / sector", value=config_yaml.get("industria", ""))
            business = st.text_area(
                "Descripción del negocio",
                value=config_yaml.get("descripcion_negocio", ""),
                height=130,
            )
            country = st.text_input("País / mercado", value=config_yaml.get("pais", ""))
            default_window = "6 meses"
            for label, config_value in WINDOW_OPTIONS.items():
                if config_yaml.get("ventana_analisis") == config_value:
                    default_window = label
            window_label = st.selectbox(
                "Ventana de análisis",
                list(WINDOW_OPTIONS),
                index=list(WINDOW_OPTIONS).index(default_window),
            )
            mode = st.selectbox(
                "Modo",
                [
                    "Simulación (sin gastar cuota)",
                    "Usar último informe guardado",
                    "Ejecución real",
                ],
                index=0,
            )
            selected_agent_label = st.selectbox(
                "Correr solo el agente N",
                ["Todos los agentes"] + [f"Agente {agent_id}" for agent_id in AGENT_META],
            )
            estimate = 1 if selected_agent_label != "Todos los agentes" else 7
            confirmation = False
            if mode == "Ejecución real":
                st.warning(f"Estimación mínima: {estimate} llamada(s) inicial(es) a Gemini. Puede requerir continuaciones o reintentos.")
                confirmation = st.checkbox(
                    f"Confirmo la ejecución y el consumo estimado de {estimate} llamada(s)."
                )
            execute = st.form_submit_button(
                "Ejecutar estudio",
                type="primary",
                icon=":material/play_arrow:",
                width="stretch",
            )
        st.divider()
        st.caption(f"Modelo: `{model_name}`")
        st.caption(f"Buscador: `{search_name}`")
        if mode == "Ejecución real" and not password_configured:
            st.warning("Para habilitar la ejecución real, configura APP_PASSWORD en st.secrets.")
        if execute:
            if not all((industry.strip(), business.strip(), country.strip())):
                st.error("Completa industria, descripción del negocio y país.")
            elif mode == "Ejecución real" and not password_configured:
                st.error("La ejecución real está bloqueada hasta configurar una contraseña de acceso.")
            elif mode == "Ejecución real" and not confirmation:
                st.error("Confirma el consumo estimado antes de iniciar.")
            elif mode == "Usar último informe guardado":
                if REPORT_PATH.exists():
                    st.session_state["study_report"] = REPORT_PATH.read_text(encoding="utf-8")
                    st.session_state["study_results"] = {
                        item.agente_id: item for item in _load_cached_results()
                    }
                    st.session_state["study_done"] = True
                    st.session_state["study_running"] = False
                    st.success("Se cargó el último informe guardado sin llamar a Gemini.")
                else:
                    st.error("Todavía no existe un informe guardado.")
            else:
                config = {
                    **config_yaml,
                    "industria": industry.strip(),
                    "descripcion_negocio": business.strip(),
                    "pais": country.strip(),
                    "ventana_analisis": WINDOW_OPTIONS[window_label],
                }
                selected_id = (
                    int(selected_agent_label.split()[-1])
                    if selected_agent_label != "Todos los agentes"
                    else None
                )
                seed_results = _load_cached_results(config)
                dependencies = (
                    range(1, selected_id) if selected_id and selected_id >= 5 else ()
                )
                for dependency_id in dependencies:
                    if not any(result.agente_id == dependency_id for result in seed_results):
                        name, question = AGENT_META[dependency_id]
                        seed_results.append(
                            AgentResult(
                                agente_id=dependency_id,
                                nombre=f"Agente {dependency_id} - {name}",
                                pregunta=question,
                                objetivo="Resultado no disponible en caché.",
                                error="Resultado previo no disponible en caché para esta configuración.",
                                contenido_completo="SECCIÓN NO GENERADA",
                            )
                        )
                credentials = {}
                for key in ("GEMINI_API_KEY", "TAVILY_API_KEY", "OPENAI_API_KEY"):
                    secret_value = _read_secret(key)
                    if secret_value:
                        credentials[key] = secret_value
                secrets_to_redact = list(credentials.values()) + [
                    os.getenv(key, "")
                    for key in ("GEMINI_API_KEY", "TAVILY_API_KEY", "OPENAI_API_KEY")
                ]
                _launch_study(
                    config=config,
                    mock_mode=mode == "Simulación (sin gastar cuota)",
                    only_agent=selected_id,
                    seed_results=seed_results,
                    credentials=credentials,
                    secret_values=secrets_to_redact,
                )

    if st.session_state.get("study_fatal"):
        st.error("No se pudo completar el estudio.")
        with st.expander("Ver detalle técnico"):
            st.code(st.session_state["study_fatal"], language="text")

    tabs = st.tabs(
        [
            "Progreso",
            "Resumen",
            "Agentes",
            "Hipótesis y plan 30 días",
            "Informe completo",
            "Fuentes",
        ]
    )
    with tabs[0]:
        _render_live_progress()
    results = st.session_state.get("study_results", {})
    report = st.session_state.get("study_report")
    with tabs[1]:
        _render_summary(results)
    with tabs[2]:
        _render_agent_details(results)
    with tabs[3]:
        _render_hypothesis(results)
    with tabs[4]:
        if report:
            st.markdown(report)
            st.download_button(
                "Descargar informe Markdown",
                data=report,
                file_name="informe_mercado.md",
                mime="text/markdown",
                icon=":material/download:",
            )
        else:
            st.info("Ejecuta un estudio o carga un informe guardado para verlo aquí.")
    with tabs[5]:
        _render_sources(results)


if __name__ == "__main__":
    main()
