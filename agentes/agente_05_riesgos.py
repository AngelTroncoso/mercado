"""
Agente 5 - Riesgos y brechas propias
Pregunta: ¿Qué riesgos o brechas existen en mi enfoque actual desde esta nueva perspectiva del mercado?
Objetivo: Detectar debilidades internas.
Tareas: Comparar mi negocio con los hallazgos de los agentes 1 a 4. Listar riesgos, brechas y su nivel de urgencia (alto, medio, bajo).
"""

import time
from typing import Dict, Any, List
from .base_agent import BaseAgent, AgentResult


class AgenteRiesgosBrechas(BaseAgent):
    def __init__(self):
        super().__init__(
            agente_id=5,
            nombre="Agente 5 - Riesgos y Brechas Propias",
            pregunta="¿Qué riesgos o brechas existen en mi enfoque actual desde esta nueva perspectiva del mercado?",
            objetivo="Detectar puntos ciegos, vulnerabilidades competitivas y brechas de producto o modelo comercial en el negocio del usuario.",
            reglas_especificas="""
ENFOQUE ESPECÍFICO DE ESTE AGENTE:
- Actúa como un auditor estratégico implacable y constructivo.
- Cruza la descripción del negocio del usuario contra los hallazgos externos de los Agentes 1, 2, 3 y 4:
  * Agente 1 (Cambios de industria): ¿El negocio está desactualizado frente a regulaciones o saltos tecnológicos?
  * Agente 2 (Voz del cliente): ¿El negocio comete los mismos errores que los usuarios odian o ignora sus dolores latentes?
  * Agente 3 (Soluciones innovadoras): ¿Una startup emergente puede dejar obsoleto nuestro valor central?
  * Agente 4 (Formatos/Modelos): ¿Nuestro esquema de precios o entrega está en desventaja frente a lo que hoy gana tracción?
- Clasifica cada riesgo/brecha por su NIVEL DE URGENCIA: [URGENCIA ALTA / MEDIA / BAJA].
            """,
        )

    async def run(self, context: Dict[str, Any], previous_results: List[AgentResult] = None) -> AgentResult:
        start_time = time.time()
        industria = context.get("industria", "")
        descripcion_negocio = context.get("descripcion_negocio", "")
        pais = context.get("pais", "")

        # Sintetizar los resultados previos de los Agentes 1 al 4
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

HALLAZGOS DE LA INVESTIGACIÓN EXTERNA (AGENTES 1, 2, 3 Y 4):
{sintesis_mercado}

INSTRUCCIÓN:
Realiza una auditoría crítica, honesta y detallada sobre las vulnerabilidades de mi negocio frente a este nuevo panorama del mercado.
Responde rigurosamente a la pregunta:
"{self.pregunta}"

Estructura obligatoria:
1. Resumen Ejecutivo (exactamente 3 líneas con el riesgo existencial más crítico)
2. Hallazgos Clave (máximo 5 riesgos o brechas concretas. Para cada uno indica [URGENCIA: ALTA | MEDIA | BAJA], describe el HECHO/DESAJUSTE citando la evidencia del mercado vs mi negocio, y la INTERPRETACIÓN del impacto que causaría si no se resuelve)
3. Nivel de Confianza (Alto/Medio/Bajo con justificación de por qué el diagnóstico es certero o qué asunciones se hicieron)
4. Qué dato falta para mejorar la respuesta (ej. métricas internas de CAC, LTV, churn, retención o backlog técnico del producto)
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
