# 🌐 Sistema Multiagente de Estudio de Mercado con IA

Un sistema autónomo de inteligencia de mercado y estrategia competitiva impulsado por **IA (Google Gemini o OpenAI)**, **búsqueda web en tiempo real (Tavily con fallback a DuckDuckGo)** y **arquitectura asíncrona pura (`asyncio`)**.

---

## 🏗️ Arquitectura del Sistema

El sistema opera bajo un modelo jerárquico y especializado compuesto por **1 Agente Orquestador** y **7 Agentes Especialistas**. Cada agente responde **SOLO una pregunta clave**, trabaja con rigurosidad analítica y produce salidas estructuradas en español.

```text
                             config.yaml
                                  │
                                  ▼
                     ┌─────────────────────────┐
                     │  Agente 0: Orquestador  │
                     └────────────┬────────────┘
                                  │
      ┌───────────────────────────┴───────────────────────────┐
      │ FASE 1: Búsqueda Web y Análisis Exterior (En Paralelo)│
      │                  asyncio.gather()                     │
      ├───────────────┬───────────────┬───────────────┬───────┴───────┐
      ▼               ▼               ▼               ▼               ▼
  [Agente 1]      [Agente 2]      [Agente 3]      [Agente 4]          │
  Cambios de      Voz del         Soluciones      Formatos y          │
  la Industria    Cliente         Innovadoras     Propuestas          │
      └───────────────┴───────┬───────┴───────────────┴───────────────┘
                              │
                              ▼
      ┌───────────────────────────────────────────────────────┐
      │ FASE 2: Diagnóstico Interno del Negocio Propio        │
      │ (Cruza el negocio del usuario con hallazgos de 1 a 4) │
      ├───────────────────────────────┬───────────────────────┤
      ▼                               ▼                       ▼
  [Agente 5]                      [Agente 6]                  │
  Riesgos y Brechas               Ideas Obsoletas             │
  (Urgencia Alta/Media/Baja)      (Mantener/Reconsiderar/Eliminar)
      └───────────────────────────────┬───────────────────────┘
                                      │
                                      ▼
      ┌───────────────────────────────────────────────────────┐
      │ FASE 3: Dirección Estratégica                         │
      │ (Sintetiza la inteligencia acumulada de 1 a 6)        │
      ├───────────────────────────────────────────────────────┤
      ▼                                                       ▼
  [Agente 7]                                                  │
  Hipótesis Estratégica (1 Principal + 2 Alternativas)        │
  + Plan de Acción Operativo a 30 Días                        │
      └───────────────────────────────┬───────────────────────┘
                                      │
                                      ▼
                      informes/informe_mercado.md
```

### Agentes y Especialidades

| Agente | Nombre | Pregunta Asignada | Enfoque de Investigación |
| :---: | :--- | :--- | :--- |
| **0** | **Orquestador** | *(Coordinación)* | Reparte datos, gestiona la concurrencia en 3 fases y compila el informe final. |
| **1** | **Cambios de la Industria** | ¿Cuáles son los cambios más significativos en mi industria en los últimos 3-6 meses? | Noticias, regulaciones, reportes, lanzamientos, inversiones y avances tecnológicos recientes. |
| **2** | **Voz del Cliente** | ¿Qué necesidades no satisfechas o frustraciones emergentes expresan los clientes en conversaciones públicas? | Foros, Reddit, reseñas en Capterra/G2, redes sociales y comunidades de usuarios. |
| **3** | **Soluciones Innovadoras** | ¿Qué nuevos actores o productos están resolviendo estas necesidades de manera no obvia y qué hacen diferente? | Startups emergentes, innovaciones *cross-industry* y modelos disruptivos vs incumbentes. |
| **4** | **Formatos y Propuestas** | ¿Qué formatos de producto, modelos de entrega o propuestas de valor están ganando tracción ahora? | Precios basados en uso, modelos freemium, Product-Led Growth (PLG), comunidades y tracción real. |
| **5** | **Riesgos y Brechas** | ¿Qué riesgos o brechas existen en mi enfoque actual desde esta nueva perspectiva del mercado? | Auditoría crítica de vulnerabilidades propias clasificadas por urgencia (Alta, Media, Baja). |
| **6** | **Ideas Obsoletas** | ¿Qué ideas o tendencias han perdido relevancia y deberían reconsiderarse o eliminarse? | Identificación de dogmas caídos recomendando: `[MANTENER]`, `[RECONSIDERAR]` o `[ELIMINAR]`. |
| **7** | **Hipótesis Estratégica** | ¿Cuál es una hipótesis estratégica de alto impacto y poco convencional que debería explorar o probar en mi negocio? | 1 hipótesis directriz + 2 alternativas con experimento ágil a 30 días, métricas y mitigación. |

---

## 📐 Reglas Estrictas de Salida

