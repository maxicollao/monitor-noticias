# ═══════════════════════════════════════════════════════════════
#  ROMÁN V2 — Monitor de Noticias Max Collao
#  Versión: 2.0
#  Cambios desde V1:
#    - Bug JSON corregido (content[] vacío, no "Sin resultados")
#    - Botones inline de Telegram (Ignorar / Resumen / Libreto / Opus)
#    - Umbral score: 7 → 8
#    - Prompt limita a solo metadatos (no abre artículos)
#    - Libreto directo como texto en Telegram (sin subprocess, sin HTML)
#    - Opus SOLO si Max toca el botón manualmente
#    - Rutas compatibles con Railway y Windows
#    - Logs estructurados por corrida
# ═══════════════════════════════════════════════════════════════

import requests
import json
import time
import os
from datetime import datetime, timedelta

# ─── CONFIGURACIÓN ────────────────────────────────────────────

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_TOKEN",    "8436226379:AAHsZSIIaMb6ROvHvypm4Cdn3vqWg-aARJo")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",  "8309799765")

INTERVALO_HORAS      = 6     # corrida de monitoreo cada 6 horas
EXPIRACION_MINUTOS   = 120   # alertas vigentes 2 horas
CHECK_TELEGRAM_SEG   = 10    # revisar Telegram cada 10 segundos
SCORE_MINIMO         = 8     # solo alertas con urgencia >= 8

# Ruta compatible con Railway (Linux) y Windows
BASE_DIR   = os.environ.get("BASE_DIR", os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(BASE_DIR, "roman_estado.json")


# ─── LOGGING ──────────────────────────────────────────────────

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def log_separador(titulo=""):
    ts = datetime.now().strftime("%H:%M:%S")
    linea = "─" * 44
    if titulo:
        print(f"[{ts}] {linea}", flush=True)
        print(f"[{ts}] {titulo}", flush=True)
    print(f"[{ts}] {linea}", flush=True)


# ─── ESTADO PERSISTENTE ───────────────────────────────────────
# Guarda alertas y posición de Telegram en un JSON en disco.
# Así si Railway reinicia el proceso, las alertas no se pierden.

def cargar_estado():
    base = {"next_alerta": 1, "last_update_id": 0, "alertas": []}
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            base.update(data)
    except Exception as e:
        log(f"Error cargando estado: {e}")
    return base

def guardar_estado(estado):
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Error guardando estado: {e}")

def ahora_iso():
    return datetime.now().isoformat(timespec="seconds")


# ─── ALERTAS ──────────────────────────────────────────────────

def crear_alerta(estado, tema_data):
    numero = estado.get("next_alerta", 1)
    estado["next_alerta"] = numero + 1
    alerta = {
        "numero":       numero,
        "tema":         tema_data.get("tema", ""),
        "bajada":       tema_data.get("bajada", ""),
        "fuente":       tema_data.get("fuente", ""),
        "hora_noticia": tema_data.get("hora_noticia", ""),
        "link":         tema_data.get("link", ""),
        "urgencia":     tema_data.get("urgencia", 0),
        "categoria":    tema_data.get("categoria", ""),
        "por_que_ahora":tema_data.get("por_que_ahora", ""),
        "razon":        tema_data.get("razon", ""),
        "creada":       ahora_iso(),
        "estado":       "pendiente",
        "modelo_usado": None
    }
    estado.setdefault("alertas", []).append(alerta)
    guardar_estado(estado)
    return alerta

def esta_expirada(alerta):
    try:
        creada = datetime.fromisoformat(alerta["creada"])
        return datetime.now() > creada + timedelta(minutes=EXPIRACION_MINUTOS)
    except Exception:
        return True

def buscar_alerta(estado, numero):
    for a in estado.get("alertas", []):
        if str(a.get("numero")) == str(numero):
            return a
    return None

def marcar_expiradas(estado):
    cambio = False
    for a in estado.get("alertas", []):
        if a.get("estado") == "pendiente" and esta_expirada(a):
            a["estado"] = "vencido"
            cambio = True
    if cambio:
        guardar_estado(estado)


# ─── TELEGRAM — ENVÍO ─────────────────────────────────────────

def enviar_telegram(mensaje):
    """Envía un mensaje de texto a Telegram."""
    # Telegram limita mensajes a 4096 caracteres.
    # Si el mensaje es más largo, lo dividimos automáticamente.
    LIMITE = 4000

    if len(mensaje) <= LIMITE:
        _enviar_bloque(mensaje)
    else:
        # Dividir en partes conservando HTML válido
        partes = []
        while len(mensaje) > LIMITE:
            partes.append(mensaje[:LIMITE])
            mensaje = mensaje[LIMITE:]
        if mensaje:
            partes.append(mensaje)

        total = len(partes)
        for i, parte in enumerate(partes, 1):
            sufijo = f"\n\n<i>[{i}/{total}]</i>" if total > 1 else ""
            _enviar_bloque(parte + sufijo)
            if i < total:
                time.sleep(0.8)  # pausa entre mensajes para no saturar

def _enviar_bloque(texto):
    """Envía un único bloque de texto a Telegram."""
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id":    TELEGRAM_CHAT_ID,
                "text":       texto,
                "parse_mode": "HTML"
            },
            timeout=15
        )
        if r.status_code == 200:
            log("Mensaje enviado ✅")
        else:
            log(f"Error Telegram {r.status_code}: {r.text[:120]}")
    except Exception as e:
        log(f"Error Telegram: {e}")

