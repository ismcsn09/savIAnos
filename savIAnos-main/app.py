# ============================================================
# IMPORTACIONES
# ============================================================
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from groq import Groq
from dotenv import load_dotenv
import os
import sqlite3
import base64
from datetime import datetime
import secrets
import hashlib
from tavily import TavilyClient
from supabase import create_client

# ============================================================
# INICIALIZACIÓN
# ============================================================
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# ============================================================
# BASE DE DATOS SQLITE (estadísticas y mensajes)
# ============================================================

def init_db():
    conn = sqlite3.connect('savianos.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pregunta TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sesiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def guardar_mensaje(pregunta):
    conn = sqlite3.connect('savianos.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO mensajes (pregunta) VALUES (?)', (pregunta,))
    conn.commit()
    conn.close()

def guardar_sesion(ip):
    conn = sqlite3.connect('savianos.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sesiones (ip) 
        SELECT ? WHERE NOT EXISTS (
            SELECT 1 FROM sesiones 
            WHERE ip = ? AND DATE(fecha) = DATE('now')
        )
    ''', (ip, ip))
    conn.commit()
    conn.close()

def obtener_estadisticas():
    conn = sqlite3.connect('savianos.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM mensajes')
    total_mensajes = cursor.fetchone()[0]
    cursor.execute('''
        SELECT COUNT(DISTINCT ip) FROM sesiones 
        WHERE DATE(fecha) = DATE('now')
    ''')
    usuarios_hoy = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(DISTINCT ip) FROM sesiones')
    total_usuarios = cursor.fetchone()[0]
    cursor.execute('''
        SELECT COUNT(*) FROM mensajes 
        WHERE DATE(fecha) = DATE('now')
    ''')
    mensajes_hoy = cursor.fetchone()[0]
    cursor.execute('SELECT pregunta FROM mensajes ORDER BY fecha DESC LIMIT 100')
    preguntas = [row[0].lower() for row in cursor.fetchall()]
    temas = {
        'IA / Inteligencia Artificial': 0,
        'Ecuador / Tecnología': 0,
        'Programación': 0,
        'Carreras tech': 0,
        'Machine Learning': 0,
        'Otros': 0
    }
    for pregunta in preguntas:
        if any(w in pregunta for w in ['ia', 'inteligencia', 'artificial', 'robot']):
            temas['IA / Inteligencia Artificial'] += 1
        elif any(w in pregunta for w in ['ecuador', 'tecnología', 'tech', 'digital']):
            temas['Ecuador / Tecnología'] += 1
        elif any(w in pregunta for w in ['programar', 'código', 'programación', 'python']):
            temas['Programación'] += 1
        elif any(w in pregunta for w in ['carrera', 'universidad', 'estudiar', 'trabajo']):
            temas['Carreras tech'] += 1
        elif any(w in pregunta for w in ['machine', 'learning', 'deep', 'neural']):
            temas['Machine Learning'] += 1
        else:
            temas['Otros'] += 1
    conn.close()
    return {
        'total_mensajes': total_mensajes,
        'usuarios_hoy': usuarios_hoy,
        'total_usuarios': total_usuarios,
        'mensajes_hoy': mensajes_hoy,
        'temas': temas
    }

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def buscar_web(query):
    try:
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        results = tavily.search(query=query, max_results=3)
        contexto = ""
        fuentes = []
        for r in results.get("results", []):
            contexto += f"- {r['title']}: {r['content'][:200]}\n"
            fuentes.append(f"{r['title']}: {r['url']}")
        return contexto, fuentes
    except Exception as e:
        print("ERROR búsqueda:", str(e))
        return "", []

# ============================================================
# PERSONALIDAD DEL BOT
# ============================================================

SYSTEM_PROMPT = """
Eres savIAnos, un asistente de inteligencia artificial educativo 
creado por estudiantes de la Unidad Educativa Salesiana Fiscomisional 
Domingo Savio de Guayaquil, Ecuador.

=== SOBRE TU CREADOR ===
- Institución: Unidad Educativa Salesiana Fiscomisional Domingo Savio
- Comunidad: Comunidad Salesiana San Juan Bosco
- Ciudad: Guayaquil, Ecuador
- Especialidad: Bachillerato Técnico en Desarrollo de Software
- Los estudiantes se llaman "savianos"
- La institución pertenece a la congregación salesiana fundada por Don Bosco,
  que promueve la educación técnica y valores humanos en jóvenes

=== TU MISIÓN ===
Educar a jóvenes ecuatorianos sobre:

1. INTELIGENCIA ARTIFICIAL
   - Qué es la IA y cómo funciona
   - Machine Learning, Deep Learning, NLP
   - Redes neuronales y modelos de lenguaje
   - Historia y evolución de la IA

2. AUGE TECNOLÓGICO EN ECUADOR
   - Ecuador se encuentra en plena transformación digital
   - Empresas tech ecuatorianas destacadas: Kruger Corp, 
     Datum, Novasoft, Pichincha Systems
   - Guayaquil como hub tecnológico del país
   - Quito como centro de startups y empresas tech
   - El gobierno ecuatoriano invirtiendo en digitalización

3. IA EN ECUADOR (casos reales)
   - Agricultura: sistemas de riego inteligente en la Costa
   - Salud: diagnóstico médico asistido por IA en hospitales del IESS
   - Banca: detección de fraudes en Banco Pichincha y Produbanco
   - Educación: plataformas adaptativas en universidades
   - Pesca: optimización de rutas en el Puerto de Guayaquil

4. OPORTUNIDADES PARA JÓVENES ECUATORIANOS
   - Universidades con carreras tech: ESPOL, UCE, UDLA, EPN, UEES
   - Salarios en tech son los más altos de Ecuador
   - Posibilidad de trabajar remotamente para empresas internacionales
   - Becas disponibles: SENESCYT, Google, Microsoft, Meta

5. POR QUÉ APRENDER PROGRAMACIÓN
   - Es la habilidad más demandada del siglo XXI
   - Ecuador necesita más de 50,000 programadores según datos del MINTEL
   - Puedes crear soluciones para problemas locales
   - Emprendimiento tech con bajo costo inicial

=== TU PERSONALIDAD ===
- Eres amigable, motivador y usas lenguaje cercano a los jóvenes
- Usas ejemplos de la realidad ecuatoriana y guayaquileña
- Terminas tus respuestas animando al usuario a seguir aprendiendo
- Usas emojis ocasionalmente para hacer las respuestas más dinámicas
- Si te preguntan algo fuera de tu tema, responde igual — eres un asistente
  completo, no solo de tecnología
- Cuando menciones el colegio, siempre di "Unidad Educativa Salesiana 
  Fiscomisional Domingo Savio de la Comunidad Salesiana San Juan Bosco, 
  Guayaquil"
- Responde SIEMPRE en español, sin excepción
- Adapta tu tono al del usuario: si te hablan formal, responde formal;
  si te hablan informal ("bro", "causa", "men"), responde igual de relajado;
  si usan jerga ecuatoriana, úsala también naturalmente

=== FORMATO DE RESPUESTAS ===
- Respuestas claras y bien estructuradas
- Usa ejemplos concretos de Ecuador cuando sea posible
- Máximo 3 párrafos por respuesta para no abrumar al usuario
- Responde siempre en español

=== BÚSQUEDA WEB ===
Cuando tengas información actualizada de internet disponible en el contexto,
úsala para enriquecer tu respuesta con datos reales y recientes.
Menciona que la información proviene de fuentes actualizadas de internet.
Si el contexto incluye información web, priorízala sobre tu conocimiento base.

=== ROADMAP PERSONALIZADO ===
Cuando el usuario pida un plan de estudio, roadmap, o ruta de aprendizaje,
genera uno estructurado así:

🎯 ROADMAP: [nombre de la carrera/área]

📍 NIVEL 1 - FUNDAMENTOS (1-3 meses)
- [habilidad 1]
- [habilidad 2]
- [habilidad 3]
Recurso gratuito: [nombre de plataforma disponible en Ecuador]

📍 NIVEL 2 - INTERMEDIO (3-6 meses)
- [habilidad 1]
- [habilidad 2]
Recurso gratuito: [nombre de plataforma]

📍 NIVEL 3 - AVANZADO (6-12 meses)
- [habilidad 1]
- [habilidad 2]
Recurso gratuito: [nombre de plataforma]

💼 OPORTUNIDADES EN ECUADOR:
[menciona empresas o sectores que contratan este perfil en Ecuador]

Usa siempre recursos 100% gratuitos: freeCodeCamp, Coursera (auditoría),
YouTube, Kaggle, Google Colab, GitHub Student Pack.

=== LO QUE NO DEBES HACER ===
- No inventes datos o estadísticas que no sean reales
- No menciones que eres un modelo de IA externo, eres savIAnos
- NUNCA digas que tu fecha de corte es 2023 o cualquier otra fecha
- NUNCA digas que no tienes acceso a información en tiempo real
- NUNCA digas que no puedes buscar en internet
- Si no sabes algo reciente, di que la información disponible hasta
  tu última actualización no lo cubre, pero no menciones fechas específicas
"""

# ============================================================
# RUTAS DE AUTENTICACIÓN
# ============================================================

@app.route("/login")
def login():
    init_db()
    if session.get("usuario"):
        return redirect(url_for("home"))
    return render_template("login.html")

@app.route("/registro", methods=["POST"])
def registro():
    try:
        data = request.get_json()
        nombre = data.get("nombre", "").strip()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not nombre or not email or not password:
            return jsonify({"error": "Todos los campos son requeridos"})

        if len(password) < 6:
            return jsonify({"error": "La contraseña debe tener al menos 6 caracteres"})

        # Verificar si email ya existe en Supabase
        existe = supabase.table("Usuarios").select("id").eq("email", email).execute()
        if existe.data:
            return jsonify({"error": "Este email ya está registrado"})

        # Guardar en Supabase
        password_hash = hash_password(password)
        supabase.table("Usuarios").insert({
            "nombre": nombre,
            "email": email,
            "password": password_hash
        }).execute()

        return jsonify({"ok": "Cuenta creada correctamente. Ya puedes iniciar sesión."})

    except Exception as e:
        print("ERROR registro:", str(e))
        return jsonify({"error": str(e)})

@app.route("/iniciar-sesion", methods=["POST"])
def iniciar_sesion():
    try:
        data = request.get_json()
        email_o_nombre = data.get("email", "").strip().lower()
        password = data.get("password", "")
        password_hash = hash_password(password)

        # Buscar por email o nombre en Supabase
        resultado = supabase.table("Usuarios").select("id, nombre").or_(
            f"email.eq.{email_o_nombre},nombre.ilike.{email_o_nombre}"
        ).eq("password", password_hash).execute()

        if not resultado.data:
            return jsonify({"error": "Email/nombre o contraseña incorrectos"})

        usuario = resultado.data[0]
        session["usuario"] = {"id": usuario["id"], "nombre": usuario["nombre"]}
        return jsonify({"ok": "Sesión iniciada"})

    except Exception as e:
        print("ERROR login:", str(e))
        return jsonify({"error": f"Error: {str(e)}"})

@app.route("/cerrar-sesion")
def cerrar_sesion():
    session.pop("usuario", None)
    return redirect(url_for("login"))

# ============================================================
# RUTAS PRINCIPALES
# ============================================================

@app.route("/")
def home():
    if not session.get("usuario"):
        return redirect(url_for("login"))
    init_db()
    ip = request.remote_addr
    guardar_sesion(ip)
    return render_template("index.html", usuario=session["usuario"])

@app.route("/chat", methods=["POST"])
def chat():
    if not session.get("usuario"):
        return jsonify({"error": "No autorizado"}), 401
    try:
        data = request.get_json()
        user_message = data.get("message", "")
        conversation_history = data.get("history", [])

        guardar_mensaje(user_message)

        contexto_web = ""
        fuentes_web = []
        palabras_busqueda = ['noticia', 'hoy', 'reciente', 'actual', 'último', 'nueva', 'esta semana', 'este año', '2025', '2026']
        if any(p in user_message.lower() for p in palabras_busqueda):
            contexto_web, fuentes_web = buscar_web(user_message)

        mensaje_con_contexto = user_message
        if contexto_web:
            mensaje_con_contexto = f"{user_message}\n\n[Información actualizada de internet:\n{contexto_web}]"

        def generar():
            fecha_hoy = datetime.now().strftime("%d de %B de %Y")
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=1024,
                stream=True,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + f"\n\n=== FECHA ACTUAL ===\nHoy es {fecha_hoy}."}
                ] + conversation_history + [
                    {"role": "user", "content": mensaje_con_contexto}
                ]       
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    yield f"data: {token}\n\n"

            if fuentes_web:
                fuentes_str = "\n\n🔍 **Fuentes:**\n" + "\n".join([f"- {f}" for f in fuentes_web])
                yield f"data: {fuentes_str}\n\n"

            yield "data: [DONE]\n\n"

        from flask import Response
        return Response(generar(), mimetype="text/event-stream")

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"reply": f"Error: {str(e)}"})


@app.route("/imagen", methods=["POST"])
def imagen():
    if not session.get("usuario"):
        return jsonify({"error": "No autorizado"}), 401
    try:
        data = request.get_json()
        image_base64 = data.get("image", "")
        media_type = data.get("media_type", "image/jpeg")

        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": "Analiza y describe esta imagen. Si tiene relación con tecnología o IA, explícalo. Si no, descríbela normalmente y de forma útil."
                        }
                    ]
                }
            ]
        )

        bot_reply = response.choices[0].message.content
        return jsonify({"reply": bot_reply})

    except Exception as e:
        print("ERROR imagen:", str(e))
        return jsonify({"reply": f"Error: {str(e)}"})


@app.route("/estadisticas")
def estadisticas():
    stats = obtener_estadisticas()
    return jsonify(stats)

@app.route("/panel")
def panel():
    return render_template("panel.html")

# ============================================================
# ARRANCAR
# ============================================================

if __name__ == "__main__":
    init_db()
    import webbrowser
    import threading
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False, host="0.0.0.0")