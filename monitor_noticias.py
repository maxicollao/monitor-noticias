import requests
import json
import time
import os
import subprocess
from datetime import datetime, timedelta

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8436226379:AAHsZSIIaMb6ROvHvypm4Cdn3vqWg-aARJo")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8309799765")

INTERVALO_MINUTOS = 30
EXPIRACION_MINUTOS = 120
CHECK_TELEGRAM_SEGUNDOS = 10

BASE_DIR = r"C:\Users\Max\youtube-agent"
STATE_FILE = os.path.join(BASE_DIR, "monitor_estado.json")
BRIEFING_SCRIPT = os.path.join(BASE_DIR, "briefing_competencia.py")
BRIEFING_HTML = os.path.join(BASE_DIR, "briefing_urgente.html")


def ahora_iso():
    return datetime.now().isoformat(timespec="seconds")


def cargar_estado():
    estado_base = {
        "next_alerta": 1,
        "last_update_id": 0,
        "alertas": []
    }
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            estado_base.update(data)
    except Exception as e:
        print(f"  Error cargando estado: {e}")
    return estado_base


def guardar_estado(estado):
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  Error guardando estado: {e}")


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


def enviar_documento_telegram(ruta_archivo, caption=""):
    try:
        if not os.path.exists(ruta_archivo):
            enviar_telegram(f"⚠️ No encontré el archivo para enviar:\n{ruta_archivo}")
            return False

        with open(ruta_archivo, "rb") as archivo:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                files={"document": archivo},
                timeout=60
            )
        if r.status_code == 200:
            print("  Documento enviado a Telegram")
            return True
        print(f"  Error enviando documento: {r.text}")
    except Exception as e:
        print(f"  Error enviando documento: {e}")
    return False


def sincronizar_telegram_al_iniciar(estado):
    """Ignora mensajes antiguos para que un 'SI' viejo o un número viejo no active libretos."""
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
            print(f"  Telegram sincronizado. Ignorando updates antiguos hasta {estado['last_update_id']}")
    except Exception as e:
        print(f"  No pude sincronizar Telegram al iniciar: {e}")


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
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "web-search-2025-03-05",
            "Content-Type": "application/json"
        }
        messages = [{"role": "user", "content": prompt}]

        for intento in range(5):
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1500,
                    "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                    "messages": messages
                },
                timeout=90
            )
            data = r.json()

            if "error" in data:
                print(f"  API error: {data['error'].get('message','')}")
                return {"hay_urgente": False, "temas": [], "recomendacion": "error"}

            content = data.get("content", [])
            stop_reason = data.get("stop_reason", "")

            if stop_reason == "end_turn":
                texto = "".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
                if not texto:
                    print("  Respuesta vacia del modelo")
                    return {"hay_urgente": False, "temas": [], "recomendacion": "error"}
                if "```" in texto:
                    partes = texto.split("```")
                    for parte in partes:
                        parte = parte.replace("json", "").strip()
                        if parte.startswith("{"):
                            texto = parte
                            break
                if "{" in texto:
                    texto = texto[texto.index("{"):texto.rindex("}") + 1]
                return json.loads(texto)

            if stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": content})
                tool_results = []
                for bloque in content:
                    if bloque.get("type") == "tool_use":
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": bloque.get("id"),
                            "content": bloque.get("content", "Sin resultados")
                        })
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                continue

            break

        print("  No se obtuvo respuesta JSON tras varios intentos")
        return {"hay_urgente": False, "temas": [], "recomendacion": "error"}

    except json.JSONDecodeError as e:
        print(f"  Error parseando JSON: {e}")
        return {"hay_urgente": False, "temas": [], "recomendacion": "error"}
    except Exception as e:
        print(f"  Error detectando temas: {e}")
        return {"hay_urgente": False, "temas": [], "recomendacion": "error"}


