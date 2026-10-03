from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()

app = Flask(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ALLOWED_EMOTIONS = {
    "Joy",
    "Sadness",
    "Anger",
    "Fear",
    "Disgust",
    "Anxiety",
    "Envy",
    "Embarrassment",
    "Ennui",
}

BASE_INSTRUCTIONS = (
    "You are MindMate, a supportive mental wellbeing assistant. "
    "Be empathetic, calm, and respectful. "
    "Do not diagnose mental health conditions or claim to be a therapist. "
    "Give general supportive guidance and encourage the user to speak "
    "with a qualified mental health professional when appropriate. "
    "If the user indicates immediate danger or intent to harm themselves "
    "or someone else, encourage them to contact local emergency services "
    "or a trusted person immediately. "
    "You help university students understand their feelings and try healthy coping steps. "
    "Every feeling has a purpose, including uncomfortable ones. Accepting a feeling "
    "works better than fighting it. A sense of self includes difficult experiences, "
    "not only good ones. If the user has checked in with a feeling, acknowledge it "
    "briefly in your own words. If that feeling is Anxiety, acknowledge that it is "
    "trying to protect them and gently bring them back to the present, because "
    "anxiety causes problems when it is the only feeling in charge. "
    "Do not mention films, studios, or copyrighted characters."
)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    emotion = data.get("emotion", "")
    if not isinstance(emotion, str):
        emotion = ""
    emotion = emotion.strip()
    if emotion not in ALLOWED_EMOTIONS:
        emotion = ""

    if not user_message:
        return jsonify({
            "reply": "Please tell me how you're feeling."
        })

    instructions = BASE_INSTRUCTIONS
    if emotion:
        instructions += f" The feeling they last checked in with is {emotion}."

    try:
        response = client.responses.create(
            model="gpt-5.6-luna",
            instructions=instructions,
            input=user_message
        )

        return jsonify({
   
     "reply": response.output_text
   
  })

    except Exception as e:
        print("OpenAI Error:", e)

        return jsonify({
            "reply": "Sorry, I couldn't connect to MindMate AI right now. Please try again."
        })


if __name__ == "__main__":
    app.run(debug=True)
    
    
