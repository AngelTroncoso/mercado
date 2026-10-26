"""
Agente 0 - Orquestador del Sistema Multiagente de Estudio de Mercado con IA.

Flujo de Ejecución:
1. Lee la configuración (config.yaml) y variables de entorno (.env).
2. FASE 1 (Paralelo): Ejecuta en paralelo los Agentes 1, 2, 3 y 4 (investigación externa).
3. FASE 2 (Análisis Interno): Ejecuta los Agentes 5 y 6 usando los resultados de 1-4.
4. FASE 3 (Síntesis Estratégica): Ejecuta el Agente 7 usando TODOS los resultados (1-6).
5. Compila y guarda el informe final en Markdown (informes/informe_mercado.md).
"""

import os
import sys
import re
import yaml
import asyncio
import argparse
import datetime
from typing import Dict, Any, List, Optional, Callable
from dotenv import load_dotenv

# Asegurar UTF-8 en consolas Windows (cp1252) para evitar UnicodeEncodeError
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Verificación temprana de dependencias para guiar al usuario
try:
    import yaml
    from dotenv import load_dotenv
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.markdown import Markdown
    HAS_RICH = True
except ImportError as err:
    print("\n" + "=" * 65)
    print("❌ AVISO: Faltan dependencias de Python requeridas.")
    print(f"   Detalle del módulo faltante: {err}")
    print("=" * 65)
    print("Para instalarlas rápidamente, ejecuta en tu terminal:")
    print("   pip install -r requirements.txt")
    print("=" * 65 + "\n")
    sys.exit(1)

# Importar agentes especialistas
from agentes.base_agent import AgentResult
from agentes.agente_01_industria import AgenteIndustria
from agentes.agente_02_cliente import AgenteVozCliente
from agentes.agente_03_soluciones import AgenteSolucionesInnovadoras
from agentes.agente_04_formatos import AgenteFormatosValor
from agentes.agente_05_riesgos import AgenteRiesgosBrechas
from agentes.agente_06_obsoleto import AgenteIdeasObsoletas
from agentes.agente_07_hipotesis import AgenteHipotesisEstrategica

load_dotenv()
console = Console(force_terminal=True, legacy_windows=False)




