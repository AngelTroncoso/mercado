"""
Agente 3 - Soluciones innovadoras
Pregunta: ¿Qué nuevos actores o productos están resolviendo estas necesidades de manera no obvia y qué hacen diferente?
Objetivo: Identificar soluciones innovadoras y efectivas.
Tareas: Detectar startups y productos emergentes (incluso de industrias vecinas), y explicar qué hacen distinto a los líderes tradicionales.
"""

import time
from typing import Dict, Any
from .base_agent import BaseAgent, AgentResult


class AgenteSolucionesInnovadoras(BaseAgent):
    def __init__(self):
        super().__init__(
            agente_id=3,
            nombre="Agente 3 - Soluciones Innovadoras",
            pregunta="¿Qué nuevos actores o productos están resolviendo estas necesidades de manera no obvia y qué hacen diferente?",
            objetivo="Identificar startups, actores no tradicionales y productos emergentes con enfoques disruptivos.",
            reglas_especificas="""
ENFOQUE ESPECÍFICO DE ESTE AGENTE:
- Identifica startups recientes (fundadas o con rondas en los últimos 2-3 años con tracción en los últimos 3-6 meses).
- Busca actores que NO sean los monopolios o líderes tradicionales conocidos de siempre.
- Considera innovaciones provenientes de industrias vecinas (cross-industry) que están entrando a este mercado.
- Para cada actor, detalla explícitamente:
  * Nombre y origen de la solución/startup.
  * Su 'secreto' o diferenciador no obvio (¿por qué funciona mejor, más rápido o más barato?).
  * Qué supuesto tradicional de la industria están desafiando.
            """,
        )

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        start_time = time.time()
        industria = context.get("industria", "")
        pais = context.get("pais", "")
        ventana = context.get("ventana_analisis", "últimos 3-6 meses")
        self.set_analysis_window(context)

        queries = [
            f"{industria} startups innovadoras nuevos actores {pais} 2024 2025",
            f"{industria} startups disruptivas nuevas soluciones alternativas financiamiento",
            f"{industria} top emerging competitors startups 'seed' 'series a' tech",
        ]

        search_results = await self.multi_search(queries, max_results_per_query=4)

        fuentes_formateadas = []
        for i, item in enumerate(search_results, 1):
            fuentes_formateadas.append(
                f"[{i}] Título: {item['title']}\n"
                f"    URL: {item['url']}\n"
                f"    Fecha/Origen: {item['date']} ({item['source']})\n"
                f"    Extracto: {item['content']}\n"
            )
        texto_fuentes = "\n".join(fuentes_formateadas) if fuentes_formateadas else "No se encontraron startups directas en la web."

        prompt_usuario = f"""
DATOS DE ENTRADA:
- Industria: {industria}
- Mercado objetivo: {pais}
- Mi negocio actual: {context.get('descripcion_negocio', '')}
- Ventana de análisis: {ventana}

EVIDENCIA DE NUEVAS STARTUPS Y PRODUCTOS:
{texto_fuentes}

INSTRUCCIÓN:
Detecta y analiza a los nuevos actores y productos que están resolviendo dolores de clientes de forma no convencional.
Responde rigurosamente a la pregunta:
"{self.pregunta}"

Estructura obligatoria:
1. Resumen Ejecutivo (exactamente 3 líneas sobre las innovaciones y nuevos entrantes)
2. Hallazgos Clave (máximo 5 soluciones/startups emergentes; para cada una destaca HECHO con enlace de la startup/noticia y fecha, e INTERPRETACIÓN de por qué su modelo es disruptivo vs incumbentes)
3. Nivel de Confianza (Alto/Medio/Bajo con justificación)
4. Qué dato falta para mejorar la respuesta (ej. métricas de retención privadas, volumen de facturación o tracción real de los nuevos competidores)
"""
        extra_ctx = self.format_extra_context(context)
        if extra_ctx:
            prompt_usuario += f"\nINFORMACIÓN ADICIONAL DEL USUARIO:\n{extra_ctx}\n"


        try:
            raw_output = await self.ask_llm(prompt_usuario, self.get_system_prompt())
            sanitized = self.sanitizar_contenido_agente(raw_output, search_results)
            parsed = self.parse_sections(sanitized)

            return AgentResult(
                agente_id=self.agente_id,
                nombre=self.nombre,
                pregunta=self.pregunta,
                objetivo=self.objetivo,
                resumen_3_lineas=parsed["resumen_3_lineas"],
                contenido_completo=sanitized,
                nivel_confianza=parsed["nivel_confianza"],
                fuentes=search_results,
                tiempo_ejecucion_segundos=round(time.time() - start_time, 2),
                aviso_corte="RESPUESTA TRUNCADA" if self.last_generation_truncated else None,
            )
        except Exception as e:
            return AgentResult(
                agente_id=self.agente_id,
                nombre=self.nombre,
                pregunta=self.pregunta,
                objetivo=self.objetivo,
                error=str(e),
                contenido_completo=f"Error durante la ejecución del {self.nombre}: {str(e)}",
                tiempo_ejecucion_segundos=round(time.time() - start_time, 2),
            )