def enviar_alerta_con_botones(alerta):
    """Envía la alerta con los 4 botones inline."""
    n = alerta["numero"]
    mensaje = (
        f"🚨 <b>ALERTA {n} — ROMÁN</b>\n\n"
        f"📰 <b>Tema:</b> {alerta['tema']}\n"
        f"🔥 <b>Score:</b> {alerta['urgencia']}/10\n"
        f"📂 <b>Categoría:</b> {alerta['categoria']}\n"
        f"⚡ <b>Por qué ahora:</b> {alerta['por_que_ahora']}\n"
        f"🎯 <b>Para Max:</b> {alerta['razon']}\n"
    )
    if alerta.get("fuente"):
        mensaje += f"📡 <b>Fuente:</b> {alerta['fuente']}\n"
    if alerta.get("hora_noticia"):
        mensaje += f"🕐 <b>Hora:</b> {alerta['hora_noticia']}\n"
    if alerta.get("link"):
        mensaje += f"🔗 {alerta['link']}\n"

    mensaje += f"\n⏳ Disponible por {EXPIRACION_MINUTOS} minutos."

    teclado = {
        "inline_keyboard": [
            [
                {"text": "🚫 Ignorar",         "callback_data": f"ignorar|{n}"},
                {"text": "📋 Resumen",          "callback_data": f"resumen|{n}"},
            ],
            [
                {"text": "🎙️ Libreto Sonnet",  "callback_data": f"libreto|{n}"},
                {"text": "⚡ MODO OPUS",        "callback_data": f"opus|{n}"},
            ]
        ]
    }
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id":    TELEGRAM_CHAT_ID,
                "text":       mensaje,
                "parse_mode": "HTML",
                "reply_markup": teclado
            },
            timeout=15
        )
        if r.status_code == 200:
            log(f"Alerta {n} enviada con botones ✅")
        else:
            log(f"Error enviando alerta con botones: {r.text[:150]}")
    except Exception as e:
        log(f"Error enviando alerta: {e}")

