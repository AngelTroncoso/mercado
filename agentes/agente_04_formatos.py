"""
Agente 4 - Formatos y propuestas de valor
Pregunta: ¿Qué formatos de producto, modelos de entrega o propuestas de valor están ganando tracción ahora?
Objetivo: Entender tendencias en formatos y experiencias.
Tareas: Identificar modelos (suscripción, freemium, on-demand, comunidad, etc.), y mostrar evidencia de tracción (crecimiento, adopción, financiamiento).
"""

import time
from typing import Dict, Any
from .base_agent import BaseAgent, AgentResult


class AgenteFormatosValor(BaseAgent):
    def __init__(self):
        super().__init__(
            agente_id=4,
            nombre="Agente 4 - Formatos y Propuestas de Valor",
            pregunta="¿Qué formatos de producto, modelos de entrega o propuestas de valor están ganando tracción ahora?",
            objetivo="Identificar qué empaquetados, esquemas de precios y modelos de entrega generan mayor tracción y conversión hoy.",
            reglas_especificas="""
ENFOQUE ESPECÍFICO DE ESTE AGENTE:
- Analiza esquemas comerciales: monetización basada en uso (consumption-based), suscripciones híbridas, esquemas outcome-based (cobro por resultado), Product-Led Growth (PLG), microtransacciones, embedding APIs, marketplaces integrados o servicios con componente de comunidad.
- Busca EVIDENCIA REAL de tracción: tasas de conversión, crecimiento en adopción de usuarios, aumentos en ARPU, reportes de financiamiento o declaraciones públicas de ejecutivos.
- Compara cómo la propuesta de valor tradicional (ej. 'ahorra tiempo con software') está siendo reemplazada por propuestas modernas (ej. 'agentes autónomos que hacen el trabajo por ti').
            """,
        )

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        start_time = time.time()
        industria = context.get("industria", "")
        pais = context.get("pais", "")
        ventana = context.get("ventana_analisis", "últimos 3-6 meses")
        self.set_analysis_window(context)

        queries = [
            f"{industria} modelos de negocio precios suscripcion monetizacion tendencias {pais}",
            f"{industria} product-led growth PLG pricing usage-based traccion 2024 2025",
            f"{industria} propuesta de valor formatos de entrega 'outcome based' marketplace",
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
        texto_fuentes = "\n".join(fuentes_formateadas) if fuentes_formateadas else "No se encontraron reportes directos sobre modelos de monetización."

        prompt_usuario = f"""
DATOS DE ENTRADA:
- Industria: {industria}
- Mercado objetivo: {pais}
- Mi modelo y producto actual: {context.get('descripcion_negocio', '')}
- Ventana temporal: {ventana}

EVIDENCIA DE MODELOS COMERCIALES Y TRACCIÓN:
{texto_fuentes}

INSTRUCCIÓN:
Identifica con precisión qué formatos de producto, modelos de entrega o esquemas de monetización están capturando el mercado hoy.
Responde rigurosamente a la pregunta:
"{self.pregunta}"

Estructura obligatoria:
1. Resumen Ejecutivo (exactamente 3 líneas sobre el formato dominante o emergente)
2. Hallazgos Clave (máximo 5 formatos/modelos con evidencia de tracción, separando HECHO con enlace y fecha de INTERPRETACIÓN estratégica)
3. Nivel de Confianza (Alto/Medio/Bajo con justificación)
4. Qué dato falta para mejorar la respuesta (ej. reportes privados de benchmarking de precios de SaaS, métricas de churn por modelo)
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
