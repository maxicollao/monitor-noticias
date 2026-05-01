import requests
import json
import time
import os
import sys
from datetime import datetime, timedelta
 
APIFY_API_KEY = os.environ.get("APIFY_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN   = "8436226379:AAHsZSIIaMb6ROvHvypm4Cdn3vqWg-aARJo"
TELEGRAM_CHAT_ID = "8309799765"
CUENTAS_IG = ["mati.burboa", "luzutv", "pamefieradiaz", "nancupil.oficial"]
 
# Modo urgente: python briefing_competencia.py --urgente "tema"
MODO_URGENTE = "--urgente" in sys.argv
TEMA_URGENTE = sys.argv[sys.argv.index("--urgente") + 1] if MODO_URGENTE and len(sys.argv) > sys.argv.index("--urgente") + 1 else ""
 
def enviar_libreto_telegram(analisis: str, tema: str):
    """Extrae el libreto de 60 seg del analisis y lo manda directo a Telegram."""
    try:
        import re
        # Extraer solo la seccion LIBRETO URGENTE - REEL/SHORT
        m = re.search(
            r'=== LIBRETO URGENTE - REEL/SHORT.*?===(.*?)(?====|\Z)',
            analisis, re.DOTALL
        )
        if m:
            libreto_texto = m.group(1).strip()
        else:
            # Si no encuentra el bloque exacto, tomar las primeras 1500 chars del analisis
            libreto_texto = analisis[:1500].strip()

        mensaje = (
            f"LIBRETO URGENTE — 60 SEG\n"
            f"Tema: {tema}\n"
            f"Vigencia: 24h — GRABA HOY\n"
            f"{'='*30}\n\n"
            f"{libreto_texto}"
        )

        # Telegram tiene limite de 4096 chars por mensaje
        if len(mensaje) > 4000:
            mensaje = mensaje[:4000] + "\n\n[... continua en briefing_urgente.html]"

        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje},
            timeout=15
        )
        print("  Libreto enviado a Telegram OK")
    except Exception as e:
        print(f"  Error enviando libreto Telegram: {e}")


def obtener_posts():
    if MODO_URGENTE:
        print("MODO URGENTE - saltando analisis de competencia...")
        return {}
    print("Analizando competencia en Instagram via Apify...")
    resultados = {}
    headers = {"Authorization": f"Bearer {APIFY_API_KEY}", "Content-Type": "application/json"}
    for cuenta in CUENTAS_IG:
        print(f"  -> @{cuenta}...")
        try:
            r = requests.post(
                "https://api.apify.com/v2/acts/apify~instagram-scraper/runs",
                json={"usernames": [cuenta], "resultsType": "posts", "resultsLimit": 6},
                headers=headers, timeout=30
            )
            data = r.json()
            if "data" not in data:
                resultados[cuenta] = []
                continue
            run_id = data["data"]["id"]
            dataset_id = data["data"]["defaultDatasetId"]
            for _ in range(24):
                time.sleep(5)
                st = requests.get(f"https://api.apify.com/v2/acts/apify~instagram-scraper/runs/{run_id}", headers=headers).json()
                estado = st["data"]["status"]
                print(f"     {estado}")
                if estado == "SUCCEEDED": break
                if estado in ["FAILED","ABORTED"]: break
            items = requests.get(f"https://api.apify.com/v2/datasets/{dataset_id}/items", headers=headers).json()
            top = sorted(items, key=lambda x: x.get("likesCount",0) + x.get("commentsCount",0)*3, reverse=True)[:3]
            resultados[cuenta] = top
            print(f"     OK: {len(top)} posts")
        except Exception as e:
            print(f"     ERROR: {e}")
            resultados[cuenta] = []
    return resultados
 
