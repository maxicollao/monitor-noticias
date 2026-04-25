import requests
import json
import time
import os
import subprocess
from datetime import datetime

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
INTERVALO_MINUTOS = 30

def enviar_telegram(mensaje):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "HTML"},
            timeout=10
        )
        print("  Alerta enviada a Telegram")
    except Exception as e:
        print(f"  Error Telegram: {e}")


def generar_libreto(tema):
    prompt = f"Eres Max Collao, ex periodista de TV chilena reconvertido a creador digital con 117K seguidores. Genera un libreto urgente para grabar un video de 3-5 minutos sobre: {tema}. Incluye: gancho inicial potente, desarrollo con datos reales, opinion directa e intensa, cierre con llamada a accion. Estilo directo, sin rodeos, para redes sociales chilenas."
    r = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}, json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1500, "messages": [{"role": "user", "content": prompt}]}, timeout=60)
    return r.json()["content"][0]["text"]

def detectar_temas_urgentes():
    hora = datetime.now().strftime("%H:%M")
    fecha = datetime.now().strftime("%d/%m/%Y")
    prompt = f"""Es {fecha} a las {hora} en Chile. Busca en internet ahora mismo las noticias mas virales y urgentes de Chile en este momento. Revisa BioBioChile, La Tercera, Emol, CHV Noticias, Mega, Twitter/X Chile tendencias, TikTok Chile.

Busca especificamente:
- Escándalos de farándula chilena (suspensiones, peleas, revelaciones)
- Estafas o denuncias que afecten a chilenos comunes
- Virales de TikTok o redes sociales en Chile
- Noticias de TV chilena (Canal 13, CHV, Mega, TVN)
- Cualquier tema que esté explotando en redes sociales chilenas AHORA

Max Collao es un ex periodista de TV chilena (14 años) reconvertido a creador digital con 117K seguidores en Instagram. Le conviene contenido de farándula con ángulo comunicacional, denuncias de estafas, y virales de Chile.

Responde SOLO en JSON sin texto adicional:
{{
  "hay_urgente": true/false,
  "temas": [
    {{
      "tema": "nombre exacto del tema con nombres reales",
      "urgencia": 1-10,
      "categoria": "denuncia/farandula/viral/politica/deporte",
      "por_que_ahora": "razon especifica de por que es urgente HOY con datos reales",
      "conviene_a_max": true/false,
      "razon": "por que le conviene o no a Max Collao"
    }}
  ],
  "tema_mas_urgente": "el tema mas caliente ahora con nombre real",
  "recomendacion": "hacer contenido urgente / esperar / no aplica"
}}"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1000,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )
        texto = "".join(b.get("text","") for b in r.json().get("content",[]) if b.get("type")=="text")
        texto = texto.strip()
        if "```" in texto:
            texto = texto.split("```")[1].replace("json","").strip()
        return json.loads(texto)
    except Exception as e:
        print(f"  Error detectando temas: {e}")
        return {"hay_urgente": False, "temas": [], "recomendacion": "error"}

def revisar_respuesta_telegram():
    """Revisa si Max respondio SI al bot"""
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"timeout": 5, "offset": -1},
            timeout=10
        )
        updates = r.json().get("result", [])
        if updates:
            ultimo = updates[-1]
            texto = ultimo.get("message", {}).get("text", "").lower()
            if texto in ["si", "sí", "yes", "1", "ok", "dale"]:
                return True
    except:
        pass
    return False

def main():
    print("="*55)
    print("  ROMAN - MONITOR DE NOTICIAS MAX COLLAO")
    print(f"  Iniciado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"  Revisando cada {INTERVALO_MINUTOS} minutos")
    print(f"  ROMAN -> Alertas Telegram @MaxCollao_bot")
    print("  Ctrl+C para detener")
    print("="*55)

    if not ANTHROPIC_API_KEY:
        print("FALTA ANTHROPIC_API_KEY")
        return

    # Mensaje de inicio a Telegram
    enviar_telegram(
        "✅ <b>ROMAN activado</b>\n"
        f"Revisando tendencias Chile cada {INTERVALO_MINUTOS} minutos.\n"
        "Te aviso cuando explote algo relevante."
    )

    ciclo = 0
    while True:
        ciclo += 1
        hora = datetime.now().strftime("%H:%M")
        print(f"\n[{hora}] Revision #{ciclo} - analizando Chile...")

        datos = detectar_temas_urgentes()
        temas_max = [t for t in datos.get("temas",[]) if t.get("conviene_a_max") and t.get("urgencia",0) >= 7]

        if datos.get("hay_urgente") and temas_max:
            tema_top = temas_max[0]
            urgencia = tema_top.get("urgencia", 0)
            tema = tema_top.get("tema", "")
            categoria = tema_top.get("categoria", "")
            por_que = tema_top.get("por_que_ahora", "")
            razon = tema_top.get("razon", "")

            print(f"  URGENTE [{urgencia}/10]: {tema}")

            # Armar mensaje para Telegram
            mensaje = (
                f"🚨 <b>ALERTA MAXCOLLAO</b>\n\n"
                f"📌 <b>Tema:</b> {tema}\n"
                f"🔥 <b>Urgencia:</b> {urgencia}/10\n"
                f"📂 <b>Categoría:</b> {categoria}\n"
                f"⚡ <b>Por qué ahora:</b> {por_que}\n"
                f"🎯 <b>Para Max:</b> {razon}\n\n"
                f"¿Genero el libreto completo?\n"
                f"Responde <b>SI</b> para activarlo ahora"
            )
            enviar_telegram(mensaje)

            # Esperar respuesta hasta 10 minutos
            print("  Esperando respuesta de Max en Telegram (10 min)...")
            for _ in range(20):
                time.sleep(30)
                if revisar_respuesta_telegram():
                    print("  Max dijo SI - generando libreto urgente...")
                    enviar_telegram(f"⚙️ Generando libreto urgente para: <b>{tema}</b>\nListo en 2 minutos...")
                libreto = generar_libreto(tema)
                enviar_telegram(f"✅ <b>Libreto listo</b>\n\n{libreto}\n\nGraba AHORA, este tema tiene max 24 horas.")
        else:
            print(f"  Sin urgencias. Proxima revision en {INTERVALO_MINUTOS} min.")

        time.sleep(INTERVALO_MINUTOS * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitor detenido.")
        enviar_telegram("⚠️ ROMAN detenido.")
