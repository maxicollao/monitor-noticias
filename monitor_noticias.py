# ═══════════════════════════════════════════════════════════════
#  ROMÁN V3 — VERSIÓN DEFINITIVA ULTRA-ROBUSTA
#  
#  Monitor de Noticias Max Collao
#  
#  CAMBIOS CRÍTICOS V3:
#  ✅ Prompt: LAS 10 MÁS URGENTES (no 1 por categoría)
#  ✅ Keywords override: gobierno/gabinete → FORZADO
#  ✅ Score mínimo: 6 (captura más)
#  ✅ LIBRETOS COMPLETOS: Hook + Guión + Caption + Comentario Fijado
#  ✅ Formato: 60 segundos máximo, universal FB/IG/TikTok
#  ✅ Reporte detallado a Telegram cada corrida
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

INTERVALO_HORAS      = 6
EXPIRACION_MINUTOS   = 120
CHECK_TELEGRAM_SEG   = 30
SCORE_MINIMO         = 6     # Captura más noticias

# ✅ KEYWORDS CRÍTICOS: override automático si aparecen
KEYWORDS_CRITICOS = [
    "gobierno", "gabinete", "presidente", "ministro", "boric",
    "crisis política", "renuncia", "emergencia", "terremoto"
]

BASE_DIR   = os.environ.get("BASE_DIR", os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(BASE_DIR, "roman_estado.json")


# ─── LOGGING ──────────────────────────────────────────────────

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def log_separador(titulo=""):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {'═' * 50}", flush=True)
    if titulo:
        print(f"[{ts}]  {titulo}", flush=True)


# ─── ESTADO ───────────────────────────────────────────────────

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
        "categoria_max":tema_data.get("categoria_max", ""),
        "por_que_ahora":tema_data.get("por_que_ahora", ""),
        "razon":        tema_data.get("razon", ""),
        "creada":       ahora_iso(),
        "estado":       "pendiente",
        "modelo_usado": None,
        "es_override":  tema_data.get("es_override", False)
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


# ─── TELEGRAM ─────────────────────────────────────────────────

def enviar_telegram(mensaje):
    LIMITE = 4000
    if len(mensaje) <= LIMITE:
        _enviar_bloque(mensaje)
    else:
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
                time.sleep(0.8)

def _enviar_bloque(texto):
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
            log("✅ Mensaje enviado")
        else:
            log(f"⚠️ Error Telegram {r.status_code}")
    except Exception as e:
        log(f"⚠️ Error Telegram: {e}")

def enviar_alerta_con_botones(alerta):
    n = alerta["numero"]
    cat_max = alerta.get("categoria_max", "")
    cat_emojis = {
        "OPINION_CONTINGENCIA": "🎙️ OPINION / CONTINGENCIA",
        "DENUNCIA_DIA":         "🚨 DENUNCIA DEL DIA",
        "PODER_MENSAJE":        "🎯 EL PODER DE TU MENSAJE",
        "FARANDULA_HUMOR":      "🎭 FARANDULA / HUMOR",
        "ESTAFAS_ALERTAS":      "⚠️ ESTAFAS / ALERTAS"
    }
    cat_label = cat_emojis.get(cat_max, f"📂 {alerta['categoria']}")
    
    override_tag = " 🔥 <b>ULTRA-URGENTE</b>" if alerta.get("es_override") else ""

    mensaje = (
        f"🚨 <b>ALERTA {n} — ROMÁN</b>{override_tag}\n\n"
        f"<b>{cat_label}</b>\n\n"
        f"📰 <b>Tema:</b> {alerta['tema']}\n"
        f"🔥 <b>Score:</b> {alerta['urgencia']}/10\n"
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
                {"text": "🎬 LIBRETO REDES",    "callback_data": f"libreto|{n}"},
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
            log(f"✅ Alerta {n} enviada")
        else:
            log(f"⚠️ Error enviando alerta {n}")
    except Exception as e:
        log(f"⚠️ Error: {e}")

def confirmar_callback(callback_query_id, texto="✅"):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": texto},
            timeout=10
        )
    except Exception:
        pass

def enviar_alerta_tecnica(detalle):
    enviar_telegram(f"⚠️ <b>ROMÁN — Error técnico</b>\n<code>{str(detalle)[:300]}</code>")

def sincronizar_telegram(estado):
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
            log(f"Telegram sincronizado")
    except Exception as e:
        log(f"⚠️ Error sincronizando: {e}")


# ─── ANTHROPIC API ────────────────────────────────────────────

def llamar_anthropic(modelo, max_tokens, prompt, system=None):
    headers = {
        "x-api-key":         ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type":      "application/json"
    }

    body = {
        "model":      modelo,
        "max_tokens": max_tokens,
        "messages":   [{"role": "user", "content": prompt}]
    }
    if system:
        body["system"] = system

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
            timeout=120
        )
        data = r.json()
        
        if "error" in data:
            log(f"⚠️ API error: {data['error'].get('message','')[:100]}")
            return None
            
        content = data.get("content", [])
        texto = "".join(
            b.get("text", "") for b in content if b.get("type") == "text"
        ).strip()
        return texto if texto else None
        
    except Exception as e:
        log(f"⚠️ Error llamando API: {e}")
        return None