def confirmar_callback(callback_query_id, texto="✅"):
    """Elimina el ícono de carga del botón en Telegram."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": texto},
            timeout=10
        )
    except Exception as e:
        log(f"Error confirmando callback: {e}")

def enviar_alerta_tecnica(detalle):
    """Alerta al chat cuando hay un error interno importante."""
    enviar_telegram(f"⚠️ <b>ROMÁN — Error técnico</b>\n<code>{str(detalle)[:300]}</code>")

def sincronizar_telegram(estado):
    """Al iniciar, ignora mensajes viejos para que no activen nada."""
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"timeout": 1},
            timeout=10
        )
        updates = r.json().get("result", [])
        if updates:
            estado["last_update_id"] = max(u.get("update_id", 0) for u in updates)
            guardar_estado(estado)
            log(f"Telegram sincronizado (ignorando hasta update {estado['last_update_id']})")
    except Exception as e:
        log(f"No pude sincronizar Telegram: {e}")


# ─── LLAMADA CENTRALIZADA A ANTHROPIC API ─────────────────────
# Esta función maneja correctamente el ciclo web_search:
#   1. API responde stop_reason="tool_use" (quiere buscar algo)
#   2. Enviamos tool_result con content=[] (Anthropic ejecuta la búsqueda)
#   3. API responde stop_reason="end_turn" con el texto final

def llamar_anthropic(modelo, max_tokens, prompt, usar_websearch=False):
    """
    Llama a la API de Anthropic y retorna el texto de respuesta.
    Maneja el ciclo tool_use automáticamente.
    Retorna None si hay error.
    """
    headers = {
        "x-api-key":         ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type":      "application/json"
    }
    if usar_websearch:
        headers["anthropic-beta"] = "web-search-2025-03-05"

    body = {
        "model":      modelo,
        "max_tokens": max_tokens,
        "messages":   [{"role": "user", "content": prompt}]
    }
    if usar_websearch:
        body["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]

    messages = [{"role": "user", "content": prompt}]

    for intento in range(6):
        body["messages"] = messages
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
                timeout=120
            )
            data = r.json()
        except Exception as e:
            log(f"Error de red en intento {intento+1}: {e}")
            time.sleep(5)
            continue

        if "error" in data:
            log(f"API error ({modelo}): {data['error'].get('message','')[:100]}")
            return None

        content     = data.get("content", [])
        stop_reason = data.get("stop_reason", "")

        if stop_reason == "end_turn":
            texto = "".join(
                b.get("text", "") for b in content if b.get("type") == "text"
            ).strip()
            return texto if texto else None

        if stop_reason == "tool_use":
            # El modelo quiere hacer una búsqueda web.
            # Enviamos tool_result con content=[] para que Anthropic
            # ejecute la búsqueda server-side y continúe.
            messages.append({"role": "assistant", "content": content})
            tool_results = []
            for bloque in content:
                if bloque.get("type") == "tool_use":
                    tool_results.append({
                        "type":         "tool_result",
                        "tool_use_id":  bloque.get("id"),
                        "content":      []   # ← FIX: no "Sin resultados"
                    })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            continue  # siguiente intento con el historial actualizado

        break  # stop_reason inesperado — salir del loop

    log("Sin respuesta válida tras varios intentos")
    return None


# ─── DETECCIÓN DE NOTICIAS (HAIKU + WEB SEARCH) ───────────────

def detectar_temas_urgentes():
    """
    Corrida de monitoreo cada 6 horas.
    Usa Haiku + web_search.
    Lee SOLO metadatos: titular, bajada, fuente, hora, link.
    NO abre artículos completos.
    Retorna dict con temas encontrados.
    """
    hora  = datetime.now().strftime("%H:%M")
    fecha = datetime.now().strftime("%d/%m/%Y")

    prompt = f"""Es {fecha} a las {hora} hora Chile. Busca en internet las noticias más urgentes y virales de Chile ahora mismo.

INSTRUCCIÓN CRÍTICA: Usa SOLO los metadatos que entrega el buscador: titular, bajada o descripción breve, fuente, hora de publicación y URL. NO abras artículos completos. NO hagas fetch de URLs individuales. Si con los metadatos no hay información suficiente para evaluar la noticia, ignórala y pasa a la siguiente.

Fuentes: BioBioChile, La Tercera, Emol, CHV Noticias, Mega, Twitter/X Chile tendencias, TikTok Chile.

Busca:
- Escándalos de farándula chilena (peleas, revelaciones, suspensiones)
- Estafas o denuncias que afecten a chilenos comunes
- Virales de TikTok o redes sociales en Chile
- Noticias de TV chilena explotando AHORA
- Cualquier tema reventando en redes chilenas en este momento

Contexto: Max Collao es ex periodista TV chilena (TVN, Canal 13, CHV, 14 años). Ahora creador digital con 117K seguidores en Instagram @maxcollao. Le conviene farándula con ángulo comunicacional, denuncias de estafas, y virales chilenos.

RESPONDE SOLO EN JSON PURO. Sin texto antes ni después. Sin bloques de código. Sin triple backtick.