def cargar_configuracion(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Carga y valida el archivo de configuración YAML."""
    if not os.path.exists(config_path):
        console.print(f"[bold red]❌ Error:[/bold red] No se encontró el archivo de configuración '{config_path}'.")
        console.print("[yellow]💡 Sugerencia:[/yellow] Copia el archivo 'config.yaml' de ejemplo y adáptalo a tu negocio.")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        try:
            config = yaml.safe_load(f)
        except Exception as e:
            console.print(f"[bold red]❌ Error al parsear YAML:[/bold red] {e}")
            sys.exit(1)

    # Validar campos obligatorios
    campos_requeridos = ["industria", "descripcion_negocio", "pais"]
    for campo in campos_requeridos:
        if not config.get(campo):
            console.print(f"[bold red]❌ Configuración incompleta:[/bold red] Falta el campo requerido '{campo}' en {config_path}.")
            sys.exit(1)

    if "ventana_analisis" not in config:
        config["ventana_analisis"] = "últimos 3-6 meses"

    return config


def generar_mock_result(agente_id: int, nombre: str, pregunta: str, objetivo: str, config: Dict[str, Any] = None) -> AgentResult:
    """Genera datos de prueba realistas para modo mock o demostración rápida basados en config.yaml."""
    cfg = config or {}
    industria = cfg.get("industria", "Tecnología e Inteligencia Artificial")
    pais = cfg.get("pais", "Latinoamérica")
    negocio = cfg.get("descripcion_negocio", "Servicios de software e IA")

    return AgentResult(
        agente_id=agente_id,
        nombre=nombre,
        pregunta=pregunta,
        objetivo=objetivo,
        resumen_3_lineas=(
            f"Simulación para el sector {industria} ({pais}), sin fuentes verificadas.\n"
            "Los resultados de esta ejecución de prueba no describen tendencias reales.\n"
            "Valida cualquier oportunidad con evidencia actual antes de tomar decisiones."
        ),
        contenido_completo=f"""#### Resumen Ejecutivo
Simulación del análisis para el sector {industria} en {pais}.
Los hallazgos de este modo son datos sintéticos y no representan investigación ni evidencia real.
Valida cualquier decisión con fuentes actuales antes de actuar.

#### Hallazgos Clave
- *Interpretación*: Este resultado simulado no contiene hechos ni citas verificadas.
- **Supuesto a validar**: Los posibles resultados y métricas del ejemplo son únicamente demostrativos.

#### Nivel de Confianza
- **Nivel**: Bajo
- **Justificación**: Modo de prueba sin búsquedas web ni análisis del modelo.

#### Información Faltante para Optimizar la Respuesta
Ejecuta el análisis en vivo para recopilar fuentes verificables.
""",
        nivel_confianza="Bajo",
        por_que_confianza="Datos sintéticos generados en modo de prueba controlada.",
        dato_faltante="Métricas internas de retención y telemetría de clientes.",
        tiempo_ejecucion_segundos=0.15,
    )


class OrquestadorMercado:
    """Agente 0: Coordina y ejecuta las tres fases del estudio de mercado."""

    def __init__(
        self,
        config: Dict[str, Any],
        output_path: str = "informes/informe_mercado.md",
        mock_mode: bool = False,
        only_agent: Optional[int] = None,
        previous_results: Optional[List[AgentResult]] = None,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.config = config
        self.output_path = output_path
        self.mock_mode = mock_mode
        self.agent_semaphore = asyncio.Semaphore(2)
        self.only_agent = only_agent
        self.on_event = on_event

        # Instanciar especialistas
        self.agente_1 = AgenteIndustria()
        self.agente_2 = AgenteVozCliente()
        self.agente_3 = AgenteSolucionesInnovadoras()
        self.agente_4 = AgenteFormatosValor()
        self.agente_5 = AgenteRiesgosBrechas()
        self.agente_6 = AgenteIdeasObsoletas()
        self.agente_7 = AgenteHipotesisEstrategica()

        self.resultados: List[AgentResult] = list(previous_results or [])
        self._agentes = {
            1: self.agente_1, 2: self.agente_2, 3: self.agente_3, 4: self.agente_4,
            5: self.agente_5, 6: self.agente_6, 7: self.agente_7,
        }
        for agent in self._agentes.values():
            agent.wait_callback = self._publish_wait

    def _publish_event(self, event: Dict[str, Any]):
        if self.on_event:
            self.on_event(event)

    def _publish_wait(self, seconds: float, reason: str):
        self._publish_event({"type": "wait", "seconds": seconds, "reason": reason})

    def _record_result(self, result: AgentResult):
        existing_index = next(
            (index for index, item in enumerate(self.resultados) if item.agente_id == result.agente_id),
            None,
        )
        if existing_index is None:
            self.resultados.append(result)
        else:
            self.resultados[existing_index] = result
        self._publish_event({"type": "result", "result": result})

    def _record_status(self, agent_id: int, status: str):
        agent = self._agentes[agent_id]
        self._publish_event({
            "type": "status",
            "agent_id": agent_id,
            "status": status,
            "name": agent.nombre,
            "question": agent.pregunta,
        })

    async def _run_single_agent(self, agent_id: int):
        agent = self._agentes[agent_id]
        self._record_status(agent_id, "trabajando")
        try:
            if self.mock_mode:
                result = generar_mock_result(
                    agent_id, agent.nombre, agent.pregunta, agent.objetivo, self.config
                )
            elif agent_id in (5, 6, 7):
                result = await agent.run(self.config, previous_results=self.resultados)
            else:
                result = await agent.run(self.config)
        except Exception as error:
            result = AgentResult(
                agente_id=agent.agente_id,
                nombre=agent.nombre,
                pregunta=agent.pregunta,
                objetivo=agent.objetivo,
                error=str(error),
                contenido_completo="SECCIÓN NO GENERADA",
            )
        self._record_result(result)
        self._record_status(
            agent_id,
            "falló" if result.error else "truncado" if result.aviso_corte else "éxito",
        )
        if agent_id == 7:
            min_confidence = min(
                ({"Bajo": 1, "Medio": 2, "Alto": 3}.get(item.nivel_confianza, 1)
                 if not item.error and not item.aviso_corte else 1)
                for item in self.resultados
                if item.agente_id in (1, 2, 3, 4)
            ) if any(item.agente_id in (1, 2, 3, 4) for item in self.resultados) else 1
            if {"Bajo": 1, "Medio": 2, "Alto": 3}.get(result.nivel_confianza, 2) > min_confidence:
                result.nivel_confianza = {1: "Bajo", 2: "Medio", 3: "Alto"}[min_confidence]
                result.contenido_completo = re.sub(
                    r'(-\s*\*\*Nivel\*\*:\s*)(Alto|Medio)',
                    rf'\g<1>{result.nivel_confianza} *(acotado a la investigación disponible)*',
                    result.contenido_completo,
                    flags=re.IGNORECASE,
                )
                self._record_result(result)
        self.guardar_informe(self.compilar_informe_markdown())
        self.mostrar_resumen_terminal()

    def mostrar_bienvenida(self):
        """Imprime el banner y la ficha técnica del estudio."""
        console.print(
            Panel.fit(
                "[bold cyan]SISTEMA MULTIAGENTE DE ESTUDIO DE MERCADO CON IA[/bold cyan]\n"
                "[italic white]1 Orquestador + 7 Especialistas Autónomos[/italic white]\n"
                f"[dim]Proveedor LLM: {os.getenv('LLM_PROVIDER', 'gemini').upper()} | Motor Búsqueda: {os.getenv('SEARCH_PROVIDER', 'tavily').upper()}[/dim]",
                border_style="cyan",
            )
        )

        tabla_info = Table(show_header=False, box=None)
        tabla_info.add_column("Campo", style="bold yellow")
        tabla_info.add_column("Valor", style="white")

        tabla_info.add_row("🏢 Industria / Sector:", self.config["industria"])
        tabla_info.add_row("💼 Negocio Actual:", self.config["descripcion_negocio"].strip())
        tabla_info.add_row("🌍 Mercado / País:", self.config["pais"])
        tabla_info.add_row("⏱️ Ventana Temporal:", self.config["ventana_analisis"])
        if self.mock_mode:
            tabla_info.add_row("⚠️ Modo:", "[bold magenta]MOCK (Simulación de prueba)[/bold magenta]")

        console.print(Panel(tabla_info, title="[bold green]Ficha Técnica del Análisis[/bold green]", border_style="green"))

    async def ejecutar_fase_1(self) -> List[AgentResult]:
        """FASE 1: Ejecuta agentes 1, 2, 3 y 4 en paralelo."""
        console.print("\n[bold blue]━━━ FASE 1: Investigación del Mercado Exterior (En Paralelo) ━━━[/bold blue]")
        console.print("[dim]Consultando fuentes web, noticias, foros, startups y modelos comerciales...[/dim]")

        if self.mock_mode:
            await asyncio.sleep(0.5)
            r1 = generar_mock_result(1, self.agente_1.nombre, self.agente_1.pregunta, self.agente_1.objetivo, self.config)
            r2 = generar_mock_result(2, self.agente_2.nombre, self.agente_2.pregunta, self.agente_2.objetivo, self.config)
            r3 = generar_mock_result(3, self.agente_3.nombre, self.agente_3.pregunta, self.agente_3.objetivo, self.config)
            r4 = generar_mock_result(4, self.agente_4.nombre, self.agente_4.pregunta, self.agente_4.objetivo, self.config)
            for result in (r1, r2, r3, r4):
                self._record_result(result)
                self._record_status(result.agente_id, "éxito")
            return [r1, r2, r3, r4]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            t1 = progress.add_task("[cyan]Agente 1: Cambios de la Industria...", total=None)
            t2 = progress.add_task("[magenta]Agente 2: Voz del Cliente...", total=None)
            t3 = progress.add_task("[yellow]Agente 3: Soluciones Innovadoras...", total=None)
            t4 = progress.add_task("[green]Agente 4: Formatos y Propuestas...", total=None)

            async def _run_with_task(agente, task_id):
                self._record_status(agente.agente_id, "trabajando")
                try:
                    async with self.agent_semaphore:
                        res = await agente.run(self.config)
                except Exception as e:
                    res = AgentResult(
                        agente_id=agente.agente_id,
                        nombre=agente.nombre,
                        pregunta=agente.pregunta,
                        objetivo=agente.objetivo,
                        error=str(e),
                        contenido_completo=f"Error durante la ejecución del {agente.nombre}: {str(e)}",
                    )
                if res.error:
                    progress.update(task_id, completed=100, description=f"[bold red]✖ {agente.nombre} FALLÓ[/bold red]")
                    console.print(f"[bold red]❌ {agente.nombre}: la sección no se generó.[/bold red]")
                else:
                    progress.update(task_id, completed=100, description=f"[bold green]✔ {agente.nombre} completado[/bold green]")
                self._record_result(res)
                self._record_status(
                    agente.agente_id,
                    "falló" if res.error else "truncado" if res.aviso_corte else "éxito",
                )
                return res

            tasks = [
                _run_with_task(self.agente_1, t1),
                _run_with_task(self.agente_2, t2),
                _run_with_task(self.agente_3, t3),
                _run_with_task(self.agente_4, t4),
            ]

            resultados_fase1 = await asyncio.gather(*tasks)

        return list(resultados_fase1)

    async def ejecutar_fase_2(self, resultados_fase1: List[AgentResult]) -> List[AgentResult]:
        """FASE 2: Ejecuta agentes 5 y 6 usando los resultados de 1-4."""
        console.print("\n[bold blue]━━━ FASE 2: Diagnóstico Interno del Negocio Propio ━━━[/bold blue]")
        console.print("[dim]Contrastando el negocio propio contra la evidencia externa recopilada...[/dim]")

        if self.mock_mode:
            await asyncio.sleep(0.5)
            r5 = generar_mock_result(5, self.agente_5.nombre, self.agente_5.pregunta, self.agente_5.objetivo, self.config)
            r6 = generar_mock_result(6, self.agente_6.nombre, self.agente_6.pregunta, self.agente_6.objetivo, self.config)
            for result in (r5, r6):
                self._record_result(result)
                self._record_status(result.agente_id, "éxito")
            return [r5, r6]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            t5 = progress.add_task("[red]Agente 5: Riesgos y Brechas Propias...", total=None)
            t6 = progress.add_task("[orange3]Agente 6: Ideas Obsoletas...", total=None)

            async def _run_5():
                self._record_status(5, "trabajando")
                try:
                    async with self.agent_semaphore:
                        res = await self.agente_5.run(self.config, previous_results=resultados_fase1)
                except Exception as e:
                    res = AgentResult(
                        agente_id=self.agente_5.agente_id,
                        nombre=self.agente_5.nombre,
                        pregunta=self.agente_5.pregunta,
                        objetivo=self.agente_5.objetivo,
                        error=str(e),
                        contenido_completo=f"Error durante la ejecución del {self.agente_5.nombre}: {str(e)}",
                    )
                if res.error:
                    progress.update(t5, completed=100, description=f"[bold red]✖ {self.agente_5.nombre} FALLÓ[/bold red]")
                    console.print(f"[bold red]❌ {self.agente_5.nombre}: la sección no se generó.[/bold red]")
                else:
                    progress.update(t5, completed=100, description=f"[bold green]✔ {self.agente_5.nombre} completado[/bold green]")
                self._record_result(res)
                self._record_status(5, "falló" if res.error else "truncado" if res.aviso_corte else "éxito")
                return res

            async def _run_6():
                self._record_status(6, "trabajando")
                try:
                    async with self.agent_semaphore:
                        res = await self.agente_6.run(self.config, previous_results=resultados_fase1)
                except Exception as e:
                    res = AgentResult(
                        agente_id=self.agente_6.agente_id,
                        nombre=self.agente_6.nombre,
                        pregunta=self.agente_6.pregunta,
                        objetivo=self.agente_6.objetivo,
                        error=str(e),
                        contenido_completo=f"Error durante la ejecución del {self.agente_6.nombre}: {str(e)}",
                    )
                if res.error:
                    progress.update(t6, completed=100, description=f"[bold red]✖ {self.agente_6.nombre} FALLÓ[/bold red]")
                    console.print(f"[bold red]❌ {self.agente_6.nombre}: la sección no se generó.[/bold red]")
                else:
                    progress.update(t6, completed=100, description=f"[bold green]✔ {self.agente_6.nombre} completado[/bold green]")
                self._record_result(res)
                self._record_status(6, "falló" if res.error else "truncado" if res.aviso_corte else "éxito")
                return res

            resultados_fase2 = await asyncio.gather(_run_5(), _run_6())

        return list(resultados_fase2)

    async def ejecutar_fase_3(self, todos_los_previos: List[AgentResult]) -> AgentResult:
        """FASE 3: Ejecuta agente 7 usando TODOS los resultados (1-6)."""
        console.print("\n[bold blue]━━━ FASE 3: Definición de Hipótesis Estratégica ━━━[/bold blue]")
        console.print("[dim]Sintetizando todas las señales en 1 hipótesis directriz + plan a 30 días...[/dim]")

        if self.mock_mode:
            await asyncio.sleep(0.5)
            result = generar_mock_result(7, self.agente_7.nombre, self.agente_7.pregunta, self.agente_7.objetivo, self.config)
            self._record_result(result)
            self._record_status(7, "éxito")
            return result

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            t7 = progress.add_task("[bold gold1]Agente 7: Hipótesis Estratégica y Plan de Acción...", total=None)
            self._record_status(7, "trabajando")
            try:
                async with self.agent_semaphore:
                    resultado_fase3 = await self.agente_7.run(self.config, previous_results=todos_los_previos)
            except Exception as e:
                resultado_fase3 = AgentResult(
                    agente_id=self.agente_7.agente_id,
                    nombre=self.agente_7.nombre,
                    pregunta=self.agente_7.pregunta,
                    objetivo=self.agente_7.objetivo,
                    error=str(e),
                    contenido_completo=f"Error durante la ejecución del {self.agente_7.nombre}: {str(e)}",
                )
            if resultado_fase3.error:
                progress.update(t7, completed=100, description=f"[bold red]✖ {self.agente_7.nombre} FALLÓ[/bold red]")
                console.print(f"[bold red]❌ {self.agente_7.nombre}: la sección no se generó.[/bold red]")
            else:
                progress.update(t7, completed=100, description=f"[bold green]✔ {self.agente_7.nombre} completado[/bold green]")
            self._record_result(resultado_fase3)
            self._record_status(
                7,
                "falló" if resultado_fase3.error else "truncado" if resultado_fase3.aviso_corte else "éxito",
            )

        return resultado_fase3

    def compilar_informe_markdown(self) -> str:
        """Genera el contenido integral del informe en formato Markdown."""
        now = datetime.datetime.now()
        meses_es = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ]
        mes_es = meses_es[now.month - 1]
        fecha_actual = f"{now.day} de {mes_es} de {now.year}, {now.strftime('%H:%M')}"
        llm_usado = os.getenv(
            "GEMINI_MODEL" if os.getenv("LLM_PROVIDER", "gemini").lower() == "gemini" else "OPENAI_MODEL",
            "gemini-3.5-flash",
        )

        def fecha_espanol(fecha: str) -> str:
            if not fecha or fecha == "fecha no verificada":
                return "fecha no verificada"
            try:
                fecha_real = datetime.date.fromisoformat(str(fecha)[:10])
            except ValueError:
                return "fecha no verificada"
            return (
                f"{fecha_real.day} de {meses_es[fecha_real.month - 1]} "
                f"de {fecha_real.year}"
            )

        # Diccionario rápido de resultados por id
        mapa_res = {r.agente_id: r for r in self.resultados}

        # Extraer resúmenes
        resumenes_tabla = []
        for i in range(1, 8):
            ag = mapa_res.get(i)
            if ag:
                if ag.error:
                    resumenes_tabla.append(f"| **Agente {i}** | {ag.nombre.split('-')[-1].strip()} | ❌ **SECCIÓN NO GENERADA**: error de ejecución | `FALLIDO` |")
                else:
                    res_linea_corta = ag.resumen_3_lineas.replace("\n", "<br>")
                    estado = "TRUNCADA" if ag.aviso_corte else ag.nivel_confianza
                    resumenes_tabla.append(f"| **Agente {i}** | {ag.nombre.split('-')[-1].strip()} | {res_linea_corta} | `{estado}` |")

        encabezado_tabla = (
            "| Agente | Enfoque | Resumen Ejecutivo (3 Líneas) | Confianza |\n"
            "| :---: | :--- | :--- | :---: |\n"
        )
        cuerpo_resumenes = "\n".join(resumenes_tabla)

        def render_seccion(agente_id: int) -> str:
            ag = mapa_res.get(agente_id)
            if not ag:
                return "> ⚠️ **SECCIÓN NO GENERADA**\n\nNo se recibieron datos para este agente."
            if ag.error:
                return f"""> [!WARNING]
> ### ⚠️ SECCIÓN NO GENERADA
> Este agente agotó los reintentos o encontró un error durante su ejecución.

Consulta el resumen de ejecución de la terminal para conocer el estado del agente."""

            contenido = ag.contenido_completo.strip()
            # Limpiar posibles títulos duplicados al inicio que repitan el encabezado del informe
            lines = contenido.splitlines()
            while lines:
                primera = lines[0].strip()
                if not primera:
                    lines.pop(0)
                    continue
                if primera.startswith("#"):
                    p_lower = primera.lower()
                    if any(k in p_lower for k in [
                        "agente", "cambios", "voz del", "soluciones", "formatos",
                        "riesgos", "ideas", "hipótesis", "hipotesis", "industria", "cliente"
                    ]) and not any(sub in p_lower for sub in ["resumen", "hallazgo", "confianza", "dato", "información", "informacion"]):
                        lines.pop(0)
                        continue
                break
            contenido = "\n".join(lines).strip()
            if ag.aviso_corte:
                contenido = (
                    "> ⚠️ **RESPUESTA TRUNCADA**: La sección no pudo completarse tras solicitar continuaciones.\n\n"
                    + contenido
                )
            return contenido

        # Compilar todas las fuentes encontradas
        todas_las_fuentes = []
        seen_urls = set()
        for r in self.resultados:
            for f in r.fuentes:
                url = f.get("url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    fecha = fecha_espanol(f.get("date", "fecha no verificada"))
                    todas_las_fuentes.append(f"- [{f.get('title', 'Fuente')}]({url}) — *{fecha}* (Vía {f.get('source', 'Web')})")

        anexo_fuentes = "\n".join(todas_las_fuentes) if todas_las_fuentes else "- Fuentes citadas directamente en el cuerpo de cada agente."

        contenido_md = f"""# INFORME ESTRATÉGICO DE ESTUDIO DE MERCADO CON IA
*Generado de forma autónoma por el Sistema Multiagente de Inteligencia Competitiva*

---

## 📋 FICHA TÉCNICA DEL ESTUDIO

| Parámetro | Detalle |
| :--- | :--- |
| **Industria / Sector** | {self.config.get('industria')} |
| **Negocio / Producto Actual** | {self.config.get('descripcion_negocio')} |
| **Mercado Objetivo** | {self.config.get('pais')} |
| **Ventana Temporal** | {self.config.get('ventana_analisis')} |
| **Fecha de Emisión** | {fecha_actual} |
| **Motor de Inteligencia** | {llm_usado} |
| **Arquitectura** | 1 Agente Orquestador + 7 Agentes Especialistas |

---

## 🎯 RESUMEN EJECUTIVO TRANSVERSAL (MATRIZ 360°)

El presente estudio integra la investigación de mercado exterior (Agentes 1 a 4), la auditoría diagnóstica del negocio propio (Agentes 5 y 6) y la síntesis de hipótesis estratégica de alto impacto (Agente 7).

{encabezado_tabla}{cuerpo_resumenes}

---

## 📊 INVESTIGACIÓN EXTERNA: PANORAMA DEL MERCADO

### 1. Cambios de la Industria
> **Pregunta**: *{self.agente_1.pregunta}*  
> **Objetivo**: *{self.agente_1.objetivo}*

{render_seccion(1)}

---

### 2. Voz del Cliente y Frustraciones Emergentes
> **Pregunta**: *{self.agente_2.pregunta}*  
> **Objetivo**: *{self.agente_2.objetivo}*

{render_seccion(2)}

---

### 3. Soluciones Innovadoras y Nuevos Actores
> **Pregunta**: *{self.agente_3.pregunta}*  
> **Objetivo**: *{self.agente_3.objetivo}*

{render_seccion(3)}

---

### 4. Formatos de Producto y Propuestas de Valor con Tracción
> **Pregunta**: *{self.agente_4.pregunta}*  
> **Objetivo**: *{self.agente_4.objetivo}*

{render_seccion(4)}

---

## 🔍 DIAGNÓSTICO INTERNO: AUDITORÍA DE MI NEGOCIO

### 5. Riesgos y Brechas Propias
> **Pregunta**: *{self.agente_5.pregunta}*  
> **Objetivo**: *{self.agente_5.objetivo}*

{render_seccion(5)}

---

### 6. Ideas y Prácticas Obsoletas (Limpieza Estratégica)
> **Pregunta**: *{self.agente_6.pregunta}*  
> **Objetivo**: *{self.agente_6.objetivo}*

{render_seccion(6)}

---

## 🚀 DIRECCIÓN ESTRATÉGICA Y ACCIÓN

### 7. Hipótesis Estratégica de Alto Impacto
> **Pregunta**: *{self.agente_7.pregunta}*  
> **Objetivo**: *{self.agente_7.objetivo}*

{render_seccion(7)}

---

## 🗓️ PLAN DE ACCIÓN OPERATIVO A 30 DÍAS

Para validar la estrategia en el sector de **{self.config.get('industria')}**, se recomienda la siguiente secuencia de ejecución ágil de 4 semanas:

```text
  SEMANA 1                 SEMANA 2                 SEMANA 3                 SEMANA 4
[Diagnóstico y Setup] → [Validación Oferta] → [Piloto en Vivo]     → [Métricas y Decisión]
- Auditoría de datos     - Prototipo "Smoke Test"- Supuesto a validar: piloto con 5-10 usuarios beta  - Medición de KPIs
- Definición de copy     - Landing page / DM      usuarios beta           - Decisión GO / NO-GO
- Selección de cohorte   - Oferta irresistible   - Recolección feedback  - Ajuste de roadmap
```

### Semana 1 (Días 1 a 7): Diagnóstico, Segmentación y Narrativa
- [ ] Eliminar o despriorizar las iniciativas clasificadas como `[ELIMINAR]` por el Agente 6.
- [ ] Entrevistar a clientes o prospectos clave para contrastar las quejas detectadas por el Agente 2.
- [ ] Rediseñar la propuesta de valor eliminando términos genéricos y enfocándose en la resolución directa del dolor detectado.

### Semana 2 (Días 8 a 14): Smoke Test y Validación de Intención de Compra
- [ ] Construir una landing page o presentación de 1 página con la nueva hipótesis de valor (Agente 7).
- [ ] **Supuesto a validar**: Enviar una campaña a 30-50 prospectos calificados o publicar en comunidades del sector.
- [ ] **Supuesto a validar**: Umbral orientativo de 15-20% de clics en "Quiero unirme al piloto" o reservas de llamada.

### Semana 3 (Días 15 a 21): Prueba de Concepto (PoC) "Concierge" / Piloto
- [ ] **Supuesto a validar**: Operar manualmente o semi-automatizada la solución para 5-10 clientes piloto.
- [ ] Comprobar si el modelo de monetización (Agente 4) es aceptado sin fricción.
- [ ] Monitorear tiempo de valor entregado (Time to Value) en los primeros días.

### Semana 4 (Días 22 a 30): Evaluación Cuantitativa y Decisión Estratégica
- [ ] Evaluar métricas de éxito definidas por el Agente 7 vs resultados del piloto.
- [ ] Decisión ejecutiva:
  - **GO**: Escalar la nueva propuesta, actualizar pricing e integrar en el producto central.
  - **PIVOTE**: Si falla la métrica, activar de inmediato la **Hipótesis Alternativa 1**.

---

## 📚 ANEXO: DIRECTORIO DE FUENTES Y REFERENCIAS CONSULTADAS

{anexo_fuentes}

---
*Informe generado con el Sistema Multiagente de Estudio de Mercado.*
"""
        # Sanitización final de etiquetas requerida por el usuario
        contenido_md = re.sub(r'\[\s*HECHO\s+CONTRASTADO\s*\]', '[HECHO]', contenido_md, flags=re.IGNORECASE)
        contenido_md = re.sub(r'\*\*\s*\[\s*HECHO\s+CONTRASTADO\s*\]\s*\*\*', '**[HECHO]**', contenido_md, flags=re.IGNORECASE)
        contenido_md = re.sub(r'\bHECHO\s+CONTRASTADO\b', '[HECHO]', contenido_md)
        contenido_md = re.sub(r'\bReciente\b', 'fecha no verificada', contenido_md, flags=re.IGNORECASE)

        def convertir_fecha_iso(match):
            return fecha_espanol(match.group(0))

        contenido_md = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', convertir_fecha_iso, contenido_md)

        return contenido_md

    def guardar_informe(self, contenido: str):
        """Escribe el informe final en disco."""
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(contenido)
        console.print(f"\n[bold green]Informe final generado:[/bold green] [underline cyan]{self.output_path}[/underline cyan]")

    def mostrar_resumen_terminal(self):
        """Imprime una tabla de rendimiento y estado final de los agentes en consola."""
        tabla = Table(title="📊 Resumen de Ejecución del Sistema Multiagente", border_style="cyan")
        tabla.add_column("ID", justify="center", style="bold yellow")
        tabla.add_column("Agente Especialista", style="white")
        tabla.add_column("Confianza", justify="center")
        tabla.add_column("Fuentes", justify="center", style="dim")
        tabla.add_column("Tiempo", justify="right", style="green")
        tabla.add_column("Estado", justify="center")

        tiempo_total = 0.0
        for r in self.resultados:
            tiempo_total += r.tiempo_ejecucion_segundos
            estado = (
                "[bold red]Fallido[/bold red]" if r.error
                else "[bold yellow]Truncado[/bold yellow]" if r.aviso_corte
                else "[bold green]Generado[/bold green]"
            )
            conf_color = "green" if r.nivel_confianza == "Alto" else ("yellow" if r.nivel_confianza == "Medio" else "red")
            tabla.add_row(
                str(r.agente_id),
                r.nombre,
                f"[{conf_color}]{r.nivel_confianza}[/{conf_color}]",
                str(len(r.fuentes)),
                f"{r.tiempo_ejecucion_segundos:.2f}s",
                estado,
            )

        console.print("\n")
        console.print(tabla)
        console.print(f"[bold cyan]Tiempo total acumulado de procesamiento:[/bold cyan] {tiempo_total:.2f} segundos.")

        errores = [r for r in self.resultados if r.error]
        truncados = [r for r in self.resultados if r.aviso_corte and not r.error]
        if errores:
            console.print("\n[bold red]⚠️ DETALLE DE ERRORES OCURRIDOS:[/bold red]")
            for r in errores:
                console.print(f" • [bold yellow]{r.nombre}[/bold yellow]: sección no generada.")
        if truncados:
            console.print("\n[bold yellow]⚠️ SECCIONES TRUNCADAS:[/bold yellow]")
            for r in truncados:
                console.print(f" • [bold yellow]{r.nombre}[/bold yellow]: no pudo completarse.")
        if errores or truncados:
            console.print(
                f"[bold yellow]Resumen honesto:[/bold yellow] {len(errores)} agente(s) fallido(s), "
                f"{len(truncados)} sección(es) truncada(s). El informe contiene las advertencias correspondientes.\n"
            )
        else:
            console.print("[bold green]Resumen honesto:[/bold green] no hubo agentes fallidos ni secciones truncadas.")

    async def iniciar(self):
        """Punto de orquestación central."""
        self.mostrar_bienvenida()
        if self.only_agent is not None:
            await self._run_single_agent(self.only_agent)
            return

        # FASE 1
        self._publish_event({"type": "phase", "phase": 1})
        res_fase1 = await self.ejecutar_fase_1()

        # Regla de calidad 4: Para los agentes 5, 6 y 7, la confianza no puede ser mayor que la más baja de los agentes 1 a 4
        conf_map = {"Bajo": 1, "Medio": 2, "Alto": 3}
        inv_conf_map = {1: "Bajo", 2: "Medio", 3: "Alto"}

        min_conf_val = min(
            conf_map.get(r.nivel_confianza, 1)
            if not r.error and not r.aviso_corte
            else 1
            for r in res_fase1
        ) if res_fase1 else 1
        max_conf_permitida = inv_conf_map[min_conf_val]

        def _acotar_confianza(res: AgentResult):
            if res.error:
                return
            conf_val_agente = conf_map.get(res.nivel_confianza, 2)
            if conf_val_agente > min_conf_val:
                res.nivel_confianza = max_conf_permitida
                # Ajustar en el contenido Markdown del agente si reportó un nivel superior
                res.contenido_completo = re.sub(
                    r'(-\s*\*\*Nivel\*\*:\s*)(Alto|Medio)',
                    rf'\g<1>{max_conf_permitida} *(acotado al nivel de confianza de la investigación externa: {max_conf_permitida})*',
                    res.contenido_completo,
                    flags=re.IGNORECASE
                )

        # FASE 2
        self._publish_event({"type": "phase", "phase": 2})
        res_fase2 = await self.ejecutar_fase_2(res_fase1)
        for r in res_fase2:
            _acotar_confianza(r)
            self._record_result(r)

        # FASE 3
        self._publish_event({"type": "phase", "phase": 3})
        res_fase3 = await self.ejecutar_fase_3(self.resultados)
        _acotar_confianza(res_fase3)
        self._record_result(res_fase3)

        # Compilar informe
        informe_md = self.compilar_informe_markdown()
        self.guardar_informe(informe_md)

        # Mostrar tabla final
        self.mostrar_resumen_terminal()


def main():
    parser = argparse.ArgumentParser(description="Sistema Multiagente de Estudio de Mercado con IA")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Ruta al archivo de configuración (default: config.yaml)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="informes/informe_mercado.md",
        help="Ruta de salida para el informe en Markdown (default: informes/informe_mercado.md)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Ejecuta en modo simulación (mock) para probar el flujo sin consumir APIs externas",
    )

    args = parser.parse_args()

    # Cargar configuración
    config = cargar_configuracion(args.config)

    # Iniciar orquestador
    orquestador = OrquestadorMercado(
        config=config,
        output_path=args.output,
        mock_mode=args.mock,
    )

    asyncio.run(orquestador.iniciar())


def ejecutar_estudio(
    config: Dict[str, Any],
    mock_mode: bool = False,
    output_path: str = "informes/informe_mercado.md",
    only_agent: Optional[int] = None,
    previous_results: Optional[List[AgentResult]] = None,
    on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> tuple[List[AgentResult], str]:
    """Ejecuta el flujo reutilizable desde una interfaz o integración Python."""
    orquestador = OrquestadorMercado(
        config=config,
        output_path=output_path,
        mock_mode=mock_mode,
        only_agent=only_agent,
        previous_results=previous_results,
        on_event=on_event,
    )
    asyncio.run(orquestador.iniciar())
    with open(output_path, "r", encoding="utf-8") as report_file:
        report = report_file.read()
    return orquestador.resultados, report


if __name__ == "__main__":
    main()
