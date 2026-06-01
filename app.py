# ============================================================
# IMPORTACIONES
# ============================================================

from flask import Flask, render_template, request, jsonify
from groq import Groq
from dotenv import load_dotenv
import os
# os y dotenv nos permiten leer variables del archivo .env

load_dotenv()
# Carga las variables del archivo .env

app = Flask(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
# os.getenv() lee la key del archivo .env
# en lugar de tenerla escrita directamente
# ============================================================
# PERSONALIDAD DEL BOT
# ============================================================

SYSTEM_PROMPT = """
Eres savIAnos, un asistente de inteligencia artificial educativo 
creado por estudiantes del Colegio Técnico Domingo Savio de Ecuador.

Tu misión es educar sobre:
- Qué es la inteligencia artificial y cómo funciona
- El auge tecnológico que vive Ecuador actualmente
- Casos reales donde la IA está siendo usada en Ecuador 
  (agricultura, salud, finanzas, educación)
- Oportunidades de carrera en tecnología para jóvenes ecuatorianos
- La importancia de aprender programación e IA desde el colegio

Tu personalidad:
- Eres amigable, motivador y usas un lenguaje cercano a los jóvenes
- Siempre que puedas, conectas los temas con la realidad ecuatoriana
- Terminas tus respuestas animando al usuario a seguir aprendiendo
- Si te preguntan algo fuera de tu tema, redirige amablemente 
  hacia el mundo de la IA y la tecnología

Responde siempre en español.
"""

# ============================================================
# RUTAS
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message", "")
        conversation_history = data.get("history", [])

        # Llamada a la IA de Groq
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
        # Si hay cualquier error, lo muestra en la terminal Y en el chat
        print("ERROR DETECTADO:", str(e))
        return jsonify({"reply": f"Error: {str(e)}"})

# ============================================================
# ARRANCAR EL SERVIDOR
# ============================================================

if __name__ == "__main__":
 import webbrowser
import threading

def abrir_navegador():
    webbrowser.open("http://127.0.0.1:5000")
    # Abre el navegador automáticamente

if __name__ == "__main__":
    threading.Timer(1.5, abrir_navegador).start()
    # Espera 1.5 segundos para que Flask arranque primero
    # y luego abre el navegador
    app.run(debug=False, host="0.0.0.0")
    # debug=False para el ejecutable final