"""
Agente 7 - Hipótesis estratégica
Pregunta: ¿Cuál es una hipótesis estratégica de alto impacto y poco convencional que debería explorar o probar en mi negocio?
Objetivo: Definir una dirección innovadora, accionable y diferenciada.
Tareas: Usando todo lo anterior (Agentes 1 a 6), proponer 1 hipótesis principal (y 2 alternativas) con: qué probar, cómo probarlo en 30 días, métrica de éxito y riesgo principal.
"""

import time
from typing import Dict, Any, List
from .base_agent import BaseAgent, AgentResult


class AgenteHipotesisEstrategica(BaseAgent):
    def __init__(self):
        super().__init__(
            agente_id=7,
            nombre="Agente 7 - Hipótesis Estratégica",
            pregunta="¿Cuál es una hipótesis estratégica de alto impacto y poco convencional que debería explorar o probar en mi negocio?",
            objetivo="Sintetizar la inteligencia de mercado previa en 1 hipótesis directriz no obvia y 2 alternativas accionables a 30 días.",
            reglas_especificas="""
ENFOQUE ESPECÍFICO DE ESTE AGENTE:
- Eres el estratega jefe del sistema. Debes conectar los puntos invisibles entre lo que la industria cambia (Agente 1), lo que el cliente sufre (Agente 2), lo que los rebeldes hacen (Agente 3), los nuevos modelos de cobro (Agente 4), las debilidades del negocio (Agente 5) y lo que se debe abandonar (Agente 6).
- Rechaza los lugares comunes (como 'hacer más marketing' o 'añadir un chatbot genérico').
- Propón 1 HIPÓTESIS PRINCIPAL DE ALTO IMPACTO y 2 HIPÓTESIS ALTERNATIVAS.
- Para CADA hipótesis debes estructurar sin excepción:
  1. QUÉ PROBAR: La propuesta de valor, producto o pivote de modelo.
  2. EXPERIMENTO A 30 DÍAS: Paso a paso concreto, barato y rápido de validación sin quemar capital.
  3. MÉTRICA DE ÉXITO (KPI): Cifra o umbral numérico que define si la hipótesis es válida.
  4. RIESGO PRINCIPAL: El mayor factor que podría hacer fracasar el experimento y cómo mitigarlo.
            """,
        )

    async def run(self, context: Dict[str, Any], previous_results: List[AgentResult] = None) -> AgentResult:
        start_time = time.time()
        industria = context.get("industria", "")
        descripcion_negocio = context.get("descripcion_negocio", "")
        pais = context.get("pais", "")

        # Resumen consolidado de todos los agentes anteriores (1 al 6)
        sintesis_todos = []
        secciones_ausentes = []
        if previous_results:
            for res in previous_results:
                if res.error:
                    secciones_ausentes.append(f"Agente {res.agente_id}: {res.nombre} (falló)")
                elif res.aviso_corte:
                    secciones_ausentes.append(f"Agente {res.agente_id}: {res.nombre} (respuesta truncada)")
                sintesis_todos.append(
                    f"====================================================\n"
                    f"RESULTADOS DE {res.nombre.upper()}\n"
                    f"Pregunta: {res.pregunta}\n"
                    f"Resumen de 3 líneas:\n{res.resumen_3_lineas}\n\n"
                    f"Detalle:\n{res.contenido_completo}\n"
                )
        texto_acumulado = "\n".join(sintesis_todos) if sintesis_todos else "No se proporcionaron resultados previos."
        aviso_ausencias = (
            "El Agente 7 debe advertir explícitamente que trabajó sin estas secciones: "
            + ", ".join(secciones_ausentes)
            if secciones_ausentes
            else "No se detectaron secciones previas fallidas o truncadas."
        )

        prompt_usuario = f"""
CONTEXTO COMPLETO DEL NEGOCIO:
- Industria / Sector: {industria}
- Mercado objetivo: {pais}
- Mi negocio / producto actual:
\"\"\"{descripcion_negocio}\"\"\"

EXPEDIENTE COMPLETO DE INVESTIGACIÓN (AGENTES 1 AL 6):
{texto_acumulado}

ADVERTENCIA DE COBERTURA:
{aviso_ausencias}
Si faltan secciones, no simules sus conclusiones; identifica expresamente cuáles no estuvieron disponibles.
Cualquier cifra hipotética, precio de ejemplo o tasa de conversión no respaldada debe etiquetarse "Supuesto a validar".

INSTRUCCIÓN:
Con base en todo el expediente de investigación acumulado, sintetiza la dirección estratégica más prometedora, audaz y pragmática para este negocio.
Responde rigurosamente a la pregunta:
"{self.pregunta}"

Estructura obligatoria:
1. Resumen Ejecutivo (exactamente 3 líneas sintetizando el salto estratégico propuesto)
2. Hallazgos Clave:
   - HIPÓTESIS PRINCIPAL (Detallando: Qué probar, Experimento de validación en 30 días, Métrica de éxito cuantitativa y Riesgo principal)
   - HIPÓTESIS ALTERNATIVA 1 (Qué probar, Experimento en 30 días, Métrica, Riesgo)
   - HIPÓTESIS ALTERNATIVA 2 (Qué probar, Experimento en 30 días, Métrica, Riesgo)
3. Nivel de Confianza (Alto/Medio/Bajo con justificación fundada en los datos previos)
4. Qué dato falta para mejorar la respuesta (ej. pruebas de elasticidad de precios, entrevistas directas con clientes piloto)
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
            if secciones_ausentes:
                aviso = (
                    "> **Advertencia:** El Agente 7 trabajó sin estas secciones: "
                    + ", ".join(secciones_ausentes)
                    + ".\n\n"
                )
                sanitized = aviso + sanitized
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