# ─── DETECCIÓN CON KEYWORDS OVERRIDE ──────────────────────────

def tiene_keywords_criticos(texto):
    texto_lower = texto.lower()
    for keyword in KEYWORDS_CRITICOS:
        if keyword in texto_lower:
            return True
    return False


# ─── DETECCIÓN DE NOTICIAS ────────────────────────────────────

def detectar_temas_urgentes():
    """
    ✅ PROMPT REDISEÑADO: pide LAS 10 MÁS URGENTES
    ✅ No limita a 1 por categoría
    ✅ Prioriza noticias que están explotando AHORA
    """
    hora  = datetime.now().strftime("%H:%M")
    fecha = datetime.now().strftime("%d/%m/%Y")

    prompt = f"""Hora Chile: {fecha} {hora}

Busca las 10 noticias MAS URGENTES y VIRALES de Chile AHORA (últimas 24 horas) usando web search.

PRIORIDAD: noticias de HOY. Si no hay suficientes urgentes de hoy, incluir de ayer.
Lo importante: URGENCIA + VIRALIDAD + FRESCURA (no fecha exacta).

FUENTES principales Chile (priorizar disponibles):
La Tercera, El Mercurio, Emol, BioBioChile, Cooperativa, CNN Chile, 
24Horas.cl, T13, Meganoticias, CHV, LUN, La Cuarta, El Mostrador, 
The Clinic, Twitter/X Chile, Instagram Chile, TikTok Chile.

MAX COLLAO: Ex periodista TV 14 años (TVN, Canal 13, CHV). 
Creador digital 117K @maxcollao. Temas: contingencia, farandula, 
denuncia, analisis. Tono: periodista analitico con picante.

PRIORIZA NOTICIAS QUE:
- Estan EXPLOTANDO ahora (gobierno, crisis, escandalos)
- Todo Chile esta comentando
- Tienen impacto real y emocional
- Son perfectas para video corto (60 segundos)

CATEGORIAS (solo para clasificar):
1. OPINION_CONTINGENCIA: politica, economia, sociedad, declaraciones
2. DENUNCIA_DIA: estafas, abusos, alertas con datos duros
3. PODER_MENSAJE: errores comunicacionales de figuras publicas
4. FARANDULA_HUMOR: escandalos, viral, entretenimiento
5. ESTAFAS_ALERTAS: denuncias ciudadanas, nuevas modalidades

DEVUELVE LAS 10 MAS URGENTES ordenadas por urgencia (10 primero).

FORMATO JSON (SOLO JSON, sin texto antes ni despues):
{{
  "total_revisados": 30,
  "hay_urgente": true,
  "temas": [
    {{
      "tema": "nombre exacto con nombres reales",
      "bajada": "bajada o descripcion",
      "fuente": "medio",
      "hora_noticia": "hora si existe",
      "link": "URL si existe",
      "urgencia": 9,
      "categoria": "contingencia/denuncia/farandula/viral/estafa",
      "categoria_max": "OPINION_CONTINGENCIA",
      "por_que_ahora": "razon especifica con datos reales",
      "conviene_a_max": true,
      "razon": "por que conviene a Max"
    }}
  ],
  "recomendacion": "hacer contenido urgente"
}}"""

    log("🔍 Buscando noticias urgentes...")

    system_prompt = (
        "Eres un sistema de monitoreo de noticias. "
        "Respondes SOLO con JSON valido. "
        "PROHIBIDO texto antes o despues del JSON. "
        "Ordena temas por urgencia descendente (10→6)."
    )

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
                        "max_tokens": 4000,
                        "system":     system_prompt,
                        "tools":      [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages":   messages
                    },
                    timeout=120
                )
                data = r.json()
            except Exception as e:
                log(f"⚠️ Error red intento {intento+1}: {e}")
                time.sleep(5)
                continue

            if "error" in data:
                error_msg = data['error'].get('message','')[:100]
                log(f"⚠️ API error: {error_msg}")
                enviar_alerta_tecnica(f"Error API deteccion:\n{error_msg}")
                return {"total_revisados": 0, "hay_urgente": False, "temas": []}

            content     = data.get("content", [])
            stop_reason = data.get("stop_reason", "")

            if stop_reason == "end_turn":
                texto = "".join(
                    b.get("text", "") for b in content if b.get("type") == "text"
                ).strip()

                if not texto:
                    log("⚠️ Respuesta vacía")
                    enviar_alerta_tecnica("Modelo devolvio respuesta vacia")
                    return {"total_revisados": 0, "hay_urgente": False, "temas": []}

                if "```" in texto:
                    partes = texto.split("```")
                    for parte in partes:
                        parte = parte.replace("json", "").strip()
                        if parte.startswith("{"):
                            texto = parte
                            break

                if "{" not in texto:
                    log(f"⚠️ No es JSON: {texto[:150]}")
                    enviar_alerta_tecnica(f"Respuesta no-JSON:\n{texto[:200]}")
                    return {"total_revisados": 0, "hay_urgente": False, "temas": []}

                texto = texto[texto.index("{"):texto.rindex("}") + 1]

                try:
                    resultado = json.loads(texto)
                    temas = resultado.get("temas", [])
                    log(f"✅ Modelo devolvió {len(temas)} temas")
                    for i, t in enumerate(temas, 1):
                        log(f"  {i}. [{t.get('urgencia',0)}/10] {t.get('tema','')[:50]}")
                    return resultado
                except json.JSONDecodeError as e:
                    log(f"⚠️ Error JSON: {e}")
                    enviar_alerta_tecnica(f"Error parseando JSON:\n{str(e)[:100]}")
                    return {"total_revisados": 0, "hay_urgente": False, "temas": []}

            if stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": content})
                tool_results = []
                for bloque in content:
                    if bloque.get("type") == "tool_use":
                        tool_results.append({
                            "type":        "tool_result",
                            "tool_use_id": bloque.get("id"),
                            "content":     []
                        })
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                continue

            break

        return {"total_revisados": 0, "hay_urgente": False, "temas": []}

    except Exception as e:
        log(f"⚠️ Error en detección: {e}")
        enviar_alerta_tecnica(f"Excepcion:\n{str(e)[:200]}")
        return {"total_revisados": 0, "hay_urgente": False, "temas": []}


