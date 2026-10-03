from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()

app = Flask(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({
            "reply": "Please tell me how you're feeling."
        })

    try:
        response = client.responses.create(
            model="gpt-5.6-luna",
            instructions=(
     "You are MindMate, a supportive mental wellbeing assistant. "
     "Be empathetic, calm, and respectful. "
      "Do not diagnose mental health conditions or claim to be a therapist. "
      "Give general supportive guidance and encourage the user to speak "
      "with a qualified mental health professional when appropriate. "
       "If the user indicates immediate danger or intent to harm themselves "
       "or someone else, encourage them to contact local emergency services "
       "or a trusted person immediately."
      ),
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
    
    