def crear_alerta(estado, tema_top):
    numero = estado.get("next_alerta", 1)
    estado["next_alerta"] = numero + 1

    alerta = {
        "numero": numero,
        "tema": tema_top.get("tema", ""),
        "urgencia": tema_top.get("urgencia", 0),
        "categoria": tema_top.get("categoria", ""),
        "por_que_ahora": tema_top.get("por_que_ahora", ""),
        "razon": tema_top.get("razon", ""),
        "creada": ahora_iso(),
        "estado": "pendiente"
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
    for alerta in estado.get("alertas", []):
        if str(alerta.get("numero")) == str(numero):
            return alerta
    return None


def marcar_expiradas(estado):
    cambio = False
    for alerta in estado.get("alertas", []):
        if alerta.get("estado") == "pendiente" and esta_expirada(alerta):
            alerta["estado"] = "vencido"
            cambio = True
    if cambio:
        guardar_estado(estado)


def generar_libreto_para_alerta(estado, alerta):
    numero = alerta.get("numero")
    tema = alerta.get("tema", "")

    if alerta.get("estado") == "generado":
        enviar_telegram(f"⚠️ <b>ALERTA {numero}</b> ya fue generada antes.")
        return

    if alerta.get("estado") == "vencido" or esta_expirada(alerta):
        alerta["estado"] = "vencido"
        guardar_estado(estado)
        enviar_telegram(
            f"⚠️ <b>ALERTA {numero}</b> ya venció.\n"
            f"Tema: {tema}\n\n"
            f"Si todavía te interesa, espera una nueva alerta actualizada para no grabar con datos viejos."
        )
        return

    enviar_telegram(f"⚙️ Generando libreto urgente para <b>ALERTA {numero}</b>:\n<b>{tema}</b>\nListo en unos minutos...")
    print(f"  Generando libreto para ALERTA {numero}: {tema}")

    try:
        resultado = subprocess.run(
            ["python", "-u", BRIEFING_SCRIPT, "--urgente", tema],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=600
        )
        if resultado.returncode != 0:
            print(resultado.stderr)
            enviar_telegram(
                f"❌ Error generando libreto para <b>ALERTA {numero}</b>.\n"
                f"Revisa la consola del PC."
            )
            return

        alerta["estado"] = "generado"
        alerta["generado"] = ahora_iso()
        guardar_estado(estado)

        enviado = enviar_documento_telegram(
            BRIEFING_HTML,
            caption=f"✅ <b>Libreto listo - ALERTA {numero}</b>\nÁbrelo desde este archivo.\nGraba AHORA."
        )
        if not enviado:
            enviar_telegram(
                f"✅ <b>Libreto listo - ALERTA {numero}</b>\n"
                f"Pero no pude adjuntar el HTML. Está en el PC:\n{BRIEFING_HTML}"
            )
    except subprocess.TimeoutExpired:
        enviar_telegram(f"❌ El libreto de <b>ALERTA {numero}</b> tardó demasiado y se detuvo.")
    except Exception as e:
        print(f"  Error generando libreto: {e}")
        enviar_telegram(f"❌ Error generando libreto para <b>ALERTA {numero}</b>: {e}")


def procesar_mensaje_telegram(estado, texto):
    texto_limpio = (texto or "").strip().lower()

    if not texto_limpio:
        return

    if texto_limpio in ["si", "sí", "yes", "ok", "dale"]:
        pendientes = [a for a in estado.get("alertas", []) if a.get("estado") == "pendiente" and not esta_expirada(a)]
        if pendientes:
            resumen = "\n".join([f"• {a['numero']}: {a['tema']}" for a in pendientes[-5:]])
            enviar_telegram(
                "⚠️ Para evitar errores, ya no basta con responder SI.\n\n"
                "Responde solo el número de la alerta.\n\n"
                f"Pendientes:\n{resumen}"
            )
        else:
            enviar_telegram("⚠️ No hay alertas pendientes activas. Espera la próxima alerta.")
        return

    if texto_limpio.isdigit():
        numero = int(texto_limpio)
        alerta = buscar_alerta(estado, numero)
        if not alerta:
            enviar_telegram(f"⚠️ No encontré la ALERTA {numero}. Revisa el número y responde de nuevo.")
            return
        generar_libreto_para_alerta(estado, alerta)
        return

    # Permite también formatos como: alerta 12, generar 12, si 12
    partes = texto_limpio.replace("#", " ").split()
    numeros = [p for p in partes if p.isdigit()]
    if numeros:
        alerta = buscar_alerta(estado, int(numeros[0]))
        if alerta:
            generar_libreto_para_alerta(estado, alerta)
        else:
            enviar_telegram(f"⚠️ No encontré la ALERTA {numeros[0]}.")


def revisar_respuestas_telegram(estado):
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"timeout": 1, "offset": estado.get("last_update_id", 0) + 1},
            timeout=10
        )
        updates = r.json().get("result", [])
        if not updates:
            return

        for update in updates:
            estado["last_update_id"] = max(estado.get("last_update_id", 0), update.get("update_id", 0))
            mensaje = update.get("message") or update.get("edited_message") or {}
            chat_id = str(mensaje.get("chat", {}).get("id", ""))
            texto = mensaje.get("text", "")

            # Seguridad: solo obedecer al chat configurado de Max.
            if chat_id != str(TELEGRAM_CHAT_ID):
                continue

            procesar_mensaje_telegram(estado, texto)

        guardar_estado(estado)
    except Exception as e:
        print(f"  Error revisando respuestas Telegram: {e}")


