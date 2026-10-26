"""
Script de diagnóstico de conexión para el Sistema Multiagente de Estudio de Mercado.
Prueba por separado:
1. Conexión con Google Gemini (usando el nuevo SDK google.genai).
2. Conexión con Tavily Search API.
Informa claramente el estado, el error real y recomendaciones en lenguaje simple.
"""

import os
import sys
import calendar
from datetime import date
from dotenv import load_dotenv

# Asegurar UTF-8 en consolas Windows (cp1252) para evitar UnicodeEncodeError
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Cargar variables de entorno
load_dotenv()


def redactar_secretos(texto: str) -> str:
    """Evita que errores externos impriman claves API presentes en el entorno."""
    for variable in ("GEMINI_API_KEY", "TAVILY_API_KEY", "OPENAI_API_KEY"):
        secreto = os.getenv(variable, "").strip()
        if secreto:
            texto = texto.replace(secreto, "[CLAVE OCULTA]")
    return texto


# Intentar usar rich para formato visual, con fallback a print estándar
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console(force_terminal=True, legacy_windows=False)
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    class DummyConsole:
        def print(self, *args, **kwargs):
            text = " ".join(str(a) for a in args)
            # Limpiar etiquetas bbcode de rich para texto plano
            import re
            clean = re.sub(r'\[/?[a-zA-Z0-9_\#\s\=\-]+\]', '', text)
            print(clean)
    console = DummyConsole()


