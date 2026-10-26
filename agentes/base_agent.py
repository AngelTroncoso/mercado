"""
Clase base para todos los agentes del sistema de Estudio de Mercado.
Gestiona el acceso a LLMs (Gemini / OpenAI), búsqueda web (Tavily con fallback a DuckDuckGo),
y asegura que todos los agentes cumplan con las reglas de formato y separación de hechos/interpretaciones.
"""

import os
import re
import asyncio
import time
import inspect
import calendar
from collections import deque
from datetime import date
from urllib.parse import urlsplit, urlunsplit
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


class GeminiRateLimiter:
    """Limita globalmente las solicitudes Gemini a cuatro por ventana móvil de un minuto."""

    def __init__(self):
        self._requests = deque()
        self._lock = asyncio.Lock()

    async def acquire(self, on_wait=None):
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._requests and now - self._requests[0] >= 60:
                    self._requests.popleft()
                if len(self._requests) < 4:
                    self._requests.append(now)
                    return
                wait_seconds = 60 - (now - self._requests[0])

            if on_wait:
                callback_result = on_wait(wait_seconds, "Límite global de Gemini")
                if inspect.isawaitable(callback_result):
                    await callback_result
            else:
                print(f"⏳ Límite global de Gemini alcanzado; esperando {wait_seconds:.1f} segundos.")
            await asyncio.sleep(wait_seconds)


_GEMINI_RATE_LIMITER = GeminiRateLimiter()
_DAILY_QUOTA_WAIT_SECONDS: Optional[float] = None


class QuotaWaitExceeded(RuntimeError):
    def __init__(self, wait_seconds: float):
        self.wait_seconds = wait_seconds
        super().__init__(
            f"La cuota diaria de Gemini requiere esperar {wait_seconds:.0f} segundos; ejecución detenida."
        )


def gemini_daily_quota_wait_seconds() -> Optional[float]:
    return _DAILY_QUOTA_WAIT_SECONDS


@dataclass
class AgentResult:
    agente_id: int
    nombre: str
    pregunta: str
    objetivo: str
    resumen_3_lineas: str = ""
    contenido_completo: str = ""
    nivel_confianza: str = "Medio"  # Alto, Medio, Bajo
    por_que_confianza: str = ""
    dato_faltante: str = ""
    fuentes: List[Dict[str, str]] = field(default_factory=list)
    tiempo_ejecucion_segundos: float = 0.0
    error: Optional[str] = None
    aviso_corte: Optional[str] = None