# ─── GENERACIÓN DE CONTENIDO ──────────────────────────────────

def _contexto_alerta(alerta):
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
    n = alerta["numero"]
    log(f"📋 Generando resumen → Alerta {n}")

    prompt = f"""Asistente de Max Collao. Ex periodista TV 14 años. 
Creador digital 117K @maxcollao.

Resumen breve para que Max decida si grabar:

{_contexto_alerta(alerta)}

ESTRUCTURA:

📰 QUÉ PASÓ
[2-3 líneas hechos clave]

🔥 POR QUÉ IMPORTA
[1-2 líneas, ángulo emocional]

🎯 ÁNGULO PARA MAX
[1-2 líneas, cómo abordarlo]

⏰ URGENCIA: {alerta['urgencia']}/10"""

    enviar_telegram(f"⏳ Generando resumen <b>Alerta {n}</b>...")
    texto = llamar_anthropic("claude-haiku-4-5-20251001", 800, prompt)

    if texto:
        enviar_telegram(
            f"📋 <b>RESUMEN — Alerta {n}</b>\n"
            f"<i>Modelo: Haiku</i>\n\n{texto}"
        )
        log(f"✅ Resumen enviado")
    else:
        enviar_telegram(f"⚠️ No pude generar resumen Alerta {n}")