{{
  "hay_urgente": true,
  "temas": [
    {{
      "tema": "nombre exacto con nombres reales",
      "bajada": "bajada o descripción breve si existe, vacío si no",
      "fuente": "nombre del medio",
      "hora_noticia": "hora de publicación si existe, vacío si no",
      "link": "URL del artículo si existe, vacío si no",
      "urgencia": 9,
      "categoria": "denuncia/farandula/viral/politica/deporte",
      "por_que_ahora": "razón específica con datos reales de por qué es urgente HOY",
      "conviene_a_max": true,
      "razon": "por qué le conviene a Max Collao específicamente"
    }}
  ],
  "recomendacion": "hacer contenido urgente"
}}"""

    log("Detectando noticias (Haiku + web search)...")
    raw_backup = ""

    try:
        headers = {
            "x-api-key":         ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "anthropic-beta":    "web-search-2025-03-05",
            "Content-Type":      "application/json"
        }
        messages = [{"role": "user", "content": prompt}]

        for intento in range(6):
            try:
                r = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json={
                        "model":      "claude-haiku-4-5-20251001",
                        "max_tokens": 2000,
                        "tools":      [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages":   messages
                    },
                    timeout=120
                )
                data = r.json()
            except Exception as e:
                log(f"Error de red intento {intento+1}: {e}")
                time.sleep(5)
                continue

            if "error" in data:
                log(f"API error: {data['error'].get('message','')[:100]}")
                return {"hay_urgente": False, "temas": [], "recomendacion": "error_api"}

            content     = data.get("content", [])
            stop_reason = data.get("stop_reason", "")

            # ─── Respuesta final: parsear JSON ─────────────────
            if stop_reason == "end_turn":
                texto = "".join(
                    b.get("text", "") for b in content if b.get("type") == "text"
                ).strip()
                raw_backup = texto  # guardar ANTES de parsear

                if not texto:
                    log("Respuesta vacía del modelo")
                    return {"hay_urgente": False, "temas": [], "recomendacion": "vacia"}

                # Limpiar bloques de código si el modelo los añadió igual
                if "```" in texto:
                    partes = texto.split("```")
                    for parte in partes:
                        parte = parte.replace("json", "").strip()
                        if parte.startswith("{"):
                            texto = parte
                            break

                # Extraer solo el bloque JSON
                if "{" in texto:
                    texto = texto[texto.index("{"):texto.rindex("}") + 1]

                # Parsear con respaldo y alerta técnica
                try:
                    return json.loads(texto)
                except json.JSONDecodeError as e:
                    log(f"Error parseando JSON: {e}")
                    log(f"RAW (primeros 400 chars): {raw_backup[:400]}")
                    enviar_alerta_tecnica(
                        f"Bug JSON en corrida de detección\n"
                        f"Error: {str(e)[:100]}\n"
                        f"RAW: {raw_backup[:150]}"
                    )
                    return {"hay_urgente": False, "temas": [], "recomendacion": "error_json"}

            # ─── El modelo quiere buscar: continuar el ciclo ────
            if stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": content})
                tool_results = []
                for bloque in content:
                    if bloque.get("type") == "tool_use":
                        # FIX DEL BUG: content=[] en vez de "Sin resultados"
                        tool_results.append({
                            "type":        "tool_result",
                            "tool_use_id": bloque.get("id"),
                            "content":     []
                        })
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                continue

            break  # stop_reason inesperado

        log("Sin JSON tras varios intentos")
        return {"hay_urgente": False, "temas": [], "recomendacion": "sin_respuesta"}

    except Exception as e:
        log(f"Error en detección: {e}")
        return {"hay_urgente": False, "temas": [], "recomendacion": "error_excepcion"}


# ─── GENERACIÓN DE CONTENIDO ──────────────────────────────────

def _contexto_alerta(alerta):
    """Texto de contexto común para todos los prompts de generación."""
    lineas = [
        f"TEMA: {alerta['tema']}",
        f"BAJADA: {alerta.get('bajada') or 'No disponible'}",
        f"FUENTE: {alerta.get('fuente') or 'No disponible'}",
        f"HORA: {alerta.get('hora_noticia') or 'No disponible'}",
        f"LINK: {alerta.get('link') or 'No disponible'}",
        f"POR QUÉ AHORA: {alerta['por_que_ahora']}",
        f"ÁNGULO PARA MAX: {alerta['razon']}",
        f"CATEGORÍA: {alerta['categoria']}",
    ]
    return "\n".join(lineas)


def generar_resumen_haiku(alerta):
    """Resumen periodístico rápido. Modelo: Haiku."""
    n = alerta["numero"]
    log(f"Generando resumen Haiku → Alerta {n}")

    prompt = f"""Eres el asistente de Max Collao. Ex periodista TV chilena 14 años. Creador digital 117K Instagram @maxcollao.

Genera un resumen periodístico breve sobre este tema para que Max decida si grabar:

{_contexto_alerta(alerta)}

ESTRUCTURA EXACTA:

📰 QUÉ PASÓ
[2-3 líneas con los hechos clave, sin especulación]