def enviar_alerta_telegram(alerta):
    mensaje = (
        f"🚨 <b>ALERTA {alerta['numero']} - MAXCOLLAO</b>\n\n"
        f"📌 <b>Tema:</b> {alerta['tema']}\n"
        f"🔥 <b>Urgencia:</b> {alerta['urgencia']}/10\n"
        f"📂 <b>Categoría:</b> {alerta['categoria']}\n"
        f"⚡ <b>Por qué ahora:</b> {alerta['por_que_ahora']}\n"
        f"🎯 <b>Para Max:</b> {alerta['razon']}\n\n"
        f"⏳ Disponible por {EXPIRACION_MINUTOS} minutos.\n"
        f"Para generar el libreto responde solo:\n"
        f"<b>{alerta['numero']}</b>"
    )
    enviar_telegram(mensaje)


def revisar_noticias_y_crear_alerta(estado):
    hora = datetime.now().strftime("%H:%M")
    print(f"\n[{hora}] Analizando Chile...")

    datos = detectar_temas_urgentes()
    temas_max = [
        t for t in datos.get("temas", [])
        if t.get("conviene_a_max") and t.get("urgencia", 0) >= 7
    ]

    if datos.get("hay_urgente") and temas_max:
        tema_top = temas_max[0]
        alerta = crear_alerta(estado, tema_top)
        print(f"  ALERTA {alerta['numero']} [{alerta['urgencia']}/10]: {alerta['tema']}")
        enviar_alerta_telegram(alerta)
    else:
        print(f"  Sin urgencias. Próxima revisión en {INTERVALO_MINUTOS} min.")


def main():
    print("=" * 60)
    print("  MONITOR DE NOTICIAS - MAX COLLAO")
    print(f"  Iniciado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"  Noticias cada {INTERVALO_MINUTOS} minutos")
    print(f"  Telegram cada {CHECK_TELEGRAM_SEGUNDOS} segundos")
    print("  Responde solo el número de alerta: 1, 2, 3...")
    print("  Ctrl+C para detener")
    print("=" * 60)

    if not ANTHROPIC_API_KEY:
        print("FALTA ANTHROPIC_API_KEY")
        return

    estado = cargar_estado()
    sincronizar_telegram_al_iniciar(estado)

    enviar_telegram(
        "✅ <b>Monitor MaxCollao activado</b>\n"
        f"Revisando tendencias Chile cada {INTERVALO_MINUTOS} minutos.\n"
        "Ahora responde solo el número de la alerta. Ejemplo: 3"
    )

    proxima_revision = datetime.now()

    while True:
        marcar_expiradas(estado)
        revisar_respuestas_telegram(estado)

        if datetime.now() >= proxima_revision:
            revisar_noticias_y_crear_alerta(estado)
            proxima_revision = datetime.now() + timedelta(minutes=INTERVALO_MINUTOS)

        time.sleep(CHECK_TELEGRAM_SEGUNDOS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitor detenido.")
        enviar_telegram("⚠️ Monitor MaxCollao detenido.")