def generar_libreto_redes(alerta):
    """
    ✅ LIBRETO COMPLETO FORMATO REDES SOCIALES
    ✅ 60 segundos máximo
    ✅ Hook viral + Guión + Caption + Comentario fijado
    ✅ Universal: FB, Instagram, TikTok
    """
    n = alerta["numero"]
    log(f"🎬 Generando LIBRETO REDES → Alerta {n}")

    prompt = f"""Eres el guionista de Max Collao. Ex periodista TV 14 años. 
Creador digital 117K @maxcollao.

Genera libreto COMPLETO para redes sociales:

{_contexto_alerta(alerta)}

REGLAS:
- Español chileno, nunca argentinismos
- Duración: 60 segundos MÁXIMO
- Formato: FB, Instagram, TikTok (universal)
- Hook: primeras 3 segundos detienen el scroll
- Tono: periodista astuto, sin ataques personales
- Ángulo: voz de los que no tienen voz

═══════════════════════════════════════════
🎬 LIBRETO REDES — {alerta['tema']}
═══════════════════════════════════════════

📱 HOOK VIRAL (3-5 segundos)
[Primera frase EXACTA que dice Max - debe detener el scroll]

🎙️ GUIÓN (45-50 segundos)
[Lo que dice Max palabra por palabra, con ritmo natural.
Máximo 150 palabras. Marcar pausas con /]

💥 CIERRE + CTA (5 segundos)
[Frase de cierre + llamado a la acción]

📹 PRODUCCIÓN
Cámara: [frente/selfie/walking]
Locación: [dónde grabarlo AHORA]
Texto pantalla: [3-5 palabras clave superpuestas]

📝 CAPTION PARA PUBLICAR
[Caption viral 2-3 líneas con emojis. 
Debe funcionar solo, sin el video. Max 280 caracteres]

Hashtags: [MÁXIMO 5 hashtags - Chile + tema específico]

💬 COMENTARIO FIJADO
[Comentario para fijar. Genera conversación. 
Max 200 caracteres. Termina con pregunta]

⏰ GRABAR HOY. Vida útil: 24 horas máximo."""

    enviar_telegram(f"⏳ Generando LIBRETO REDES <b>Alerta {n}</b>...")
    texto = llamar_anthropic("claude-sonnet-4-5", 5000, prompt)

    if texto:
        enviar_telegram(
            f"🎬 <b>LIBRETO REDES — Alerta {n}</b>\n"
            f"<i>Modelo: Sonnet | 60 seg | FB/IG/TikTok</i>\n\n{texto}"
        )
        log(f"✅ Libreto enviado")
    else:
        enviar_telegram(f"⚠️ No pude generar libreto Alerta {n}")