def generar_prompt(datos):
    resumen = ""
    for cuenta, posts in datos.items():
        resumen += f"\n@{cuenta}: {len(posts)} posts\n"
        for i, p in enumerate(posts, 1):
            likes = p.get("likesCount", 0)
            comments = p.get("commentsCount", 0)
            caption = str(p.get("caption") or "")[:200]
            resumen += f"  {i}. Likes:{likes} Comentarios:{comments} | {caption}\n"
 
    fecha = datetime.now().strftime("%A %d de %B de %Y")
    hora = datetime.now().strftime("%H:%M")
    dias = ["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado","Domingo"]
    dia_actual = dias[datetime.now().weekday()]
 
    if MODO_URGENTE:
        return f"""Eres el jefe de contenido y guionista de Max Collao. Ex periodista TV chilena 14 anos. Creador digital 117K Instagram @maxcollao.
 
MODO URGENTE - {fecha} {hora}
Acaba de explotar el tema: "{TEMA_URGENTE}"
 
Genera INMEDIATAMENTE:
 
=== LIBRETO URGENTE - REEL/SHORT (60 seg) ===
Hook (primeras 3 segundos):
Desarrollo (lo que dice Max exactamente, con ritmo):
Cierre y CTA:
Camara: frente / selfie / walking
Locacion: donde grabarlo ahora
Texto en pantalla:
Hashtags urgentes:
Publicar en: [redes y orden]
Publicar a las: [hora exacta de hoy]
 
=== LIBRETO URGENTE - VERSION LARGA YOUTUBE (si aplica) ===
Hook:
Introduccion (30 seg):
Desarrollo (punto 1, punto 2, punto 3):
Cierre y CTA:
 
=== HISTORIA DE SEGUIMIENTO ===
Historia 1: [texto exacto]
Historia 2: [texto exacto]
Historia 3: CTA final
 
=== ANGULO DE MAX ===
Como abordar este tema con el estilo de Max: astuto, periodistico, sin atacar directamente a nadie, siendo la voz de los que no tienen voz.
 
IMPORTANTE: Este tema tiene maximo 24 horas de vida util. Grabar HOY.
 
Responde en espanol chileno. Directo y urgente."""
 
    return f"""Eres el jefe de contenido y guionista de Max Collao. Ex periodista TV chilena 14 anos. Creador digital 117K Instagram @maxcollao. Hoy es {fecha}, son las {hora}. Dia actual: {dia_actual}.
 
REGLA DE ORO: Todo el contenido debe tener maxima 24-48 horas de antiguedad. Nada viejo. Si un tema tiene mas de 48 horas NO lo incluyas.
 
DATOS COMPETENCIA (ultimos posts):
{resumen if resumen else "Sin datos de competencia disponibles."}
 
Genera el BRIEFING SEMANAL COMPLETO con libretos. Estructura OBLIGATORIA:
 
=== BLOQUE 1: TV Y FARANDULA ===
Que pasa HOY en matinales, teleseries, figuras TV chilena. Solo temas de las ultimas 48 horas.
Angulo de Max: astuto, nunca ataque directo. Tipo "Lo que nadie menciono sobre X".
2 ideas de reels con sus libretos completos.
 
=== BLOQUE 2: LA DENUNCIA DEL DIA ===
3 CASOS reales de las ultimas 24 horas: injusticias, estafas, abusos, noticias que indignan a Chile.
Para CADA caso entrega:
 
CASO [N]: [TITULO EN MAYUSCULAS]
El hecho: [que paso exactamente]
Por que indigna: [el angulo emocional]
Dato duro: [estadistica o cifra que golpea]
Potencial viral: [del 1 al 10]
Conviene porque: [argumento especifico de por que esta semana]
 
LIBRETO VERSION YOUTUBE LARGO (5-8 min):
- Hook primeros 30 seg (lo que detiene al espectador)
- Introduccion del caso (1 min)
- Desarrollo: punto 1, punto 2, punto 3 (3 min)
- Casos similares / estadistica (1 min)
- Cierre emocional y CTA (30 seg)
 
LIBRETO VERSION SHORT/REEL (60-90 seg):
- Hook (primeras 3 palabras que detienen el scroll)
- El caso en 3 golpes
- Cierre y CTA
- Texto en pantalla
- Hashtags
 
RECOMENDACION FINAL DENUNCIA:
Cual de los 3 casos elegir y por que esta semana especificamente.
 
=== BLOQUE 3: VIRALES INTERNET Y TIKTOK ===
Solo tendencias de las ultimas 24 horas. Personajes reventando sin TV. Trends, audios virales, memes en Chile/Latam.
2 ideas de como Max se sube a estos trends con su estilo.
Libreto completo para cada idea.
 
=== BLOQUE 4: EL PODER DE TU MENSAJE ===
 
REEL DE COMUNICACION:
REEL EL PODER DE TU MENSAJE:
Tema: [conectar un hecho noticioso o trend de esta semana con un error de comunicacion que todos cometemos]
Hook (primeras 3 palabras que detienen el scroll):
Libreto completo (60 seg, tono didactico, apuntar a camara):
CTA final: "Si quieres aprender a comunicar sin perder el control, escríbeme directo: wa.me/56996722300"
Plataformas: Instagram + Facebook + TikTok + YouTube Shorts
Dia de grabacion: LUNES
Dia de publicacion: VIERNES 20:00
 
CARRUSEL INSTAGRAM/LINKEDIN/FACEBOOK:
Concepto: [tip de comunicacion aplicable a cualquier persona]
Titulo del carrusel:
Slide 1 (portada): texto exacto [impactante, que genere guardado]
Slide 2: texto exacto
Slide 3: texto exacto
Slide 4: texto exacto
Slide 5: texto exacto
Slide 6 (CTA): "Comunicar bien no es hablar mas. Es hablar mejor. Escríbeme: wa.me/56996722300 @maxcollao"
Plataformas: Instagram + LinkedIn + Facebook
Dia de publicacion: SABADO 11:00
 
POST LINKEDIN - EL PODER DE TU MENSAJE:
RECOMENDACION: [por que este tema especifico funciona esta semana en LinkedIn, que tipo de profesional lo necesita leer]
POST COMPLETO LISTO PARA PUBLICAR:
Primera linea (detiene el scroll, sin mencionar farándula ni TV):
Desarrollo (3 parrafos, tono profesional cercano, ejemplos del mundo laboral):
CTA final: "¿Quieres entrenar tu comunicacion profesional? Conversemos: wa.me/56996722300"
Hashtags LinkedIn: [5 hashtags relevantes]
Plataforma: Solo LinkedIn
Dia de publicacion: JUEVES 13:00 (misma hora que el reel de farandula para no saturar IG)
 
HISTORIA CTA TALLER:
Historia 1: texto exacto + indicacion visual (mostrar pantalla del taller o grabar mirando camara)
Historia 2: texto exacto + testimonio o resultado concreto
Historia 3: "¿Quieres comunicar mejor? Escríbeme directo 👇" + Link wa.me/56996722300
Tipo: ESPONTANEA
Dia y hora: VIERNES 20:30 (despues de publicar el reel)
Plataformas: Instagram Stories + Facebook Stories
 
=== BLOQUE 5: INFLUENCERS SIN TV ===
Quienes la estan rompiendo en Chile digital en las ultimas 48 horas. Que les funciona. Oportunidades para Max.
1 idea de contenido basada en lo que esta funcionando en este mundo.
 
=== BLOQUE 6: IDEA ESTRELLA DE LA SEMANA ===
La idea con MAYOR potencial viral para @maxcollao esta semana. Desarrollala al maximo:
 
CONCEPTO: [nombre pegajoso y memorable]
POR QUE VA A REVENTAR: [razon especifica de por que explota ESTA semana, no otra]
FORMATO Y DURACION: [exacto]
PLATAFORMA PRINCIPAL: [con justificacion del algoritmo]
HOOK DE APERTURA: [primera frase EXACTA que Max dice o escribe - que detenga el scroll]
LIBRETO COMPLETO: [de principio a fin con indicaciones de ritmo, pausas, enfasis]
CIERRE Y CTA: [como termina exactamente]
REPURPOSING EN 5 PLATAFORMAS:
  - Instagram: como adaptarlo
  - TikTok: como adaptarlo
  - YouTube: como adaptarlo
  - Facebook: como adaptarlo
  - LinkedIn: como adaptarlo
NIVEL DE URGENCIA: [por que grabar ESTA semana y no la siguiente]
POTENCIAL DE VIRALIDAD: [del 1 al 10 con justificacion detallada]
 
=== TEXTOS PARA X (TWITTER) ===
Solo para piezas de contingencia y noticias. No para entretenimiento ni taller.
Para cada pieza que aplique:

TEXTO X - [TITULO PIEZA]
Opcion A (tweet simple, maximo 280 caracteres): [texto con gancho]
Opcion B (hilo 3 tweets): Tweet 1: / Tweet 2: / Tweet 3:

=== PLAN SEMANAL DIA A DIA ===
REGLA ABSOLUTA SIN EXCEPCIONES:
- TODOS los eventos grabacion_reel, grabacion_youtube, grabacion_historia DEBEN tener fecha del LUNES. SIN EXCEPCION.
- TODOS los eventos edicion y preparar_textos DEBEN tener fecha del MARTES. SIN EXCEPCION.
- MIERCOLES a DOMINGO = solo publicaciones, historias espontaneas y estrenos.
- JUEVES 19:00 = ESTRENO MaxStage (ya grabado, solo subir)
- VIERNES 18:00 = ESTRENO Se Viene (ya grabado, solo subir)
- JAMAS distribuir grabaciones en otros dias. TODO se graba el lunes. TODO se edita el martes.

Para cada pieza de contenido:

PIEZA [N] | [TITULO]
Seccion: [a que bloque pertenece]
Formato: REEL / VIDEO YOUTUBE / HISTORIA / CARRUSEL / POST LINKEDIN
Plataformas: [lista exacta con todas las redes]
Duracion: [exacta]
Dia de grabacion: LUNES a las [hora] (tipo: grabacion_reel / grabacion_youtube / grabacion_historia)
Dia de edicion: MARTES a las [hora]
Dia de publicacion: [dia] a las [hora segun metricas: reels 13:00 o 20:00, YouTube 19:00, taller 20:00]
Nota de produccion: [camara, ropa, energia]

=== HISTORIAS DE LA SEMANA ===
Para Instagram y Facebook. Minimo 3 secuencias.
Cada historia incluye dia Y hora exacta de publicacion.
Las PRE-GRABADAS se graban el lunes en batch junto a todo lo demas.
Las ESPONTANEAS se graban en el momento que corresponde.

SECUENCIA [N] - [TEMA]
Tipo: PRE-GRABADA (lunes) o ESPONTANEA (tiempo real)
Dia y hora de publicacion: [dia exacto] a las [hora exacta]
Historia 1: [texto exacto + indicacion visual]
Historia 2: [texto exacto + indicacion visual]
Historia 3: [CTA exacto con link si aplica]
Vinculo con: [que reel o post apoya]

=== CALENDARIO JSON ===
CALENDARIO_JSON_INICIO
[
  {{"titulo": "GRABAR HISTORIA: Anticipacion semana", "fecha": "LUNES", "hora_inicio": "09:00", "hora_fin": "09:30", "descripcion": "Batch historias pre-grabables de la semana.", "tipo": "grabacion_historia", "plataformas": ["Instagram Stories", "Facebook Stories"]}},
  {{"titulo": "GRABAR VIDEO YOUTUBE: [titulo exacto del video]", "fecha": "LUNES", "hora_inicio": "10:00", "hora_fin": "11:30", "descripcion": "Horizontal 8-10 min. Camisa si tema serio, polera si liviano.", "tipo": "grabacion_youtube", "plataformas": ["YouTube", "YouTube Shorts"]}},
  {{"titulo": "GRABAR REEL: [titulo exacto]", "fecha": "LUNES", "hora_inicio": "11:30", "hora_fin": "12:15", "descripcion": "Vertical 60-90 seg.", "tipo": "grabacion_reel", "plataformas": ["Instagram", "TikTok", "YouTube Shorts", "Facebook"]}},
  {{"titulo": "EDITAR: [titulo] Largo + Short", "fecha": "MARTES", "hora_inicio": "10:00", "hora_fin": "13:00", "descripcion": "Video largo + short. Mover a youtube-agent/listos/", "tipo": "edicion", "plataformas": ["YouTube"]}},
  {{"titulo": "PREPARAR TEXTOS: [titulo] X + Carrusel + LinkedIn", "fecha": "MARTES", "hora_inicio": "17:00", "hora_fin": "18:00", "descripcion": "Texto X hilo 3 tweets, carrusel 6 slides, post LinkedIn.", "tipo": "preparar_textos", "plataformas": ["X", "Instagram", "LinkedIn"]}},
  {{"titulo": "PUBLICAR HISTORIA: Anticipacion video", "fecha": "MIERCOLES", "hora_inicio": "09:00", "hora_fin": "09:05", "descripcion": "Historia pre-grabada del lunes anunciando el video.", "tipo": "publicacion_historia", "plataformas": ["Instagram Stories", "Facebook Stories"]}},
  {{"titulo": "PUBLICAR VIDEO YOUTUBE: [titulo exacto]", "fecha": "MIERCOLES", "hora_inicio": "19:00", "hora_fin": "19:15", "descripcion": "Video largo + Short simultaneo.", "tipo": "publicacion_youtube", "plataformas": ["YouTube", "YouTube Shorts"]}},
  {{"titulo": "PUBLICAR EN X: [titulo exacto]", "fecha": "MIERCOLES", "hora_inicio": "19:00", "hora_fin": "19:05", "descripcion": "Hilo o tweet de contingencia publicado junto al video.", "tipo": "publicacion_x", "plataformas": ["X"]}},
  {{"titulo": "PUBLICAR REEL: [titulo exacto]", "fecha": "JUEVES", "hora_inicio": "13:00", "hora_fin": "13:15", "descripcion": "Reel en todas las plataformas.", "tipo": "publicacion_reel", "plataformas": ["Instagram", "TikTok", "YouTube Shorts", "Facebook"]}},
  {{"titulo": "ESTRENO MaxStage — Episodio semana", "fecha": "JUEVES", "hora_inicio": "19:00", "hora_fin": "19:15", "descripcion": "Ya grabado previamente. Solo subir o programar. NO requiere grabacion este dia. Corte highlights para IG y TikTok.", "tipo": "estreno", "plataformas": ["YouTube", "Instagram", "TikTok", "Facebook"]}},
  {{"titulo": "ESTRENO Se Viene — Episodio semana", "fecha": "VIERNES", "hora_inicio": "18:00", "hora_fin": "18:15", "descripcion": "Ya grabado previamente. Solo subir o programar. NO requiere grabacion este dia. Corte highlights para IG y TikTok.", "tipo": "estreno", "plataformas": ["YouTube", "Instagram", "TikTok", "Facebook"]}},
  {{"titulo": "PUBLICAR REEL: [titulo taller - El Poder de Tu Mensaje]", "fecha": "VIERNES", "hora_inicio": "20:00", "hora_fin": "20:15", "descripcion": "Reel taller conectado a noticia de la semana. CTA wa.me/56996722300", "tipo": "publicacion_reel", "plataformas": ["Instagram", "TikTok", "YouTube Shorts", "Facebook"]}},
  {{"titulo": "PUBLICAR HISTORIA CTA: Taller", "fecha": "VIERNES", "hora_inicio": "20:30", "hora_fin": "20:35", "descripcion": "3 historias espontaneas CTA al taller. Link wa.me/56996722300", "tipo": "publicacion_historia", "plataformas": ["Instagram Stories", "Facebook Stories"]}},
  {{"titulo": "PUBLICAR CARRUSEL: [titulo carrusel taller]", "fecha": "SABADO", "hora_inicio": "11:00", "hora_fin": "11:15", "descripcion": "Carrusel 6 slides tip de comunicacion. CTA taller.", "tipo": "publicacion_carrusel", "plataformas": ["Instagram", "LinkedIn", "Facebook"]}},
  {{"titulo": "PUBLICAR LINKEDIN: [titulo post taller]", "fecha": "JUEVES", "hora_inicio": "13:00", "hora_fin": "13:15", "descripcion": "Post profesional completo. Mismo tema del reel adaptado para ejecutivos.", "tipo": "publicacion_linkedin", "plataformas": ["LinkedIn"]}}
]
CALENDARIO_JSON_FIN

IMPORTANTE CALENDARIO: Reemplaza LUNES/MARTES/etc con las fechas reales de esta semana. Todos los eventos de grabacion van el lunes. Todos los de edicion el martes. Publicaciones en sus dias optimos.

Responde en espanol chileno natural. Directo, periodistico, con urgencia real. Sin argentinismos. Sin relleno."""
 