🔥 POR QUÉ IMPORTA
[1-2 líneas, ángulo emocional para la audiencia chilena]

🎯 ÁNGULO PARA MAX
[1-2 líneas, cómo abordarlo con su estilo periodístico]

⏰ URGENCIA: {alerta['urgencia']}/10

Español chileno natural. Nunca argentinismos. Directo."""

    enviar_telegram(f"⏳ Generando resumen para <b>Alerta {n}</b>...")
    texto = llamar_anthropic("claude-haiku-4-5-20251001", 800, prompt)

    if texto:
        enviar_telegram(
            f"📋 <b>RESUMEN — Alerta {n}</b>\n"
            f"<i>Modelo: Haiku</i>\n\n"
            f"{texto}"
        )
        log(f"Resumen enviado ✅ — Haiku")
    else:
        enviar_telegram(f"⚠️ No pude generar el resumen para Alerta {n}.")
        log("Error: resumen Haiku vacío")


def generar_libreto_sonnet(alerta):
    """Libreto completo para reel/video. Modelo: Sonnet."""
    n = alerta["numero"]
    log(f"Generando libreto Sonnet → Alerta {n}")

    prompt = f"""Eres el jefe de contenido y guionista de Max Collao. Ex periodista TV chilena 14 años (TVN, Canal 13, CHV). Creador digital 117K Instagram @maxcollao.

Genera el libreto completo para que Max grabe AHORA:

{_contexto_alerta(alerta)}

REGLAS DE ESTILO:
- Español chileno natural, nunca argentinismos
- Astuto, periodístico, sin ataques directos a personas
- Ángulo: la voz de los que no tienen voz
- Nunca mencionar TV, teleprompter ni matinal
- Este tema tiene máximo 24 horas de vida útil

═══════════════════════════════════════
🎙️ LIBRETO URGENTE — {alerta['tema']}
═══════════════════════════════════════

📱 VERSIÓN REEL/SHORT (60 segundos)

Hook — primeras 3 palabras que detienen el scroll:
[texto exacto]

Desarrollo — lo que dice Max palabra por palabra:
[texto con ritmo, pausas marcadas con / /]

Cierre y CTA:
[texto exacto]

📹 PRODUCCIÓN:
Cámara: [frente / selfie / walking]
Locación: [dónde grabarlo ahora mismo]
Texto en pantalla: [texto superpuesto]
Hashtags: [5-8 hashtags]
Publicar en: [orden de redes]

🎬 VERSIÓN YOUTUBE (5-8 min, si aplica)

Hook primeros 30 seg:
Introducción del caso (1 min):
Desarrollo — 3 puntos:
  Punto 1:
  Punto 2:
  Punto 3:
Cierre emocional y CTA:

⚠️ GRABAR HOY. Máximo 24 horas de vida."""

    enviar_telegram(f"⏳ Generando libreto para <b>Alerta {n}</b>...")
    texto = llamar_anthropic("claude-sonnet-4-5", 4000, prompt)

    if texto:
        enviar_telegram(
            f"🎙️ <b>LIBRETO — Alerta {n}</b>\n"
            f"<i>Modelo: Sonnet</i>\n\n"
            f"{texto}"
        )
        log(f"Libreto enviado ✅ — Sonnet")
    else:
        enviar_telegram(f"⚠️ No pude generar el libreto para Alerta {n}.")
        log("Error: libreto Sonnet vacío")


def generar_libreto_opus(alerta):
    """
    Libreto extendido. Modelo: Opus.
    ⚠️  SOLO se ejecuta cuando Max toca el botón manualmente.
    Nunca en ejecución automática.
    """
    n = alerta["numero"]
    log(f"⚡ MODO OPUS activado manualmente → Alerta {n}")
    log(f"Modelo: claude-opus-4-5")

    prompt = f"""Eres el jefe de contenido y guionista senior de Max Collao. Ex periodista TV chilena 14 años (TVN, Canal 13, CHV). Creador digital 117K Instagram @maxcollao.

Max activó el MODO OPUS. Desarrolla al máximo este tema:

{_contexto_alerta(alerta)}

REGLAS DE ESTILO:
- Español chileno natural, nunca argentinismos
- Astuto, periodístico, sin ataques directos
- Ángulo: la voz de los que no tienen voz
- Nunca mencionar TV, teleprompter ni matinal
- Máximo 24 horas de vida útil