Cada agente cumple con cuatro estándares de calidad analítica:
1. **Separación de HECHOS e INTERPRETACIONES**: Todo dato fáctico se etiqueta como `[HECHO]` citando su fuente con enlace Markdown y fecha; la deducción estratégica se etiqueta como `*Interpretación*`.
2. **Honestidad Intelectual**: Si no hay evidencia en la web, el agente lo declara abiertamente. Nunca inventa datos ni URLs.
3. **Formato Obligatorio**:
   - Resumen Ejecutivo en exactamente 3 líneas.
   - Máximo 5 hallazgos clave con citas.
   - Nivel de Confianza (Alto / Medio / Bajo) con justificación.
   - Qué dato falta para mejorar la respuesta.
4. **Idioma**: Salida 100% en español ejecutivo.

---

## 📂 Estructura del Proyecto

```text
tendencia/
├── .env.example              # Plantilla de variables de entorno y API keys
├── .env                      # Tus claves locales (no incluir en repositorios públicos)
├── config.yaml               # Datos de entrada del usuario (industria, negocio, país)
├── requirements.txt          # Dependencias de Python
├── README.md                 # Guía paso a paso
├── orquestador.py            # Agente 0: Punto de entrada y orquestador
├── agentes/
│   ├── __init__.py
│   ├── base_agent.py         # Clase base con llamadas async a LLM y búsqueda web
│   ├── agente_01_industria.py
│   ├── agente_02_cliente.py
│   ├── agente_03_soluciones.py
│   ├── agente_04_formatos.py
│   ├── agente_05_riesgos.py
│   ├── agente_06_obsoleto.py
│   └── agente_07_hipotesis.py
└── informes/
    └── informe_mercado.md    # Informe final compilado automáticamente en Markdown
```

---

## 🚀 Guía de Instalación y Ejecución

### Paso 1: Clonar o abrir la carpeta del proyecto
Abre una terminal (PowerShell, CMD o bash) en el directorio `tendencia`:
```bash
cd tendencia
```

### Paso 2: Crear y activar entorno virtual
En Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(Si usas CMD escribe `venv\Scripts\activate.bat`, o en macOS/Linux `source venv/bin/activate`)*

### Paso 3: Instalar dependencias
```bash
pip install -r requirements.txt
```