def generar_calendario_respaldo(texto):
    eventos = []
    hoy = datetime.now()
    lineas = texto.split('\n')
    piezas = []
    for linea in lineas:
        l = linea.strip()
        if l.startswith("PIEZA ") and "|" in l:
            partes = l.split("|")
            if len(partes) >= 2:
                piezas.append(partes[1].strip())
        elif l.startswith("REEL ") and " - " in l:
            piezas.append(l.split(" - ",1)[1].strip())
    if not piezas:
        piezas = ["Reel TV Farandula","La Denuncia del Dia","El Poder de Tu Mensaje","Viral de la Semana","Idea Estrella"]
    horas = ["10:00","11:30","14:00","10:00","11:00"]
    for i, pieza in enumerate(piezas[:6]):
        dia_grab = hoy + timedelta(days=i % 5)
        dia_pub = dia_grab + timedelta(days=1)
        hora = horas[i % len(horas)]
        hora_fin = f"{int(hora[:2])+1}:30"
        eventos.append({"titulo": f"GRABAR: {pieza}", "fecha": dia_grab.strftime("%Y-%m-%d"), "hora_inicio": hora, "hora_fin": hora_fin, "descripcion": f"Revisar libreto en briefing_lunes.html antes de grabar.", "tipo": "grabacion", "plataforma": "Instagram/TikTok"})
        eventos.append({"titulo": f"EDITAR: {pieza}", "fecha": dia_grab.strftime("%Y-%m-%d"), "hora_inicio": "15:00", "hora_fin": "17:00", "descripcion": "Editar y mover a carpeta youtube-agent/listos/", "tipo": "edicion", "plataforma": "Instagram/TikTok"})
        eventos.append({"titulo": f"PUBLICAR: {pieza}", "fecha": dia_pub.strftime("%Y-%m-%d"), "hora_inicio": "12:00", "hora_fin": "12:15", "descripcion": "El agente publica automaticamente al detectar el archivo.", "tipo": "publicacion", "plataforma": "Instagram/TikTok/YouTube"})
    return eventos
 
