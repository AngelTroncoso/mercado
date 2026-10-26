"""
Agente 1 - Cambios de la industria
Pregunta: ¿Cuáles son los cambios más significativos en mi industria en los últimos 3-6 meses?
Objetivo: Actualizar la visión del mercado con datos actuales.
Tareas: Buscar noticias, regulaciones, reportes, lanzamientos, inversiones y cambios tecnológicos recientes. Priorizar fuentes con fecha.
"""

import time
from typing import Dict, Any
from .base_agent import BaseAgent, AgentResult


class AgenteIndustria(BaseAgent):
    def __init__(self):
        super().__init__(
            agente_id=1,
            nombre="Agente 1 - Cambios de la Industria",
            pregunta="¿Cuáles son los cambios más significativos en mi industria en los últimos 3-6 meses?",
            objetivo="Actualizar la visión del mercado con datos actuales, noticias, regulaciones, inversiones y saltos tecnológicos.",
            reglas_especificas="""
ENFOQUE ESPECÍFICO DE ESTE AGENTE:
- Identifica cambios macro y micro ocurridos en la ventana temporal especificada (últimos 3-6 meses).
- Profundiza en 5 frentes: (1) Regulaciones recientes, (2) Rondas de inversión o M&A, (3) Lanzamientos tecnológicos disruptivos, (4) Alianzas estratégicas y (5) Cambios en la demanda agregada.
- No generalices sobre tendencias de hace 5 años (como 'la nube es importante'); enfócate en lo nuevo de los últimos meses.
            """,
        )

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        start_time = time.time()
        industria = context.get("industria", "")
        pais = context.get("pais", "")
        ventana = context.get("ventana_analisis", "últimos 3-6 meses")
        self.set_analysis_window(context)

        # 1. Diseñar queries de búsqueda estratégica
        queries = [
            f"{industria} noticias tendencias recientes {ventana} {pais}",
            f"{industria} inversiones financiamiento lanzamientos {pais}",
            f"{industria} regulacion normativa cambios tecnologicos {pais}",
        ]

        # 2. Búsqueda web en paralelo
        search_results = await self.multi_search(queries, max_results_per_query=4)

        # 3. Preparar contexto para el LLM
        fuentes_formateadas = []
        for i, item in enumerate(search_results, 1):
            fuentes_formateadas.append(
                f"[{i}] Título: {item['title']}\n"
                f"    URL: {item['url']}\n"
                f"    Fecha/Origen: {item['date']} ({item['source']})\n"
                f"    Extracto: {item['content']}\n"
            )
        texto_fuentes = "\n".join(fuentes_formateadas) if fuentes_formateadas else "No se obtuvieron resultados de búsqueda web en tiempo real."

        prompt_usuario = f"""
DATOS DE ENTRADA:
- Industria / Sector: {industria}
- País / Mercado objetivo: {pais}
- Ventana temporal de análisis: {ventana}
- Descripción del negocio de referencia: {context.get('descripcion_negocio', '')}

EVIDENCIA RECOPILADA DE LA WEB ({len(search_results)} fuentes encontradas):
{texto_fuentes}

INSTRUCCIÓN:
Con base en la evidencia anterior y tu conocimiento de mercado, responde rigurosamente a la pregunta:
"{self.pregunta}"

Sigue estrictamente la estructura solicitada:
1. Resumen Ejecutivo (exactamente 3 líneas)
2. Hallazgos Clave (máximo 5, separando HECHO con enlace y fecha de INTERPRETACIÓN)
3. Nivel de Confianza (Alto/Medio/Bajo con justificación)
4. Qué dato falta para mejorar la respuesta
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