class BaseAgent:
    """Clase base para todos los agentes especialistas."""

    def __init__(
        self,
        agente_id: int,
        nombre: str,
        pregunta: str,
        objetivo: str,
        reglas_especificas: Optional[str] = None,
    ):
        self.agente_id = agente_id
        self.nombre = nombre
        self.pregunta = pregunta
        self.objetivo = objetivo
        self.reglas_especificas = reglas_especificas or ""

        # Configuración LLM
        self.llm_provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model_name = os.getenv("OPENAI_MODEL", "gpt-4o").strip()
        self.last_generation_truncated = False
        self.wait_callback = None
        self.search_window_months = 6

        # Configuración Búsqueda
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "").strip()
        self.tavily_search_depth = os.getenv("TAVILY_SEARCH_DEPTH", "advanced")

        # Inicialización de clientes
        self.gemini_init_error = None
        self._init_llm_client()
        self._init_search_client()

    def _init_llm_client(self):
        """Inicializa el cliente de LLM según proveedor y variables de entorno."""
        self.gemini_client = None
        self.openai_client = None

        if self.gemini_api_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.gemini_api_key)
            except Exception as e:
                self.gemini_init_error = str(e)

        if self.openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_api_key)
            except Exception:
                pass

    def _init_search_client(self):
        """Inicializa Tavily Client si la API key está disponible."""
        self.tavily_client = None
        if self.tavily_api_key:
            try:
                from tavily import TavilyClient
                self.tavily_client = TavilyClient(api_key=self.tavily_api_key)
            except Exception:
                pass

    def set_analysis_window(self, context: Dict[str, Any]):
        window = str(context.get("ventana_analisis", ""))
        matches = re.findall(r"\b(3|6|12)\b", window)
        if matches:
            self.search_window_months = max(map(int, matches))

    def _search_start_date(self) -> date:
        today = date.today()
        month = today.month - self.search_window_months
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        start_day = min(today.day, calendar.monthrange(year, month)[1])
        return date(year, month, start_day)

    # ========================================================
    # BÚSQUEDA WEB (Tavily con fallback a DuckDuckGo)
    # ========================================================

    def _sync_search_tavily(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Búsqueda síncrona con Tavily API filtrando últimos 6 meses (180 días)."""
        if not self.tavily_client:
            raise ValueError("Tavily API key no configurada o cliente no inicializado.")

        today = date.today()
        start_date = self._search_start_date().isoformat()

        response = self.tavily_client.search(
            query=query,
            search_depth=self.tavily_search_depth,
            max_results=max_results,
            start_date=start_date,
            end_date=today.isoformat(),
            include_published_date=True,
            filter_by_published_date=True,
            include_answer=False,
            include_raw_content=False,
        )

        results = []
        for r in response.get("results", []):
            pub_date = r.get("published_date")
            fecha_limpia = str(pub_date).strip() if pub_date and str(pub_date).strip().lower() not in ["none", "null", "", "n/a"] else "fecha no verificada"

            results.append({
                "title": r.get("title", "Sin título"),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "date": fecha_limpia,
                "source": "Tavily",
            })
        return results

    def _sync_search_duckduckgo(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Búsqueda síncrona con DuckDuckGo (Fallback)."""
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []

        today = date.today()
        start_date = self._search_start_date()

        results = []
        try:
            with DDGS() as ddgs:
                ddgs_results = list(
                    ddgs.text(
                        f"{query} after:{start_date.isoformat()} before:{today.isoformat()}",
                        max_results=max_results,
                    )
                )
                for r in ddgs_results:
                    pub_date = str(r.get("date", "")).strip()
                    try:
                        parsed_date = date.fromisoformat(pub_date[:10])
                    except ValueError:
                        continue
                    if not start_date <= parsed_date <= today:
                        continue
                    results.append({
                        "title": r.get("title", "Sin título"),
                        "url": r.get("href", ""),
                        "content": r.get("body", ""),
                        "date": parsed_date.isoformat(),
                        "source": "DuckDuckGo",
                    })
        except Exception:
            return []
        return results

    def _sync_search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Ejecuta búsqueda con Tavily y aplica fallback a DuckDuckGo si es necesario."""
        if self.tavily_client:
            try:
                res = self._sync_search_tavily(query, max_results=max_results)
                if res:
                    return res
            except Exception:
                # Fallback silencioso a DuckDuckGo
                pass

        return self._sync_search_duckduckgo(query, max_results=max_results)

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Método asíncrono para ejecutar búsquedas sin bloquear el loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_search, query, max_results)

    async def multi_search(self, queries: List[str], max_results_per_query: int = 4) -> List[Dict[str, str]]:
        """Ejecuta múltiples búsquedas en paralelo y unifica fuentes sin duplicados de URL."""
        tasks = [self.search(q, max_results=max_results_per_query) for q in queries]
        all_results = await asyncio.gather(*tasks)

        merged: List[Dict[str, str]] = []
        seen_urls = set()

        for res_list in all_results:
            for item in res_list:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    merged.append(item)
                elif not url:
                    merged.append(item)

        return merged

    # ========================================================
    # INTERACCIÓN CON LLM (Gemini / OpenAI)
    # ========================================================

    def _sync_ask_gemini(self, prompt: str, system_prompt: str) -> Any:
        """Realiza una llamada síncrona al SDK oficial google.genai."""
        if not self.gemini_client:
            err = getattr(self, "gemini_init_error", None) or "Cliente no inicializado."
            raise ValueError(
                f"Gemini API Key no configurada o cliente no inicializado en google.genai ({err}). Por favor define GEMINI_API_KEY en tu archivo .env"
            )

        from google.genai import types
        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=16384,
            system_instruction=system_prompt,
        )
        return self.gemini_client.models.generate_content(
            model=self.gemini_model_name,
            contents=prompt,
            config=config,
        )

    @staticmethod
    def _is_rate_limit_error(error: Exception) -> bool:
        message = str(error).lower()
        return "429" in message or "resource_exhausted" in message

    @staticmethod
    def _retry_delay_seconds(error: Exception) -> float:
        message = str(error)
        compound_delay = re.search(
            r"retry\s+in\s+(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)",
            message,
            flags=re.IGNORECASE,
        )
        if compound_delay:
            hours, minutes, seconds = compound_delay.groups()
            return float(hours or 0) * 3600 + float(minutes or 0) * 60 + float(seconds or 0)
        patterns = (
            r'retryDelay["\']?\s*:\s*["\']?([\d.]+)s',
            r"retry\s+in\s+([\d.]+)s",
        )
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                return float(match.group(1))
        return 0.0

    async def _generate_gemini_with_retries(self, prompt: str, system_prompt: str) -> Any:
        global _DAILY_QUOTA_WAIT_SECONDS
        loop = asyncio.get_running_loop()
        for attempt in range(5):
            if _DAILY_QUOTA_WAIT_SECONDS is not None:
                raise QuotaWaitExceeded(_DAILY_QUOTA_WAIT_SECONDS)
            await _GEMINI_RATE_LIMITER.acquire(self.wait_callback)
            try:
                return await loop.run_in_executor(
                    None, self._sync_ask_gemini, prompt, system_prompt
                )
            except Exception as error:
                if not self._is_rate_limit_error(error) or attempt == 4:
                    raise
                retry_delay = self._retry_delay_seconds(error)
                wait_seconds = max(retry_delay + 2, (retry_delay + 2) * (2 ** attempt))
                if wait_seconds > 600:
                    _DAILY_QUOTA_WAIT_SECONDS = wait_seconds
                    if self.wait_callback:
                        callback_result = self.wait_callback(
                            wait_seconds, "Cuota diaria de Gemini agotada"
                        )
                        if inspect.isawaitable(callback_result):
                            await callback_result
                    raise QuotaWaitExceeded(wait_seconds) from error
                if self.wait_callback:
                    callback_result = self.wait_callback(wait_seconds, "Reintento por límite 429 de Gemini")
                    if inspect.isawaitable(callback_result):
                        await callback_result
                else:
                    print(
                        f"⏳ Gemini respondió con 429; reintento {attempt + 1}/4 "
                        f"en {wait_seconds:.1f} segundos."
                    )
                await asyncio.sleep(wait_seconds)

        raise RuntimeError("Se agotaron los reintentos de Gemini.")

    async def _ask_gemini(self, prompt: str, system_prompt: str) -> str:
        parts = []
        current_prompt = prompt
        self.last_generation_truncated = False

        for continuation in range(5):
            response = await self._generate_gemini_with_retries(current_prompt, system_prompt)
            candidate = response.candidates[0] if response.candidates else None
            if candidate is None:
                raise RuntimeError("Gemini no devolvió candidatos para la solicitud.")

            text = response.text or ""
            if text:
                parts.append(text)
            finish_reason = str(getattr(candidate, "finish_reason", "")).upper()
            if "MAX_TOKENS" not in finish_reason:
                if "STOP" not in finish_reason:
                    self.last_generation_truncated = True
                break
            if continuation == 4:
                self.last_generation_truncated = True
                break

            accumulated = "\n".join(parts)
            current_prompt = (
                f"{prompt}\n\n"
                "CONTINUACIÓN DE RESPUESTA: La respuesta anterior alcanzó MAX_TOKENS. "
                "Continúa exactamente desde el punto donde quedó, sin repetir texto. "
                "Conserva las reglas, las citas y el formato solicitado.\n\n"
                f"RESPUESTA GENERADA HASTA AHORA:\n{accumulated}"
            )

        final_text = "\n".join(parts).strip()
        if self.last_generation_truncated:
            final_text += "\n\n> **RESPUESTA TRUNCADA**: Gemini no pudo completar la sección tras las continuaciones disponibles."
        if not final_text:
            raise RuntimeError("Gemini devolvió una respuesta vacía.")
        return final_text

    def _sync_ask_openai(self, prompt: str, system_prompt: str) -> str:
        """Llamada síncrona a OpenAI con aumento de tokens y control de corte."""
        if not self.openai_client:
            raise ValueError(
                "OpenAI API Key no configurada. Por favor define OPENAI_API_KEY en tu archivo .env"
            )

        response = self.openai_client.chat.completions.create(
            model=self.openai_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=16384,
        )

        choice = response.choices[0]
        texto_final = choice.message.content or ""

        if choice.finish_reason != "stop":
            prompt_reintento = prompt + "\n\n[ATENCIÓN: Tu respuesta anterior se cortó. Por favor concluye todas las secciones de manera completa.]"
            try:
                retry_resp = self.openai_client.chat.completions.create(
                    model=self.openai_model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt_reintento},
                    ],
                    temperature=0.2,
                    max_tokens=16384,
                )
                retry_choice = retry_resp.choices[0]
                texto_final = retry_choice.message.content or texto_final
                self.last_generation_truncated = retry_choice.finish_reason != "stop"
            except Exception:
                self.last_generation_truncated = True

        if self.last_generation_truncated:
            texto_final += "\n\n> **RESPUESTA TRUNCADA**: La respuesta no pudo completarse tras el reintento."

        return texto_final

    def _sync_ask_llm(self, prompt: str, system_prompt: str) -> str:
        """Invoca el LLM configurado (Gemini por defecto o OpenAI)."""
        # Si se eligió gemini o hay key de gemini disponible
        if self.llm_provider == "gemini" and self.gemini_api_key:
            return self._sync_ask_gemini(prompt, system_prompt)
        elif self.openai_api_key:
            return self._sync_ask_openai(prompt, system_prompt)
        elif self.gemini_api_key:
            return self._sync_ask_gemini(prompt, system_prompt)
        else:
            raise ValueError(
                "No se encontró ninguna clave de API válida. Por favor edita el archivo .env y coloca GEMINI_API_KEY o OPENAI_API_KEY."
            )

    async def ask_llm(self, prompt: str, system_prompt: str) -> str:
        """Consulta el LLM elegido, aplicando límites y continuaciones a Gemini."""
        use_gemini = (
            (self.llm_provider == "gemini" and bool(self.gemini_api_key))
            or (not self.openai_api_key and bool(self.gemini_api_key))
        )
        if use_gemini:
            return await self._ask_gemini(prompt, system_prompt)

        self.last_generation_truncated = False
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_ask_llm, prompt, system_prompt)

    def format_extra_context(self, context: Dict[str, Any]) -> str:
        """Formatea campos opcionales de config.yaml como competidores y notas adicionales."""
        extras = []
        competidores = context.get("competidores_referencia")
        if competidores:
            if isinstance(competidores, list):
                extras.append("COMPETIDORES / REFERENTES CONOCIDOS:\n" + "\n".join(f"- {c}" for c in competidores))
            else:
                extras.append(f"COMPETIDORES / REFERENTES CONOCIDOS:\n{competidores}")
        notas = context.get("notas_adicionales")
        if notas:
            extras.append(f"ENFOQUE Y NOTAS ADICIONALES DEL USUARIO:\n{str(notas).strip()}")
        return "\n\n".join(extras)

    # ========================================================
    # PROMPTS Y REGLAS MAESTRAS
    # ========================================================

    def get_system_prompt(self) -> str:
        """Genera el prompt de sistema universal respetando las reglas de la arquitectura."""
        return f"""Eres el {self.nombre} (Agente #{self.agente_id}) de un sistema multiagente de Estudio de Mercado de nivel ejecutivo.

Tu Pregunta Asignada es:
"{self.pregunta}"

Tu Objetivo es:
"{self.objetivo}"

{self.reglas_especificas}

REGLAS OBLIGATORIAS PARA TU RESPUESTA:
1. Responde SIEMPRE en ESPAÑOL profesional, conciso y de alta relevancia estratégica.
2. CITAS Y FECHAS OBLIGATORIAS:
   - Cita la fuente con enlace Markdown exacto: [Nombre de la fuente](URL), solo si la URL aparece en la evidencia.
   - Usa EXCLUSIVAMENTE la fecha que aparece en la evidencia provista.
   - Si una fuente no trae fecha en la evidencia o dice 'fecha no verificada', escribe obligatoriamente 'fecha no verificada'.
   - PROHIBIDO inventar fechas. Si falta fecha, escribe 'fecha no verificada'.
3. SEPARACIÓN ESTRICTA Y ETIQUETAS:
   - Usa ÚNICAMENTE las etiquetas `[HECHO]` (con su fuente) y `*Interpretación*` (tu deducción estratégica).
   - Está terminantemente prohibido usar etiquetas de hecho distintas de `[HECHO]`.
   - Cualquier cifra hipotética, precio de ejemplo o tasa de conversión no respaldada debe etiquetarse 'Supuesto a validar'.
4. HONESTIDAD INTELECTUAL: Si no hay evidencia suficiente en los datos o búsquedas para responder un aspecto, indícalo expresamente. NUNCA inventes estadísticas, nombres de startups ni URLs.
5. FORMATO OBLIGATORIO DE SALIDA: Debes estructurar tu respuesta exactamente con estos encabezados H4 (sin agregar números como 1, 2, 3 en los títulos para evitar duplicación con el informe general):

#### Resumen Ejecutivo
(Exactamente en 3 líneas:
 Línea 1: El cambio o patrón central detectado.
 Línea 2: El impacto directo o implicancia en el mercado.
 Línea 3: La conclusión o llamada de atención clave.)

#### Hallazgos Clave
(Máximo 5 hallazgos de alto impacto usando estrictamente este esquema):
- **[HECHO]**: Descripción precisa del dato, evento o métrica con su cita [Fuente](URL) - Fecha.
  - *Interpretación*: Qué significa este hecho para el sector y qué oportunidad o riesgo abre.

#### Nivel de Confianza
- **Nivel**: [Alto | Medio | Bajo]
- **Justificación**: Explicación clara de por qué asignas este nivel (calidad de fuentes encontradas, frescura de los datos, representatividad de la muestra).

#### Información Faltante para Optimizar la Respuesta
(Describe qué dato privado, estudio de pago, métrica de telemetría o fuente interna cerraría la brecha de información restante).
"""

    def verificar_y_sanear_citas(self, texto: str, fuentes: List[Dict[str, str]]) -> str:
        """
        Verifica que cada enlace Markdown [Texto](URL) citado por el agente
        esté efectivamente en la lista de fuentes devueltas por la búsqueda web.
        Si no está en las fuentes encontradas, borra el enlace y marca el dato como '(sin fuente)'.
        """
        def normalize_url(url: str) -> str:
            parsed = urlsplit(url.strip())
            return urlunsplit(
                (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, "")
            )

        valid_urls = {
            normalize_url(source.get("url", ""))
            for source in fuentes
            if source.get("url", "").strip()
        }

        pattern = re.compile(r'\[([^\]]+)\]\((https?://[^\)\s]+)\)')

        def _replace_link(match):
            anchor_text = match.group(1).strip()
            link_url = match.group(2).strip()
            if normalize_url(link_url) in valid_urls:
                return match.group(0)
            return f"{anchor_text} (sin fuente)"

        texto = pattern.sub(_replace_link, texto)
        sanitized_lines = []
        for line in texto.splitlines():
            if "[HECHO]" in line and not re.search(pattern, line):
                line = line.replace("[HECHO]", "*Interpretación*")
                if "sin fuente" not in line.lower():
                    line += " (sin fuente)"
            sanitized_lines.append(line)
        return "\n".join(sanitized_lines)

    def sanitizar_contenido_agente(self, raw_text: str, fuentes: List[Dict[str, str]]) -> str:
        """Aplica todas las reglas de calidad: citas verificadas, limpieza de fechas y títulos limpios."""
        texto = raw_text

        # 1. Quitar 'HECHO CONTRASTADO' y dejar solo [HECHO]
        texto = re.sub(r'\[\s*HECHO\s+CONTRASTADO\s*\]', '[HECHO]', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\*\*\s*\[\s*HECHO\s+CONTRASTADO\s*\]\s*\*\*', '**[HECHO]**', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\bHECHO\s+CONTRASTADO\b', '[HECHO]', texto)

        # 2. Eliminar la palabra prohibida y sustituirla por una fecha no verificada.
        texto = re.sub(r'\bReciente\b', 'fecha no verificada', texto, flags=re.IGNORECASE)

        # 3. Verificar y sanear citas contra la lista de fuentes (si no está, borra y marca sin fuente)
        texto = self.verificar_y_sanear_citas(texto, fuentes)

        # 4. Normalizar encabezados para evitar títulos duplicados en el informe
        texto = re.sub(r'###\s*1\.\s*Resumen\s*Ejecutivo[^\n]*', '#### Resumen Ejecutivo', texto, flags=re.IGNORECASE)
        texto = re.sub(r'###\s*2\.\s*Hallazgos\s*Clave[^\n]*', '#### Hallazgos Clave', texto, flags=re.IGNORECASE)
        texto = re.sub(r'###\s*3\.\s*Nivel\s*de\s*Confianza[^\n]*', '#### Nivel de Confianza', texto, flags=re.IGNORECASE)
        texto = re.sub(r'###\s*4\.\s*Qu[eé]\s*dato\s*falta[^\n]*', '#### Información Faltante para Optimizar la Respuesta', texto, flags=re.IGNORECASE)
        texto = re.sub(r'###\s*Resumen\s*Ejecutivo[^\n]*', '#### Resumen Ejecutivo', texto, flags=re.IGNORECASE)
        texto = re.sub(r'###\s*Hallazgos\s*Clave[^\n]*', '#### Hallazgos Clave', texto, flags=re.IGNORECASE)
        texto = re.sub(r'###\s*Nivel\s*de\s*Confianza[^\n]*', '#### Nivel de Confianza', texto, flags=re.IGNORECASE)

        # 5. Eliminar títulos duplicados iniciales si el LLM repitió el título del agente
        lines = texto.splitlines()
        while lines and (lines[0].strip().startswith("#") or not lines[0].strip()):
            line_str = lines[0].lower()
            if any(k in line_str for k in ["agente", "cambios", "voz del", "soluciones", "formatos", "riesgos", "ideas", "hipótesis", "hipotesis"]):
                lines.pop(0)
            else:
                break
        texto = "\n".join(lines).strip()

        return texto

    def parse_sections(self, raw_text: str) -> Dict[str, str]:
        """Extrae el resumen de 3 líneas y el nivel de confianza para reportes ejecutivos."""
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        resumen_lines = []
        capturing_resumen = False

        for line in lines:
            if "Resumen Ejecutivo" in line:
                capturing_resumen = True
                continue
            if capturing_resumen:
                if line.startswith("#"):
                    break
                # Ignorar avisos o notas
                if line and not line.startswith(">"):
                    resumen_lines.append(line)
                if len(resumen_lines) >= 3:
                    break

        resumen_3_lineas = "\n".join(resumen_lines[:3]) if resumen_lines else "Resumen disponible en el cuerpo del informe."

        # Detectar nivel de confianza
        nivel_confianza = "Medio"
        lower_text = raw_text.lower()
        if "**nivel**: alto" in lower_text or "nivel: alto" in lower_text:
            nivel_confianza = "Alto"
        elif "**nivel**: bajo" in lower_text or "nivel: bajo" in lower_text:
            nivel_confianza = "Bajo"

        return {
            "resumen_3_lineas": resumen_3_lineas,
            "nivel_confianza": nivel_confianza,
        }


    # ========================================================
    # MÉTODO PRINCIPAL A SOBREESCRIBIR
    # ========================================================

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        """Debe ser implementado por cada agente especialista."""
        raise NotImplementedError("Cada agente debe implementar su propio método run(context).")
