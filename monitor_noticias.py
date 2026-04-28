import requests
import json
import time
import re
import os
import subprocess
from datetime import datetime

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = "8436226379:AAHsZSIIaMb6ROvHvypm4Cdn3vqWg-aARJo"
TELEGRAM_CHAT_ID = "8309799765"
INTERVALO_MINUTOS = 30
COOLDOWN_HORAS = 24

# ── Estado global ────────────────────────────────────────
ultimo_update_id   = None
temas_alertados    = {}   # {clave_tema: datetime}
alertas_pendientes = {}   # {numero: tema_info}
contador_alertas   = 0


# ── Telegram ─────────────────────────────────────────────

def enviar_telegram(mensaje):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "HTML"},
            timeout=10
        )
        print("  Mensaje enviado a Telegram")
    except Exception as e:
        print(f"  Error Telegram: {e}")


def marcar_updates_leidos():
    global ultimo_update_id
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"timeout": 5}, timeout=10
        )
        updates = r.json().get("result", [])
        if updates:
            ultimo_update_id = updates[-1]["update_id"]
            print(f"  Updates marcados hasta ID {ultimo_update_id}")
    except Exception as e:
        print(f"  Error marcando updates: {e}")


def revisar_respuestas_telegram():
    global ultimo_update_id
    numeros = []
    try:
        params = {"timeout": 5}
        if ultimo_update_id is not None:
            params["offset"] = ultimo_update_id + 1
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params=params, timeout=10
        )
        updates = r.json().get("result", [])
        for upd in updates:
            ultimo_update_id = upd["update_id"]
            texto = upd.get("message", {}).get("text", "").strip()
            if texto.isdigit():
                numeros.append(int(texto))
            elif texto.lower() in ["si", "sí", "yes", "ok", "dale"]:
                if alertas_pendientes:
                    numeros.append(min(alertas_pendientes.keys()))
    except Exception as e:
        print(f"  Error revisando Telegram: {e}")
    return numeros


# ── Cooldown ─────────────────────────────────────────────

def normalizar_tema(tema):
    clave = tema.lower().strip()
    clave = re.sub(r'[^a-záéíóúñ0-9 ]', '', clave)
    clave = re.sub(r'\s+', ' ', clave)
    return ' '.join(clave.split()[:5])


def ya_fue_alertado(tema):
    clave = normalizar_tema(tema)
    if clave in temas_alertados:
        horas = (datetime.now() - temas_alertados[clave]).total_seconds() / 3600
        if horas < COOLDOWN_HORAS:
            print(f"  Ya alertado hace {horas:.1f}h — ignorando")
            return True
        del temas_alertados[clave]
    return False


def registrar_tema_alertado(tema):
    temas_alertados[normalizar_tema(tema)] = datetime.now()


# ── API Anthropic ─────────────────────────────────────────

def extraer_json_de_respuesta(content_blocks):
    textos = [b.get("text","").strip() for b in content_blocks if b.get("type")=="text"]
    texto  = "\n".join(textos).strip()
    if not texto:
        return None
    if "```" in texto:
        for parte in texto.split("```"):
            parte = parte.replace("json","").strip()
            if parte.startswith("{"):
                try: return json.loads(parte)
                except: continue
    if texto.startswith("{"):
        try: return json.loads(texto)
        except: pass
    i = texto.find("{"); f = texto.rfind("}")+1
    if i != -1 and f > i:
        try: return json.loads(texto[i:f])
        except: pass
    return None


def detectar_temas_urgentes():
    hora  = datetime.now().strftime("%H:%M")
    fecha = datetime.now().strftime("%d/%m/%Y")
    prompt = f"""Es {fecha} a las {hora} en Chile. Busca en internet las noticias mas virales y urgentes de Chile ahora. Revisa BioBioChile, La Tercera, Emol, CHV Noticias, Twitter/X Chile, TikTok Chile.

Busca: escandalos farandula, estafas a chilenos, virales redes sociales, noticias TV chilena.

Max Collao: ex periodista TV chilena 14 anos, creador digital 117K seguidores Instagram. Le conviene farandula con angulo comunicacional, denuncias estafas, virales Chile.

Responde SOLO JSON valido sin texto ni backticks:
{{"hay_urgente": true, "temas": [{{"tema": "nombre exacto con nombres reales", "urgencia": 8, "categoria": "farandula", "por_que_ahora": "razon especifica hoy", "conviene_a_max": true, "razon": "por que le conviene a Max"}}], "tema_mas_urgente": "tema mas caliente", "recomendacion": "hacer contenido urgente"}}"""
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1500,
                  "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=90
        )
        data = r.json()
        if r.status_code != 200:
            print(f"  Error API [{r.status_code}]")
            return {"hay_urgente": False, "temas": []}
        return extraer_json_de_respuesta(data.get("content", [])) or {"hay_urgente": False, "temas": []}
    except Exception as e:
        print(f"  Error detectando temas: {e}")
        return {"hay_urgente": False, "temas": []}