def analizar_con_claude(datos):
    print("\nGenerando briefing completo con libretos...")
    prompt = generar_prompt(datos)
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json={
                "model": "claude-opus-4-5",
                "max_tokens": 16000,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=600
        )
        print(f"  Claude API status: {r.status_code}")
        data = r.json()
        if r.status_code != 200:
            return f"Error API: {data.get('error',{}).get('message','desconocido')}", []
        texto = "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
        print(f"  Respuesta: {len(texto)} caracteres")
        eventos = []
        if "CALENDARIO_JSON_INICIO" in texto and "CALENDARIO_JSON_FIN" in texto:
            inicio = texto.index("CALENDARIO_JSON_INICIO") + len("CALENDARIO_JSON_INICIO")
            fin = texto.index("CALENDARIO_JSON_FIN")
            json_str = texto[inicio:fin].strip()
            try:
                eventos = json.loads(json_str)
                print(f"  Eventos calendario: {len(eventos)}")
            except Exception as e:
                print(f"  Error parseando calendario: {e}")
 
        # Si no hay eventos, generar calendario basico desde el texto
        if not eventos:
            print("  Generando calendario de respaldo...")
            eventos = generar_calendario_respaldo(texto)
            print(f"  Eventos calendario respaldo: {len(eventos)}")
 
        return texto, eventos
    except Exception as e:
        return f"Error: {e}", []
 