═══════════════════════════════════════
⚡ MODO OPUS — {alerta['tema']}
═══════════════════════════════════════

📊 ANÁLISIS COMPLETO
Contexto, antecedentes, protagonistas, datos relevantes para entender el tema a fondo.

🎙️ LIBRETO REEL/SHORT (60-90 segundos)
Hook exacto / Desarrollo con ritmo / Cierre y CTA.

🎬 LIBRETO YOUTUBE LARGO (8-12 minutos)
Hook 30 seg / Intro 1 min / Desarrollo 3 puntos detallados / Contexto histórico o estadístico / Cierre emocional / CTA.

📱 ESTRATEGIA DE DISTRIBUCIÓN
Plataformas en orden / Horarios óptimos / Adaptaciones por red.

📊 ANÁLISIS DE VIRALIDAD
Potencial 1-10 con justificación / Riesgos / Oportunidades de seguimiento.

⚠️ GRABAR HOY. Máximo 24 horas de vida."""

    enviar_telegram(
        f"⚡ <b>MODO OPUS activado</b>\n"
        f"Generando análisis extendido para <b>Alerta {n}</b>...\n"
        f"<i>Esto puede tomar 2-3 minutos.</i>"
    )
    texto = llamar_anthropic("claude-opus-4-5", 8000, prompt)

    if texto:
        enviar_telegram(
            f"⚡ <b>MODO OPUS — Alerta {n}</b>\n"
            f"<i>Modelo: Opus</i>\n\n"
            f"{texto}"
        )
        log(f"Libreto Opus enviado ✅ — claude-opus-4-5")
    else:
        enviar_telegram(f"⚠️ No pude generar el libreto Opus para Alerta {n}.")
        log("Error: libreto Opus vacío")


# ─── PROCESAMIENTO DE BOTONES (CALLBACK_QUERY) ────────────────

def procesar_callback(estado, callback):
    """
    Se ejecuta cuando Max toca uno de los botones inline.
    Extrae la acción y el número de alerta del callback_data.
    """
    callback_id = callback.get("id")
    data_cb     = callback.get("data", "")
    # Verificar que el mensaje viene del chat correcto
    chat_id     = str(callback.get("message", {}).get("chat", {}).get("id", ""))

    if chat_id != str(TELEGRAM_CHAT_ID):
        confirmar_callback(callback_id, "No autorizado")
        return

    # Confirmar inmediatamente para eliminar el ícono de carga del botón
    confirmar_callback(callback_id, "Recibido ✅")

    if "|" not in data_cb:
        log(f"Callback con formato inesperado: {data_cb}")
        return

    accion, numero_str = data_cb.split("|", 1)
    alerta = buscar_alerta(estado, numero_str)
    log(f"Callback: [{accion}] → Alerta {numero_str}")

    # Verificar que la alerta existe
    if not alerta:
        enviar_telegram(f"⚠️ No encontré la Alerta {numero_str}. Puede haber expirado.")
        return

    # Verificar que no está ya procesada o ignorada
    if alerta.get("estado") == "ignorado":
        enviar_telegram(f"🚫 La Alerta {numero_str} ya fue ignorada.")
        return

    # Verificar que no expiró
    if alerta.get("estado") == "vencido" or esta_expirada(alerta):
        alerta["estado"] = "vencido"
        guardar_estado(estado)
        enviar_telegram(
            f"⏰ <b>Alerta {numero_str} expirada.</b>\n"
            f"Tenía {EXPIRACION_MINUTOS} min de vida.\n"
            f"Si el tema sigue siendo relevante, espera la próxima corrida con datos frescos."
        )
        return

    # ─── Ejecutar acción según botón ───────────────────────────
    if accion == "ignorar":
        alerta["estado"] = "ignorado"
        guardar_estado(estado)
        enviar_telegram(f"🚫 Alerta {numero_str} ignorada.")
        log(f"Alerta {numero_str} → ignorada")

    elif accion == "resumen":
        generar_resumen_haiku(alerta)
        # El resumen no cierra la alerta — Max puede pedir libreto después

    elif accion == "libreto":
        generar_libreto_sonnet(alerta)
        alerta["estado"]       = "generado"
        alerta["modelo_usado"] = "claude-sonnet-4-5"
        guardar_estado(estado)

    elif accion == "opus":
        # ⚠️ GUARDIA: Opus solo desde este punto, nunca automático
        generar_libreto_opus(alerta)
        alerta["estado"]       = "generado"
        alerta["modelo_usado"] = "claude-opus-4-5"
        guardar_estado(estado)

    else:
        log(f"Acción desconocida: {accion}")


# ─── POLLING DE TELEGRAM ──────────────────────────────────────

def revisar_telegram(estado):
    """
    Revisa actualizaciones de Telegram.
    Procesa tanto botones (callback_query) como mensajes de texto.
    """
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={
                "timeout": 1,
                "offset":  estado.get("last_update_id", 0) + 1
            },
            timeout=15
        )
        updates = r.json().get("result", [])
        if not updates:
            return

        for update in updates:
            uid = update.get("update_id", 0)
            estado["last_update_id"] = max(estado.get("last_update_id", 0), uid)

            # Botón inline tocado por Max
            if "callback_query" in update:
                procesar_callback(estado, update["callback_query"])
                continue

            # Mensaje de texto (compatibilidad — ya no necesario, pero no rompe nada)
            mensaje = update.get("message") or update.get("edited_message") or {}
            chat_id = str(mensaje.get("chat", {}).get("id", ""))
            if chat_id != str(TELEGRAM_CHAT_ID):
                continue
            texto = (mensaje.get("text") or "").strip()
            if texto:
                log(f"Texto recibido: '{texto}' (usa los botones inline)")

        guardar_estado(estado)

    except Exception as e:
        log(f"Error revisando Telegram: {e}")


# ─── CORRIDA DE MONITOREO ─────────────────────────────────────

def correr_revision(estado):
    log_separador("ROMÁN — CORRIDA INICIADA")

    datos = detectar_temas_urgentes()

    total        = len(datos.get("temas", []))
    temas_validos = [
        t for t in datos.get("temas", [])
        if t.get("conviene_a_max") and t.get("urgencia", 0) >= SCORE_MINIMO
    ]
    descartados  = total - len(temas_validos)
    enviados     = 0

    log(f"Titulares revisados:      {total}")
    log(f"Descartados (score < {SCORE_MINIMO}): {descartados}")
    log(f"Artículo completo abierto: NO")

    if datos.get("hay_urgente") and temas_validos:
        for tema in temas_validos[:2]:  # máximo 2 alertas por corrida
            alerta = crear_alerta(estado, tema)
            log(f"ALERTA {alerta['numero']} [{alerta['urgencia']}/10]: {alerta['tema']}")
            enviar_alerta_con_botones(alerta)
            enviados += 1
    else:
        log(f"Sin urgencias.")

    log(f"Enviados a Telegram:      {enviados}")
    log_separador("ROMÁN — CORRIDA COMPLETADA")


# ─── MAIN ─────────────────────────────────────────────────────

def main():
    print("=" * 52)
    print("  ROMÁN V2 — Monitor de Noticias Max Collao")
    print(f"  Iniciado:     {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"  Monitoreo:    cada {INTERVALO_HORAS} horas")
    print(f"  Score mínimo: {SCORE_MINIMO}/10")
    print(f"  Polling:      cada {CHECK_TELEGRAM_SEG} segundos")
    print(f"  Estado:       {STATE_FILE}")
    print("=" * 52)

    if not ANTHROPIC_API_KEY:
        print("❌ FALTA ANTHROPIC_API_KEY — no se puede iniciar")
        return

    estado = cargar_estado()
    sincronizar_telegram(estado)

    enviar_telegram(
        "✅ <b>ROMÁN V2 activado</b>\n"
        f"Monitoreando Chile cada {INTERVALO_HORAS} horas.\n"
        f"Score mínimo: {SCORE_MINIMO}/10\n"
        f"Usa los botones inline para responder a las alertas."
    )

    proxima_revision = datetime.now()  # primera corrida inmediata al arrancar

    while True:
        try:
            marcar_expiradas(estado)
            revisar_telegram(estado)

            if datetime.now() >= proxima_revision:
                correr_revision(estado)
                proxima_revision = datetime.now() + timedelta(hours=INTERVALO_HORAS)
                log(f"Próxima corrida: {proxima_revision.strftime('%d/%m/%Y %H:%M')}")

            time.sleep(CHECK_TELEGRAM_SEG)

        except KeyboardInterrupt:
            raise
        except Exception as e:
            log(f"Error inesperado en loop: {e}")
            time.sleep(30)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nROMÁN detenido.")
        enviar_telegram("⚠️ ROMÁN detenido manualmente.")