# ── Libreto ───────────────────────────────────────────────

def generar_libreto(numero, tema_info):
    tema = tema_info.get("tema", "")
    print(f"  Generando libreto #{numero}: {tema[:50]}...")
    enviar_telegram(f"⚙️ Generando libreto <b>#{numero}</b>: <b>{tema}</b>\nListo en ~2 minutos...")
    try:
        subprocess.run(["python", "-u",
            "C:\\Users\\Max\\youtube-agent\\briefing_competencia.py",
            "--urgente", tema])
        enviar_telegram(
            f"✅ <b>Libreto #{numero} listo</b>\n"
            f"Tema: <b>{tema}</b>\n"
            f"Abre: briefing_urgente.html\n"
            f"⚡ Graba AHORA — máximo 24h de vigencia."
        )
    except Exception as e:
        enviar_telegram(f"❌ Error libreto #{numero}: {e}")


# ── Main ──────────────────────────────────────────────────

def main():
    global contador_alertas

    print("="*55)
    print("  ROMAN — MONITOR NOTICIAS MAX COLLAO")
    print(f"  Iniciado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"  Revisando cada {INTERVALO_MINUTOS} minutos")
    print("  Responde el NÚMERO de alerta para el libreto")
    print("="*55)

    if not ANTHROPIC_API_KEY:
        print("ERROR: Falta ANTHROPIC_API_KEY")
        return

    print("  Sincronizando Telegram...")
    marcar_updates_leidos()

    enviar_telegram(
        "✅ <b>Román activado</b>\n"
        f"Monitoreando Chile cada {INTERVALO_MINUTOS} minutos.\n"
        "Cuando haya algo urgente te mando una alerta numerada.\n"
        "Responde con el <b>número</b> para generar el libreto.\n"
        "Puedes tener varias alertas pendientes al mismo tiempo."
    )

    ciclo = 0
    while True:
        ciclo += 1
        hora = datetime.now().strftime("%H:%M")
        print(f"\n[{hora}] Ciclo #{ciclo}")

        # 1. Procesar respuestas de Max
        numeros = revisar_respuestas_telegram()
        for num in numeros:
            if num in alertas_pendientes:
                tema_info = alertas_pendientes.pop(num)
                generar_libreto(num, tema_info)
            else:
                enviar_telegram(f"⚠️ No hay alerta #{num} pendiente.")

        # 2. Buscar temas urgentes
        print("  Buscando noticias urgentes...")
        datos     = detectar_temas_urgentes()
        temas_max = [t for t in datos.get("temas", [])
                     if t.get("conviene_a_max") and t.get("urgencia", 0) >= 7]

        for tema_info in temas_max:
            tema = tema_info.get("tema", "")

            if ya_fue_alertado(tema):
                continue
            if any(normalizar_tema(a["tema"]) == normalizar_tema(tema)
                   for a in alertas_pendientes.values()):
                print(f"  Ya pendiente: {tema[:50]}")
                continue

            contador_alertas += 1
            num = contador_alertas
            alertas_pendientes[num] = tema_info
            registrar_tema_alertado(tema)

            otros = [f"#{n}" for n in alertas_pendientes if n != num]
            otros_txt = f"\n📋 Otras pendientes: {', '.join(otros)}" if otros else ""

            enviar_telegram(
                f"🚨 <b>ALERTA #{num}</b>\n\n"
                f"📌 <b>Tema:</b> {tema}\n"
                f"🔥 <b>Urgencia:</b> {tema_info.get('urgencia',0)}/10\n"
                f"📂 <b>Categoría:</b> {tema_info.get('categoria','')}\n"
                f"⚡ <b>Por qué ahora:</b> {tema_info.get('por_que_ahora','')}\n"
                f"🎯 <b>Para Max:</b> {tema_info.get('razon','')}"
                f"{otros_txt}\n\n"
                f"Responde <b>{num}</b> para el libreto."
            )
            print(f"  Alerta #{num} enviada: {tema[:50]}")

        if not temas_max:
            print(f"  Sin urgencias. Próxima revisión en {INTERVALO_MINUTOS} min.")
        if alertas_pendientes:
            print(f"  Alertas pendientes: {list(alertas_pendientes.keys())}")

        time.sleep(INTERVALO_MINUTOS * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitor detenido.")
        enviar_telegram("⚠️ Román detenido.")