def guardar_eventos_calendario(eventos):
    if not eventos: return
    ruta = os.path.join(os.getcwd(), "calendario_semana.json")
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(eventos, f, ensure_ascii=False, indent=2)
        print(f"  Calendario: {ruta}")
    except:
        with open("calendario_semana.json", "w", encoding="utf-8") as f:
            json.dump(eventos, f, ensure_ascii=False, indent=2)
        print("  Calendario: calendario_semana.json")
 
def generar_html(analisis, datos, eventos):
    fecha = datetime.now().strftime("%d de %B de %Y")
    hora = datetime.now().strftime("%H:%M")
 
    comp_html = ""
    for cuenta, posts in datos.items():
        comp_html += f'<div class="card"><h4>@{cuenta}</h4>'
        if posts:
            for p in posts[:2]:
                likes = p.get("likesCount",0)
                comments = p.get("commentsCount",0)
                caption = str(p.get("caption") or "Sin caption")[:120]
                url = p.get("url","#")
                comp_html += f'<div class="post"><span class="m">Likes: {likes:,} | Comentarios: {comments:,}</span><p class="c">"{caption}..."</p><a href="{url}" target="_blank">Ver post</a></div>'
        else:
            comp_html += '<p class="c">Sin datos esta semana</p>'
        comp_html += '</div>'
 
    cal_html = ""
    colores = {
        "grabacion_reel":      "#ff6b00",
        "grabacion_youtube":   "#ef4444",
        "grabacion_historia":  "#f59e0b",
        "edicion":             "#8b5cf6",
        "preparar_textos":     "#a16207",
        "publicacion_reel":    "#10b981",
        "publicacion_youtube": "#1e3a8a",
        "publicacion_historia":"#ec4899",
        "publicacion_x":       "#9ca3af",
        "publicacion_linkedin":"#0077b5",
        "publicacion_carrusel":"#06b6d4",
        "estreno":             "#00d4ff",
        "grabacion":           "#ff6b00",
        "publicacion":         "#10b981",
    }
    labels = {
        "grabacion_reel":      "🎬 GRABAR REEL",
        "grabacion_youtube":   "📺 GRABAR VIDEO YOUTUBE",
        "grabacion_historia":  "📲 GRABAR HISTORIA",
        "edicion":             "✂️ EDITAR",
        "preparar_textos":     "✍️ PREPARAR TEXTOS",
        "publicacion_reel":    "🚀 PUBLICAR REEL",
        "publicacion_youtube": "📺 PUBLICAR VIDEO YOUTUBE",
        "publicacion_historia":"📲 PUBLICAR HISTORIA",
        "publicacion_x":       "✕ PUBLICAR EN X",
        "publicacion_linkedin":"💼 PUBLICAR LINKEDIN",
        "publicacion_carrusel":"🎨 PUBLICAR CARRUSEL",
        "estreno":             "⭐ ESTRENO",
        "grabacion":           "🎬 GRABAR",
        "publicacion":         "🚀 PUBLICAR",
    }
    plat_colors = {
        "Instagram": "#e1306c", "TikTok": "#69c9d0", "YouTube": "#ff0000",
        "YouTube Shorts": "#ff0000", "Facebook": "#3b5998", "X": "#9ca3af",
        "LinkedIn": "#0077b5", "Instagram Stories": "#e1306c",
        "Facebook Stories": "#3b5998",
    }
    for ev in eventos:
        tipo = ev.get("tipo", "grabacion")
        color = colores.get(tipo, "#ff6b00")
        label = labels.get(tipo, "TAREA")
        plataformas = ev.get("plataformas", [ev.get("plataforma", "")])
        if isinstance(plataformas, str):
            plataformas = [p.strip() for p in plataformas.split("/")]
        plat_badges = "".join(
            f'<span style="background:#1e1e1e;color:{plat_colors.get(p,"#aaa")};font-size:.65em;font-weight:700;padding:2px 7px;border-radius:6px;margin-right:3px">{p}</span>'
            for p in plataformas if p
        )
        cal_html += f'<div class="evento" style="border-left-color:{color}"><span class="ev-tipo" style="color:{color}">{label}</span><strong>{ev.get("titulo","")}</strong><span class="ev-hora">{ev.get("fecha","")} {ev.get("hora_inicio","")} - {ev.get("hora_fin","")}</span><p class="ev-desc">{ev.get("descripcion","")}</p><div style="margin-top:5px">{plat_badges}</div></div>'
 
    lineas = analisis.split('\n')
    contenido_html = ""
    for linea in lineas:
        if "CALENDARIO_JSON_INICIO" in linea: break
        l = linea.strip()
        if l.startswith("===") and l.endswith("==="):
            titulo = l.replace("===","").strip()
            icono = ""
            if "TV" in titulo or "FARANDULA" in titulo: icono = "TV y Farándula"
            elif "DENUNCIA" in titulo: icono = "La Denuncia del Día"
            elif "VIRAL" in titulo or "TIKTOK" in titulo: icono = "Virales & TikTok"
            elif "PODER" in titulo: icono = "El Poder de Tu Mensaje"
            elif "INFLUENCER" in titulo: icono = "Influencers sin TV"
            elif "ESTRELLA" in titulo: icono = "Idea Estrella"
            elif "PLAN" in titulo: icono = "Plan Semanal"
            elif "HISTORIA" in titulo: icono = "Historias"
            else: icono = titulo
            contenido_html += f'<h3 class="bloque-titulo">{icono}</h3>'
        elif l.startswith("CASO ") or l.startswith("PIEZA ") or l.startswith("REEL ") or l.startswith("SECUENCIA "):
            contenido_html += f'<div class="sub-bloque"><h4 class="sub-titulo">{l}</h4>'
        elif l.startswith("LIBRETO") or l.startswith("CARRUSEL") or l.startswith("POST LINKEDIN") or l.startswith("HISTORIA INSTAGRAM"):
            contenido_html += f'<div class="libreto-label">{l}</div><div class="libreto">'
        elif l.startswith("RECOMENDACION") or l.startswith("CONCEPTO:") or l.startswith("POR QUE VA A REVENTAR") or l.startswith("HOOK DE APERTURA") or l.startswith("NIVEL DE URGENCIA") or l.startswith("POTENCIAL DE VIRALIDAD"):
            contenido_html += f'<div class="highlight-line"><strong>{l}</strong></div>'
        elif l.startswith("Hashtags") or l.startswith("CTA"):
            contenido_html += f'<div class="hashtags">{l}</div>'
        elif l == "---":
            contenido_html += '</div><hr class="sep">'
        elif l == "":
            contenido_html += '<br>'
        else:
            contenido_html += f'{l}<br>'
 
    modo_badge = '<span class="urgente-badge">MODO URGENTE</span>' if MODO_URGENTE else '<span class="normal-badge">BRIEFING SEMANAL</span>'
 
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Briefing - Max Collao</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',sans-serif;background:#080808;color:#f0f0f0;padding:20px;max-width:1100px;margin:0 auto}}
.header{{background:linear-gradient(135deg,#ff6b00,#ff0080);padding:32px;border-radius:16px;margin-bottom:24px}}
.header h1{{font-size:2.4em;font-weight:900;letter-spacing:-1px}}
.header p{{opacity:.85;margin-top:6px;font-size:1.05em}}
.urgente-badge{{background:#ff0000;color:white;padding:5px 14px;border-radius:20px;font-size:.8em;font-weight:700;display:inline-block;margin-top:10px}}
.normal-badge{{background:rgba(255,255,255,.2);color:white;padding:5px 14px;border-radius:20px;font-size:.8em;font-weight:700;display:inline-block;margin-top:10px}}
.section{{background:#141414;border-radius:12px;padding:24px;margin-bottom:20px;border-left:4px solid #ff6b00}}
.section h2{{color:#ff6b00;margin-bottom:16px;font-size:1.15em;font-weight:700;text-transform:uppercase;letter-spacing:.5px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}
.card{{background:#1e1e1e;border-radius:10px;padding:14px}}
.card h4{{color:#ff6b00;margin-bottom:10px;font-size:.95em}}
.post{{border-top:1px solid #2a2a2a;padding-top:8px;margin-top:8px}}
.m{{font-size:.8em;color:#888;display:block}}
.c{{font-size:.78em;color:#bbb;margin:4px 0;font-style:italic}}
.post a{{color:#ff6b00;font-size:.78em;text-decoration:none}}
.contenido{{line-height:1.9;font-size:.93em}}
.bloque-titulo{{color:#ff6b00;font-size:1.15em;font-weight:900;margin:32px 0 16px;padding:12px 18px;background:#1a1a1a;border-radius:8px;border-left:4px solid #ff6b00;text-transform:uppercase;letter-spacing:.5px}}
.sub-bloque{{background:#1c1c2e;border:1px solid #2a2a3a;border-radius:10px;padding:18px;margin:14px 0}}
.sub-titulo{{color:#fff;font-size:1em;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #333}}
.libreto-label{{color:#ff6b00;font-size:.78em;font-weight:700;margin:14px 0 6px;text-transform:uppercase;letter-spacing:1px}}
.libreto{{background:#0d0d0d;border-radius:8px;padding:16px;font-size:.9em;line-height:1.9;color:#ddd;border-left:3px solid #ff6b00;margin-bottom:10px}}
.highlight-line{{background:#1a1500;border-left:3px solid #FFD700;padding:10px 14px;margin:8px 0;border-radius:4px}}
.highlight-line strong{{color:#FFD700}}
.hashtags{{color:#8b5cf6;font-size:.85em;margin:8px 0}}
.sep{{border:none;border-top:1px solid #2a2a2a;margin:14px 0}}
.evento{{background:#1a1a2a;border-left:4px solid #ff6b00;border-radius:8px;padding:14px;margin-bottom:10px}}
.ev-tipo{{font-size:.75em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;display:block;margin-bottom:4px}}
.ev-hora{{font-size:.8em;color:#888;display:block;margin:4px 0}}
.ev-desc{{font-size:.83em;color:#bbb;margin-top:6px}}
.footer{{text-align:center;opacity:.3;margin-top:40px;padding-bottom:40px;font-size:.8em}}
</style>
</head>
<body>
<div class="header">
  <h1>Max Collao</h1>
  <p>Briefing generado el {fecha} a las {hora}</p>
  {modo_badge}
</div>
 
{'<div class="section"><h2>Competencia esta semana</h2><div class="grid">' + comp_html + '</div></div>' if comp_html else ''}
 
{'<div class="section"><h2>Calendario de la semana</h2><div>' + cal_html + '</div></div>' if cal_html else ''}
 
<div class="section">
  <h2>Briefing completo + Libretos</h2>
  <div class="contenido">{contenido_html}</div>
</div>
 
<div class="footer">Sistema de contenido automatizado @maxcollao</div>
</body></html>"""
 
def main():
    print("="*55)
    if MODO_URGENTE:
        print(f"  MODO URGENTE: {TEMA_URGENTE}")
    else:
        print("  BRIEFING SEMANAL COMPLETO - MAX COLLAO")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("="*55)
 
    datos = obtener_posts()
 
    if not ANTHROPIC_API_KEY:
        print("FALTA ANTHROPIC_API_KEY")
        print("Ejecuta: set ANTHROPIC_API_KEY=tu_key")
        return
 
    analisis, eventos = analizar_con_claude(datos)
    guardar_eventos_calendario(eventos)
 
    html = generar_html(analisis, datos, eventos)
    nombre = "briefing_urgente.html" if MODO_URGENTE else "briefing_lunes.html"
    ruta = os.path.join(os.getcwd(), nombre)
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\nGuardado: {ruta}")
    except:
        with open(nombre, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\nGuardado: {nombre}")
 
    print(f"Eventos calendario: {len(eventos)}")
    print(f"Abre con: start {nombre}")

    if MODO_URGENTE:
        print("\nEnviando libreto a Telegram...")
        enviar_libreto_telegram(analisis, TEMA_URGENTE)

    # Sincronizar con Google Calendar
    try:
        from sincronizar_calendario import sincronizar
        sincronizar()
    except Exception as e:
        print(f"\nGoogle Calendar: {e}")
        print("Corre manualmente: python sincronizar_calendario.py")
 
if __name__ == "__main__":
    main()
 
