# ============================================================
# IMPORTACIONES
# ============================================================
from flask import Flask, render_template, request, jsonify
from groq import Groq
from dotenv import load_dotenv
import os
import sqlite3
# sqlite3 es la base de datos incluida en Python
# guarda los datos en un archivo .db
import base64
# base64 para convertir imágenes a texto y enviarlas
from datetime import datetime
# datetime nos permite guardar la fecha y hora de cada mensaje
import base64
import requests

# ============================================================
# INICIALIZACIÓN
# ============================================================
load_dotenv()
app = Flask(__name__)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ============================================================
# BASE DE DATOS
# ============================================================

def init_db():
    # Crea las tablas si no existen
    conn = sqlite3.connect('savianos.db')
    cursor = conn.cursor()
    
    # Tabla de mensajes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pregunta TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de sesiones (usuarios únicos)
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
    # Guarda cada pregunta en la base de datos
    conn = sqlite3.connect('savianos.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO mensajes (pregunta) VALUES (?)', (pregunta,))
    conn.commit()
    conn.close()

def guardar_sesion(ip):
    # Guarda la IP del usuario si es nueva hoy
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
    # Obtiene todas las estadísticas
    conn = sqlite3.connect('savianos.db')
    cursor = conn.cursor()
    
    # Total de mensajes
    cursor.execute('SELECT COUNT(*) FROM mensajes')
    total_mensajes = cursor.fetchone()[0]
    
    # Usuarios únicos hoy
    cursor.execute('''
        SELECT COUNT(DISTINCT ip) FROM sesiones 
        WHERE DATE(fecha) = DATE('now')
    ''')
    usuarios_hoy = cursor.fetchone()[0]
    
    # Total de usuarios únicos
    cursor.execute('SELECT COUNT(DISTINCT ip) FROM sesiones')
    total_usuarios = cursor.fetchone()[0]
    
    # Mensajes de hoy
    cursor.execute('''
        SELECT COUNT(*) FROM mensajes 
        WHERE DATE(fecha) = DATE('now')
    ''')
    mensajes_hoy = cursor.fetchone()[0]
    
    # Palabras más frecuentes en las preguntas
    cursor.execute('SELECT pregunta FROM mensajes ORDER BY fecha DESC LIMIT 100')
    preguntas = [row[0].lower() for row in cursor.fetchall()]
    
    # Contamos temas frecuentes
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
- Si te preguntan algo fuera de tu tema, redirige amablemente 
  hacia el mundo de la IA y la tecnología
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

=== GENERACIÓN DE IMÁGENES ===
Cuando el usuario pida generar, crear o dibujar una imagen, responde ÚNICAMENTE
con este formato exacto y nada más:
GENERAR_IMAGEN: [descripción en inglés detallada de la imagen]

No agregues texto antes ni después, solo la línea GENERAR_IMAGEN.



=== LO QUE NO DEBES HACER ===
- No inventes datos o estadísticas que no sean reales
- No hables de temas que no sean tecnología e IA
- No menciones que eres un modelo de IA externo, eres savIAnos
"""

# ============================================================
# RUTAS
# ============================================================

@app.route("/")
def home():
    init_db()
    # Inicializa la base de datos si no existe
    ip = request.remote_addr
    guardar_sesion(ip)
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message", "")
        conversation_history = data.get("history", [])

        # Guardamos la pregunta en la base de datos
        guardar_mensaje(user_message)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT}
            ] + conversation_history + [
                {"role": "user", "content": user_message}
            ]
        )

        bot_reply = response.choices[0].message.content
        return jsonify({"reply": bot_reply})

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"reply": f"Error: {str(e)}"})
    

@app.route("/imagen", methods=["POST"])
def imagen():
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
    
@app.route("/generar-imagen", methods=["POST"])
def generar_imagen():
        try:
            data = request.get_json()
            prompt = data.get("prompt", "")
            hf_token = os.getenv("HF_TOKEN")
            api_url = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-2-1"
            headers = {"Authorization": f"Bearer {hf_token}"}
            payload = {"inputs": prompt}
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            img_base64 = base64.b64encode(response.content).decode('utf-8')
            return jsonify({"image": img_base64})
        except Exception as e:
            print("ERROR generar imagen:", str(e))
            return jsonify({"error": str(e)})
    
@app.route("/estadisticas")
def estadisticas():
    # Ruta que devuelve las estadísticas en JSON
    stats = obtener_estadisticas()
    return jsonify(stats)

@app.route("/panel")
def panel():
    # Página del panel de estadísticas
    return render_template("panel.html")

# ============================================================
# ARRANCAR
# ============================================================

if __name__ == "__main__":
    init_db()
    # Inicializamos la base de datos al arrancar
    import webbrowser
    import threading
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False, host="0.0.0.0")