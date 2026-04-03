from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from groq import Groq
import os
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"


LOGISTICS_PROMPT = """אתה סוכן AI מומחה בלוגיסטיקה ותפעול.
תפקידך לעזור בנושאים הבאים:
- מעקב משלוחים והזמנות
- ניהול מלאי
- תיאום ספקים ולקוחות
- פתרון בעיות תפעוליות
תמיד תענה בעברית, בצורה ברורה ותכליתית."""

ORCHESTRATOR_PROMPT = """אתה מנתב הודעות. החזר JSON בלבד:
{"agent": "logistics" או "general", "reason": "סיבה"}"""

conversation_history = {}

def route_to_agent(message):
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": ORCHESTRATOR_PROMPT},
                {"role": "user", "content": f"הודעה: {message}"}
            ],
            max_tokens=100
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("agent", "general")
    except:
        return "general"

def run_agent(message, history, system_prompt):
    messages = [{"role": "system", "content": system_prompt}]
    messages += history[-10:]
    messages.append({"role": "user", "content": message})
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=500
    )
    return response.choices[0].message.content

def process_message(sender, message):
    if sender not in conversation_history:
        conversation_history[sender] = []
    history = conversation_history[sender]
    agent = route_to_agent(message)
    logger.info(f"ניתוב ל: {agent} | שולח: {sender}")
    if agent == "logistics":
        reply = run_agent(message, history, LOGISTICS_PROMPT)
    else:
        reply = run_agent(message, history, "אתה עוזר AI לעסק. תמיד ענה בעברית.")
    conversation_history[sender].append({"role": "user", "content": message})
    conversation_history[sender].append({"role": "assistant", "content": reply})
    return reply

@app.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")
    if not incoming_msg:
        return Response(str(MessagingResponse()), mimetype="text/xml")
    reply_text = process_message(sender, incoming_msg)
    resp = MessagingResponse()
    resp.message(reply_text)
    return Response(str(resp), mimetype="text/xml")

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