def generar_libreto_opus(alerta):
    """MODO OPUS: análisis extendido + múltiples versiones"""
    n = alerta["numero"]
    log(f"⚡ MODO OPUS → Alerta {n}")

    prompt = f"""Guionista SENIOR Max Collao. MODO OPUS activado.

{_contexto_alerta(alerta)}

═══════════════════════════════════════════
⚡ MODO OPUS — {alerta['tema']}
═══════════════════════════════════════════

📊 ANÁLISIS PROFUNDO
[Contexto, antecedentes, protagonistas, datos para entender a fondo]

🎬 LIBRETO REDES 60 SEG (versión A)
Hook viral (3 seg) / Guión (50 seg) / Cierre (7 seg)
Caption + Hashtags (máximo 5) + Comentario fijado

🎬 LIBRETO REDES 60 SEG (versión B - ángulo alternativo)
Hook diferente / Desarrollo alternativo / Cierre
Caption + Hashtags (máximo 5) + Comentario fijado

📺 LIBRETO YOUTUBE LARGO (5-8 min si aplica)
Hook 30 seg / Intro 1 min / 3 puntos desarrollados / 
Contexto histórico / Cierre emocional

📱 ESTRATEGIA DISTRIBUCIÓN
Plataformas en orden / Horarios óptimos / 
Adaptaciones por red / Seguimiento

📊 ANÁLISIS VIRALIDAD
Potencial 1-10 / Riesgos / Oportunidades

⚠️ GRABAR HOY. 24 horas máximo."""

    enviar_telegram(
        f"⚡ <b>MODO OPUS activado</b>\n"
        f"Análisis extendido <b>Alerta {n}</b>...\n"
        f"<i>2-3 minutos</i>"
    )
    texto = llamar_anthropic("claude-opus-4-5", 8000, prompt)

    if texto:
        enviar_telegram(
            f"⚡ <b>MODO OPUS — Alerta {n}</b>\n"
            f"<i>Modelo: Opus</i>\n\n{texto}"
        )
        log(f"✅ Opus enviado")
    else:
        enviar_telegram(f"⚠️ Error Opus Alerta {n}")


# ─── PROCESAMIENTO BOTONES ────────────────────────────────────

def procesar_callback(estado, callback):
    callback_id = callback.get("id")
    data_cb     = callback.get("data", "")
    chat_id     = str(callback.get("message", {}).get("chat", {}).get("id", ""))

    if chat_id != str(TELEGRAM_CHAT_ID):
        confirmar_callback(callback_id, "No autorizado")
        return

    confirmar_callback(callback_id, "✅")

    if "|" not in data_cb:
        return

    accion, numero_str = data_cb.split("|", 1)
    alerta = buscar_alerta(estado, numero_str)
    log(f"📱 Callback: [{accion}] Alerta {numero_str}")

    if not alerta:
        enviar_telegram(f"⚠️ Alerta {numero_str} no encontrada")
        return

    if alerta.get("estado") == "ignorado":
        enviar_telegram(f"🚫 Alerta {numero_str} ya ignorada")
        return

    if alerta.get("estado") == "vencido" or esta_expirada(alerta):
        alerta["estado"] = "vencido"
        guardar_estado(estado)
        enviar_telegram(f"⏰ Alerta {numero_str} expirada")
        return

    if accion == "ignorar":
        alerta["estado"] = "ignorado"
        guardar_estado(estado)
        enviar_telegram(f"🚫 Alerta {numero_str} ignorada")

    elif accion == "resumen":
        generar_resumen_haiku(alerta)

    elif accion == "libreto":
        generar_libreto_redes(alerta)
        alerta["estado"]       = "generado"
        alerta["modelo_usado"] = "claude-sonnet-4-5"
        guardar_estado(estado)

    elif accion == "opus":
        generar_libreto_opus(alerta)
        alerta["estado"]       = "generado"
        alerta["modelo_usado"] = "claude-opus-4-5"
        guardar_estado(estado)


# ─── POLLING TELEGRAM ─────────────────────────────────────────

def revisar_telegram(estado):
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

            if "callback_query" in update:
                procesar_callback(estado, update["callback_query"])

        guardar_estado(estado)

    except Exception as e:
        log(f"⚠️ Error Telegram: {e}")


# ─── CORRIDA DE MONITOREO CON REPORTE ─────────────────────────