### Paso 4: Configurar tus claves en `.env`
Copia o edita el archivo `.env`:
```env
# ========================================================
# LLM (GEMINI RECOMENDADO O OPENAI)
# ========================================================
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...tu_clave_aqui
GEMINI_MODEL=gemini-3.5-flash

# ========================================================
# BÚSQUEDA WEB (TAVILY CON FALLBACK A DUCKDUCKGO)
# ========================================================
TAVILY_API_KEY=tvly-...tu_clave_aqui
SEARCH_PROVIDER=tavily
```
> **Nota sobre API Keys**:
> - **Google Gemini**: Clave gratuita en [Google AI Studio](https://aistudio.google.com/).
> - **Tavily Search**: Clave gratuita (1,000 búsquedas/mes) en [tavily.com](https://tavily.com). Si dejas `TAVILY_API_KEY` vacío o se agotan las peticiones, el sistema conmuta automáticamente a DuckDuckGo sin interrumpir el análisis.
> - Si prefieres usar **OpenAI GPT-4o**, ajusta `LLM_PROVIDER=openai` y coloca tu `OPENAI_API_KEY`.
> - `GEMINI_MODEL` permite seleccionar el modelo; el valor predeterminado es `gemini-3.5-flash`.

### Paso 5: Personalizar tu negocio en `config.yaml`
Abre `config.yaml` con cualquier editor y define tu negocio:
```yaml
# Industria o sector a investigar
industria: "Tu industria aquí"

# Descripción detallada de tu negocio o producto actual
descripcion_negocio: >
  Describe qué hace tu producto, cómo cobra, quién es tu cliente ideal
  y qué problema resuelves actualmente.

# País o mercado objetivo
pais: "México y Colombia (Latinoamérica)"

# Ventana de análisis
ventana_analisis: "últimos 3 a 6 meses"
```

---

## ⚡ Ejecución

### 1. Ejecución Completa en Vivo
```bash
python orquestador.py
```
El sistema iniciará la interfaz visual interactiva en consola mostrando:
- Ficha técnica inicial.
- Progreso en tiempo real con barras y spinners por fase.
- Tabla final con tiempos de procesamiento y nivel de confianza de cada agente.
- Generación de `informes/informe_mercado.md`.

### 2. Modo Simulación / Prueba Rápida (Sin consumir APIs)
Para verificar que el flujo, la interfaz y el compilador de Markdown funcionan sin gastar tokens de búsqueda ni de LLM:
```bash
python orquestador.py --mock
```

### 3. Interfaz web con Streamlit
Instala las dependencias con `pip install -r requirements.txt` y, desde la raíz del proyecto, inicia:
```bash
streamlit run app.py
```
La interfaz precarga los datos de `config.yaml`. En modo simulación no consume APIs; también permite abrir el último informe guardado o ejecutar un único agente. Cada resultado se guarda en `informes/cache/` para reutilizarlo. La ejecución real solicita confirmación de las llamadas estimadas y necesita `APP_PASSWORD` configurada en `.streamlit/secrets.toml` bajo la clave `APP_PASSWORD`; la app pide esa contraseña antes de mostrar la interfaz. Nunca publiques ni subas ese archivo al repositorio.

Ejemplo local de `.streamlit/secrets.toml` (no lo añadas a Git):
```toml
APP_PASSWORD = "elige-una-contraseña-larga"
GEMINI_API_KEY = "tu-clave-de-gemini"
TAVILY_API_KEY = "tu-clave-de-tavily"
```
La aplicación toma las claves de variables de entorno o de `st.secrets`, solo las utiliza durante las llamadas y no las muestra en la interfaz.

### 4. Usar un Archivo de Configuración Alternativo
```bash
python orquestador.py --config otro_negocio.yaml --output informes/informe_otro_negocio.md
```

---

## 📄 Contenido del Informe Generado (`informe_mercado.md`)

El reporte final incluye:
1. **Ficha Técnica**: Negocio, industria, país, fecha, ventana de análisis y modelo de IA utilizado.
2. **Resumen Ejecutivo Transversal**: Matriz 360° con los resúmenes en 3 líneas y niveles de confianza de los 7 especialistas.
3. **Investigación Externa (Agentes 1 a 4)**: Cambios en el mercado, quejas y deseos del cliente, startups disruptivas y modelos de monetización emergentes.
4. **Auditoría Interna (Agentes 5 y 6)**: Puntos ciegos clasificados por nivel de urgencia (`ALTA`, `MEDIA`, `BAJA`) y supuestos obsoletos (`MANTENER`, `RECONSIDERAR`, `ELIMINAR`).
5. **Dirección Estratégica (Agente 7)**:
   - 1 Hipótesis Principal de alto impacto no obvia.
   - 2 Hipótesis Alternativas de respaldo.
   - Especificación detallada de: *Qué probar*, *Experimento de 30 días*, *Métricas de éxito* y *Riesgos*.
6. **Plan de Acción Operativo a 30 Días**: Hoja de ruta dividida en 4 semanas (Setup, Smoke Test, Piloto en Vivo, Evaluación Go/No-Go).
7. **Directorio de Fuentes Consultadas**: Lista unificada de enlaces con fecha.

---

## 🛠️ Decisiones de Ingeniería y Arquitectura

- **Asyncio Puro sin Frameworks Pesados**: Prescinde de dependencias opacas (como LangChain o CrewAI) para ofrecer un código transparente, trazable y fácil de auditar.
- **Control de cuota de Gemini**: Se ejecutan como máximo 2 agentes simultáneos y 4 llamadas a Gemini por minuto de forma global. Los errores 429/`RESOURCE_EXHAUSTED` se reintentan hasta 4 veces usando el `retryDelay` del servicio más 2 segundos y espera exponencial. La consola informa cuándo espera por cuota.
- **Respuestas completas**: Los agentes solicitan hasta 16.384 tokens; cuando Gemini indica `MAX_TOKENS`, pide continuaciones y concatena los fragmentos. Si aun así no termina, el informe marca la sección como `RESPUESTA TRUNCADA`.
- **Fechas verificables**: Tavily recibe `start_date` y `end_date` para la ventana móvil de seis meses, junto con `include_published_date` y `filter_by_published_date`. El formato sigue la [documentación oficial de búsqueda de Tavily](https://docs.tavily.com/documentation/api-reference/endpoint/search); el anexo presenta las fechas en español.
- **Citas y honestidad**: Los enlaces se conservan solo si coinciden exactamente con una URL de las fuentes recopiladas. Un hecho sin enlace válido pasa a interpretación marcada como «sin fuente». Precios, conversiones y otras cifras hipotéticas deben indicarse como «Supuesto a validar».
- **Concurrencia No Bloqueante**: Como los SDKs de Google Gemini y Tavily tienen llamadas I/O síncronas, se despachan mediante `loop.run_in_executor` en un ThreadPool sin bloquear el bucle de eventos.
- **Resiliencia en Búsqueda (Fallback Automático)**: Si Tavily falla por cuota o latencia de red, DuckDuckGo intenta buscar fuentes fechadas dentro de la misma ventana temporal.
- **Aislamiento de Contexto en Fases**: Los Agentes 1 a 4 investigan de forma estrictamente neutral el mercado externo. Los Agentes 5 y 6 reciben esa síntesis para auditar el negocio propio sin sesgar la fase 1. El Agente 7 consolida ambas perspectivas para formular la hipótesis.
- **Informe honesto**: Si falla un agente, el informe muestra `SECCIÓN NO GENERADA`; el Agente 7 advierte qué secciones faltaron. Los fallos y truncamientos quedan resumidos en terminal sin declarar que la ejecución se completó correctamente.