def probar_gemini() -> dict:
    """Prueba la conexión con Google Gemini usando el SDK google.genai."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()

    resultado = {
        "servicio": "Google Gemini (LLM)",
        "configurado": bool(api_key),
        "modelo": model_name,
        "exito": False,
        "error_tipo": None,
        "error_mensaje": None,
        "diagnostico_simple": None,
        "sugerencia": None,
    }

    if not api_key:
        resultado["error_tipo"] = "Falta API Key"
        resultado["error_mensaje"] = "La variable GEMINI_API_KEY está vacía en el archivo .env."
        resultado["diagnostico_simple"] = "No has colocado tu clave de Gemini en el archivo .env."
        resultado["sugerencia"] = "Obtén una clave gratuita en https://aistudio.google.com/ y colócala en GEMINI_API_KEY en tu archivo .env."
        return resultado

    # Probar importación de google.genai
    try:
        from google import genai
    except ImportError as e:
        resultado["error_tipo"] = "Librería no instalada"
        resultado["error_mensaje"] = str(e)
        resultado["diagnostico_simple"] = "Falta instalar el nuevo paquete oficial 'google-genai'."
        resultado["sugerencia"] = "Ejecuta: pip install google-genai"
        return resultado

    # Probar llamada a la API
    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model_name,
            contents="Responde únicamente la palabra: CONECTADO",
        )
        texto = resp.text.strip() if resp and resp.text else ""
        resultado["exito"] = True
        resultado["respuesta_prueba"] = texto
        return resultado
    except Exception as e:
        err_msg = redactar_secretos(str(e))
        resultado["error_tipo"] = type(e).__name__
        resultado["error_mensaje"] = err_msg

        # Diagnóstico en lenguaje simple
        if "404" in err_msg or "NOT_FOUND" in err_msg or "is no longer available" in err_msg:
            resultado["diagnostico_simple"] = (
                f"El modelo configurado '{model_name}' no existe o ya no está disponible en la API de Google."
            )
            resultado["sugerencia"] = (
                "Consulta los modelos disponibles para tu cuenta y configura GEMINI_MODEL con uno habilitado."
            )
        elif "503" in err_msg or "UNAVAILABLE" in err_msg or "high demand" in err_msg:
            resultado["diagnostico_simple"] = (
                f"Los servidores de Google tienen alta demanda temporal para el modelo '{model_name}'."
            )
            resultado["sugerencia"] = (
                "Intenta nuevamente en unos instantes o selecciona otro modelo habilitado en GEMINI_MODEL."
            )
        elif "400" in err_msg or "API_KEY_INVALID" in err_msg or "PERMISSION_DENIED" in err_msg or "403" in err_msg:
            resultado["diagnostico_simple"] = "La clave GEMINI_API_KEY no es válida o no tiene permisos activados."
            resultado["sugerencia"] = "Verifica que copiaste la clave completa de https://aistudio.google.com/ sin espacios extra."
        elif "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
            if "per day" in err_msg.lower() or "perday" in err_msg.lower():
                resultado["diagnostico_simple"] = "Se agotó la cuota diaria de solicitudes del modelo Gemini configurado."
                resultado["sugerencia"] = "Vuelve a intentarlo cuando se cumpla el retryDelay informado por Google o revisa los límites de tu cuenta."
            else:
                resultado["diagnostico_simple"] = "Se superó el límite de solicitudes por minuto de Gemini."
                resultado["sugerencia"] = "Espera el retryDelay indicado por Google antes de volver a consultar."
        else:
            resultado["diagnostico_simple"] = f"Error al contactar con la API de Gemini: {err_msg[:120]}"
            resultado["sugerencia"] = "Revisa tu conexión a internet o el estado de los servicios de Google AI."

        return resultado


def probar_tavily() -> dict:
    """Prueba la conexión con Tavily Search API."""
    api_key = os.getenv("TAVILY_API_KEY", "").strip()

    resultado = {
        "servicio": "Tavily Search API",
        "configurado": bool(api_key),
        "exito": False,
        "error_tipo": None,
        "error_mensaje": None,
        "diagnostico_simple": None,
        "sugerencia": None,
    }

    if not api_key:
        resultado["error_tipo"] = "API Key no configurada"
        resultado["error_mensaje"] = "TAVILY_API_KEY está vacía en .env."
        resultado["diagnostico_simple"] = "No tienes configurada la clave de Tavily."
        resultado["sugerencia"] = "Tavily es opcional pero recomendado. El sistema usará DuckDuckGo automáticamente si no tienes clave."
        return resultado

    try:
        from tavily import TavilyClient
    except ImportError as e:
        resultado["error_tipo"] = "Librería no instalada"
        resultado["error_mensaje"] = str(e)
        resultado["diagnostico_simple"] = "Falta instalar el paquete 'tavily-python'."
        resultado["sugerencia"] = "Ejecuta: pip install tavily-python"
        return resultado

    try:
        client = TavilyClient(api_key=api_key)
        today = date.today()
        month = today.month - 6
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        start_day = min(today.day, calendar.monthrange(year, month)[1])
        start_date = date(year, month, start_day).isoformat()
        res = client.search(
            query="inteligencia artificial tecnologia",
            max_results=1,
            start_date=start_date,
            end_date=today.isoformat(),
            include_published_date=True,
            filter_by_published_date=True,
        )
        results = res.get("results", [])
        if results:
            resultado["exito"] = True
            resultado["primer_resultado"] = results[0].get("title", "Resultado obtenido")
            resultado["url"] = results[0].get("url", "")
        else:
            resultado["exito"] = True
            resultado["primer_resultado"] = "Búsqueda ejecutada sin resultados para la query de prueba."
        return resultado
    except Exception as e:
        err_msg = redactar_secretos(str(e))
        resultado["error_tipo"] = type(e).__name__
        resultado["error_mensaje"] = err_msg

        if "401" in err_msg or "Unauthorized" in err_msg or "Invalid API key" in err_msg:
            resultado["diagnostico_simple"] = "Tu clave de Tavily es inválida o expiró."
            resultado["sugerencia"] = "Revisa tu clave en https://tavily.com o bórrala de .env para que el sistema use DuckDuckGo."
        elif "quota" in err_msg.lower() or "limit" in err_msg.lower() or "429" in err_msg:
            resultado["diagnostico_simple"] = "Consumiste el límite mensual de 1,000 búsquedas gratuitas de Tavily."
            resultado["sugerencia"] = "No te preocupes: el sistema pasará automáticamente a DuckDuckGo."
        else:
            resultado["diagnostico_simple"] = f"Error en Tavily: {err_msg[:120]}"
            resultado["sugerencia"] = "Si el error persiste, el sistema usará el fallback a DuckDuckGo."

        return resultado


def main():
    console.print("\n[bold cyan]🔍 DIAGNÓSTICO DE CONEXIÓN: GEMINI & TAVILY[/bold cyan]")
    console.print("[dim]Probando credenciales y conectividad de servicios externos...[/dim]\n")

    # 1. Probar Gemini
    console.print("[bold yellow]1. Probando Google Gemini...[/bold yellow]")
    res_gemini = probar_gemini()
    if res_gemini["exito"]:
        console.print(f"[bold green]   ✔ Conexión con Gemini EXITOSA[/bold green] (Modelo: [cyan]{res_gemini['modelo']}[/cyan])")
        console.print(f"   [dim]Respuesta de prueba: {res_gemini.get('respuesta_prueba')}[/dim]\n")
    else:
        console.print(f"[bold red]   ✖ Falló la conexión con Gemini[/bold red]")
        console.print(f"   [bold]Motivo simple:[/bold] [red]{res_gemini['diagnostico_simple']}[/red]")
        console.print(f"   [bold]Qué hacer:[/bold] [yellow]{res_gemini['sugerencia']}[/yellow]")
        console.print(f"   [dim]Error técnico: {res_gemini['error_tipo']}: {res_gemini['error_mensaje']}[/dim]\n")

    # 2. Probar Tavily
    console.print("[bold yellow]2. Probando Tavily Search...[/bold yellow]")
    res_tavily = probar_tavily()
    if res_tavily["exito"]:
        console.print(f"[bold green]   ✔ Conexión con Tavily EXITOSA[/bold green]")
        console.print(f"   [dim]Resultado de prueba: {res_tavily.get('primer_resultado')} ({res_tavily.get('url')})[/dim]\n")
    else:
        console.print(f"[bold red]   ✖ Falló la conexión con Tavily[/bold red]")
        console.print(f"   [bold]Motivo simple:[/bold] [red]{res_tavily['diagnostico_simple']}[/red]")
        console.print(f"   [bold]Qué hacer:[/bold] [yellow]{res_tavily['sugerencia']}[/yellow]")
        console.print(f"   [dim]Error técnico: {res_tavily['error_tipo']}: {res_tavily['error_mensaje']}[/dim]\n")

    # Resumen y veredicto
    console.print("[bold cyan]══════════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold]📋 RESUMEN GENERAL:[/bold]")
    estado_gemini = "[bold green]LISTO[/bold green]" if res_gemini["exito"] else "[bold red]REQUIERE ATENCIÓN[/bold red]"
    estado_tavily = "[bold green]LISTO[/bold green]" if res_tavily["exito"] else "[bold yellow]FALLBACK A DUCKDUCKGO[/bold yellow]"

    console.print(f" • Proveedor de IA (Gemini):  {estado_gemini}")
    console.print(f" • Búsqueda Web (Tavily):     {estado_tavily}")

    if res_gemini["exito"]:
        console.print("\n[bold green]🚀 El sistema está listo para ejecutar orquestador.py[/bold green]\n")
    else:
        console.print("\n[bold yellow]⚠️ Corrige la configuración de Gemini antes de ejecutar orquestador.py[/bold yellow]\n")


if __name__ == "__main__":
    main()
