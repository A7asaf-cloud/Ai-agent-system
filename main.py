from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import anthropic
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

LOGISTICS_AGENT_PROMPT = """אתה סוכן AI מומחה בלוגיסטיקה ותפעול.
תפקידך לעזור בנושאים הבאים:
- מעקב משלוחים והזמנות
- ניהול מלאי
- תיאום ספקים ולקוחות
- פתרון בעיות תפעוליות
תמיד תענה בעברית, בצורה ברורה ותכליתית."""

ORCHESTRATOR_PROMPT = """אתה המוח המרכזי של מערכת AI.
נתח הודעות והחזר JSON בלבד:
{"agent": "logistics" או "general", "reason": "סיבה"}"""

conversation_history = {}

def route_to_agent(message):
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{"role": "user", "content": f"הודעה: {message}"}],
            system=ORCHESTRATOR_PROMPT
        )
        import json
        result = json.loads(response.content[0].text)
        return result.get("agent", "general")
    except:
        return "general"

def logistics_agent(message, history):
    messages = history + [{"role": "user", "content": message}]
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=LOGISTICS_AGENT_PROMPT,
        messages=messages
    )
    return response.content[0].text

def general_agent(message, history):
    messages = history + [{"role": "user", "content": message}]
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system="אתה עוזר AI לעסק. תמיד ענה בעברית.",
        messages=messages
    )
    return response.content[0].text

def process_message(sender, message):
    if sender not in conversation_history:
        conversation_history[sender] = []
    history = conversation_history[sender][-10:]
    agent = route_to_agent(message)
    if agent == "logistics":
        reply = logistics_agent(message, history)
    else:
        reply = general_agent(message, history)
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
