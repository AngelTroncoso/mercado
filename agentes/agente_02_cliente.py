"""
Agente 2 - Voz del cliente
Pregunta: ¿Qué necesidades no satisfechas o frustraciones emergentes expresan los clientes en conversaciones públicas?
Objetivo: Captar señales reales de los usuarios.
Tareas: Revisar reseñas, foros, Reddit, redes sociales, comentarios y comunidades. Agrupar quejas y deseos por tema y estimar su frecuencia.
"""

import time
from typing import Dict, Any
from .base_agent import BaseAgent, AgentResult


class AgenteVozCliente(BaseAgent):
    def __init__(self):
        super().__init__(
            agente_id=2,
            nombre="Agente 2 - Voz del Cliente",
            pregunta="¿Qué necesidades no satisfechas o frustraciones emergentes expresan los clientes en conversaciones públicas?",
            objetivo="Captar señales reales de los usuarios, detectando quejas recurrentes, dolores no resueltos y fricciones emergentes.",
            reglas_especificas="""
ENFOQUE ESPECÍFICO DE ESTE AGENTE:
- Busca conversaciones espontáneas y testimonios reales: Reddit, foros especializados, reseñas en G2, Capterra, Google Reviews, Twitter/X, comentarios en YouTube y comunidades del sector.
- Agrupa las quejas y deseos por TEMAS (ej. fricción en soporte técnico, opacidad de precios, curvas de aprendizaje excesivas, caídas de servicio, integraciones rotas).
- Estima la frecuencia/intensidad del dolor (Crítico / Frecuente / Emergente) para cada tema.
- Diferencia claramente lo que los usuarios dicen explícitamente (hecho con fuente/reseña) de lo que deduces sobre su frustración psicológica subyacente (interpretación).
            """,
        )

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        start_time = time.time()
        industria = context.get("industria", "")
        pais = context.get("pais", "")
        ventana = context.get("ventana_analisis", "últimos 3-6 meses")
        self.set_analysis_window(context)

        # Queries orientadas a dolor y foros
        queries = [
            f"{industria} quejas opiniones reclamos problemas usuarios {pais}",
            f"{industria} reddit foro opiniones 'peor' 'odio' 'problema' review",
            f"{industria} frustraciones alternativas soporte precio comentarios clientes",
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
        texto_fuentes = "\n".join(fuentes_formateadas) if fuentes_formateadas else "No se encontraron reseñas directas en la web."

        prompt_usuario = f"""
DATOS DE ENTRADA:
- Industria: {industria}
- País / Mercado: {pais}
- Producto / Negocio de referencia: {context.get('descripcion_negocio', '')}
- Ventana de análisis: {ventana}

CONVERSACIONES PÚBLICAS Y EVIDENCIA DETECTADA:
{texto_fuentes}

INSTRUCCIÓN:
Analiza a fondo las frustraciones, quejas y deseos latentes de los compradores o usuarios en este sector.
Responde rigurosamente a la pregunta:
"{self.pregunta}"

Estructura obligatoria:
1. Resumen Ejecutivo (exactamente 3 líneas sobre el dolor dominante del cliente)
2. Hallazgos Clave (máximo 5 quejas/deseos, indicando tema y frecuencia estimada, separando HECHO de reseña/comunidad con enlace de INTERPRETACIÓN)
3. Nivel de Confianza (Alto/Medio/Bajo con justificación)
4. Qué dato falta para mejorar la respuesta (ej. acceso a tickets de soporte, encuestas NPS privadas)
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
