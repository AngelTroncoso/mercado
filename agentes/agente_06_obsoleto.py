"""
Agente 6 - Ideas obsoletas
Pregunta: ¿Qué ideas o tendencias han perdido relevancia y deberían reconsiderarse o eliminarse?
Objetivo: Limpiar y enfocar la estrategia eliminando lastre y supuestos caducos.
Tareas: Señalar supuestos, productos, canales o tendencias que ya no funcionan. Recomendar: mantener, reconsiderar o eliminar.
"""

import time
from typing import Dict, Any, List
from .base_agent import BaseAgent, AgentResult


class AgenteIdeasObsoletas(BaseAgent):
    def __init__(self):
        super().__init__(
            agente_id=6,
            nombre="Agente 6 - Ideas Obsoletas",
            pregunta="¿Qué ideas o tendencias han perdido relevancia y deberían reconsiderarse o eliminarse?",
            objetivo="Identificar dogmas caídos, características zombis, canales agotados o supuestos obsoletos para despriorizarlos o eliminarlos de raíz.",
            reglas_especificas="""
ENFOQUE ESPECÍFICO DE ESTE AGENTE:
- Identifica lo que solía ser una 'mejor práctica' hace 12-24 meses pero que hoy destruye margen, alarga ciclos de venta o es ignorado por los usuarios.
- Analiza 4 dimensiones de obsolescencia:
  1. Supuestos de producto (funcionalidades complejas que nadie usa, interfaces pesadas).
  2. Canales de adquisición (canales de marketing saturados o con CAC disparado).
  3. Modelos comerciales y de precios (términos contractuales rígidos, barreras de entrada innecesarias).
  4. Narrativas de marketing gastadas (mensajes de venta trillados que no generan clics ni confianza).
- Para cada elemento analizado, emite una recomendación categórica:
  * [MANTENER]: Si aún aporta valor defensivo comprobado.
  * [RECONSIDERAR]: Si requiere un rediseño radical o simplificación urgente.
  * [ELIMINAR]: Si drena recursos y debe cortarse inmediatamente.
            """,
        )

    async def run(self, context: Dict[str, Any], previous_results: List[AgentResult] = None) -> AgentResult:
        start_time = time.time()
        industria = context.get("industria", "")
        descripcion_negocio = context.get("descripcion_negocio", "")
        pais = context.get("pais", "")

        prev_text = []
        if previous_results:
            for res in previous_results:
                if res.agente_id in [1, 2, 3, 4]:
                    prev_text.append(
                        f"=== HALLAZGOS DEL {res.nombre.upper()} ===\n"
                        f"Resumen:\n{res.resumen_3_lineas}\n\n"
                        f"Detalle completo:\n{res.contenido_completo}\n"
                    )
        sintesis_mercado = "\n".join(prev_text) if prev_text else "No se recibieron resultados de los agentes 1 a 4."

        prompt_usuario = f"""
DATOS DE MI NEGOCIO:
- Industria: {industria}
- Mercado objetivo: {pais}
- Descripción exacta de mi negocio actual:
\"\"\"{descripcion_negocio}\"\"\"

HALLAZGOS EXTERNOS DEL MERCADO (AGENTES 1, 2, 3 Y 4):
{sintesis_mercado}

INSTRUCCIÓN:
Evalúa críticamente qué prácticas, supuestos o elementos del negocio o de la industria están caducos y deben ser desestimados para ganar foco y agilidad.
Responde rigurosamente a la pregunta:
"{self.pregunta}"

Estructura obligatoria:
1. Resumen Ejecutivo (exactamente 3 líneas sobre el mayor lastre o distracción estratégica)
2. Hallazgos Clave (máximo 5 prácticas o supuestos a limpiar. Para cada uno indica [RECOMENDACIÓN: MANTENER | RECONSIDERAR | ELIMINAR], describe el HECHO/EVIDENCIA de obsolescencia y la INTERPRETACIÓN de qué recursos se liberan al corregirlo)
3. Nivel de Confianza (Alto/Medio/Bajo con justificación)
4. Qué dato falta para mejorar la respuesta (ej. tasa de uso de funcionalidades internas, desglose de costos por canal)
"""
        extra_ctx = self.format_extra_context(context)
        if extra_ctx:
            prompt_usuario += f"\nINFORMACIÓN ADICIONAL DEL USUARIO:\n{extra_ctx}\n"


        fuentes_acumuladas = []
        if previous_results:
            for pr in previous_results:
                fuentes_acumuladas.extend(pr.fuentes)

        try:
            raw_output = await self.ask_llm(prompt_usuario, self.get_system_prompt())
            sanitized = self.sanitizar_contenido_agente(raw_output, fuentes_acumuladas)
            parsed = self.parse_sections(sanitized)

            return AgentResult(
                agente_id=self.agente_id,
                nombre=self.nombre,
                pregunta=self.pregunta,
                objetivo=self.objetivo,
                resumen_3_lineas=parsed["resumen_3_lineas"],
                contenido_completo=sanitized,
                nivel_confianza=parsed["nivel_confianza"],
                fuentes=fuentes_acumuladas,
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