def correr_revision(estado):
    log_separador("🚀 CORRIDA INICIADA")

    datos = detectar_temas_urgentes()

    total_revisados = datos.get("total_revisados", 0)
    temas_devueltos = datos.get("temas", [])
    
    # ✅ APLICAR KEYWORDS OVERRIDE
    for tema in temas_devueltos:
        tema_texto = f"{tema.get('tema','')} {tema.get('bajada','')}".lower()
        if tiene_keywords_criticos(tema_texto):
            tema["es_override"] = True
            tema["urgencia"] = max(tema.get("urgencia", 0), 9)
            log(f"🔥 OVERRIDE: {tema.get('tema','')[:40]}")
    
    # Filtrado con logging detallado
    temas_validos = []
    temas_descartados = []
    
    for t in temas_devueltos:
        score = t.get("urgencia", 0)
        conviene = t.get("conviene_a_max", False)
        es_override = t.get("es_override", False)
        
        if es_override:
            temas_validos.append(t)
            log(f"✅ [OVERRIDE {score}/10] {t.get('tema','')[:50]}")
        elif conviene and score >= SCORE_MINIMO:
            temas_validos.append(t)
            log(f"✅ [{score}/10] {t.get('tema','')[:50]}")
        else:
            razon = "score bajo" if score < SCORE_MINIMO else "no conviene"
            temas_descartados.append({
                "tema": t.get("tema", "")[:50],
                "score": score,
                "razon": razon
            })
            log(f"❌ [{score}/10] {t.get('tema','')[:50]} — {razon}")

    # ✅ REPORTE A TELEGRAM
    reporte = (
        f"📊 <b>REPORTE DE CORRIDA</b>\n\n"
        f"📰 Titulares revisados: {total_revisados}\n"
        f"📥 Devueltos por modelo: {len(temas_devueltos)}\n"
        f"✅ Válidos (score ≥{SCORE_MINIMO}): {len(temas_validos)}\n"
        f"❌ Descartados: {len(temas_descartados)}\n"
    )
    
    if temas_descartados:
        reporte += f"\n<b>DESCARTADOS:</b>\n"
        for d in temas_descartados[:5]:
            reporte += f"• [{d['score']}/10] {d['tema']} — {d['razon']}\n"
    
    enviar_telegram(reporte)
    
    # Enviar alertas
    enviados = 0
    if datos.get("hay_urgente") and temas_validos:
        for tema in temas_validos[:10]:
            alerta = crear_alerta(estado, tema)
            log(f"🚨 ALERTA {alerta['numero']} [{alerta['urgencia']}/10]: {alerta['tema'][:50]}")
            enviar_alerta_con_botones(alerta)
            enviados += 1
            time.sleep(1)
    else:
        log("Sin urgencias")

    log(f"✅ Enviados: {enviados}")
    log_separador("✅ CORRIDA COMPLETADA")


# ─── MAIN ─────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  ROMÁN V3 — VERSIÓN DEFINITIVA ULTRA-ROBUSTA")
    print(f"  Iniciado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"  Monitoreo: cada {INTERVALO_HORAS} horas")
    print(f"  Score mínimo: {SCORE_MINIMO}/10")
    print(f"  Keywords críticos: {len(KEYWORDS_CRITICOS)}")
    print("=" * 60)

    if not ANTHROPIC_API_KEY:
        print("❌ FALTA ANTHROPIC_API_KEY")
        return

    estado = cargar_estado()
    sincronizar_telegram(estado)

    enviar_telegram(
        "✅ <b>ROMÁN V3 ACTIVADO</b>\n\n"
        f"🔍 Búsqueda: LAS 10 MÁS URGENTES\n"
        f"🔥 Keywords override: {len(KEYWORDS_CRITICOS)}\n"
        f"🎬 Libretos: formato redes 60seg\n"
        f"📊 Reporte: cada corrida\n"
        f"⏰ Monitoreo: cada {INTERVALO_HORAS}h\n\n"
        f"Usa botones inline para responder."
    )

    proxima_revision = datetime.now()

    while True:
        try:
            marcar_expiradas(estado)
            revisar_telegram(estado)

            if datetime.now() >= proxima_revision:
                correr_revision(estado)
                proxima_revision = datetime.now() + timedelta(hours=INTERVALO_HORAS)
                log(f"⏰ Próxima: {proxima_revision.strftime('%d/%m/%Y %H:%M')}")

            time.sleep(CHECK_TELEGRAM_SEG)

        except KeyboardInterrupt:
            raise
        except Exception as e:
            log(f"⚠️ Error loop: {e}")
            enviar_alerta_tecnica(f"Error loop:\n{str(e)[:200]}")
            time.sleep(30)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n✅ ROMÁN detenido")
