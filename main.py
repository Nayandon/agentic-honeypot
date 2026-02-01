from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import re
import requests

app = FastAPI()

# In-memory storage
sessions = {}

# ---------------- Models ----------------
class Message(BaseModel):
    sender: str
    text: str
    timestamp: str

class RequestBody(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: List[Message] = []
    metadata: Optional[dict] = {}

# ---------------- Scam Detection ----------------
def is_scam(text: str) -> bool:
    keywords = ["blocked", "verify", "urgent", "upi", "click"]
    return any(k in text.lower() for k in keywords)

# ---------------- Intelligence Extraction ----------------
def extract_intelligence(text: str, session):
    session["extracted"]["phoneNumbers"].extend(
        re.findall(r'\+?\d{10,13}', text)
    )
    session["extracted"]["upiIds"].extend(
        re.findall(r'\b[\w.\-]{2,}@\w+\b', text)
    )
    session["extracted"]["phishingLinks"].extend(
        re.findall(r'https?://\S+', text)
    )

    for k in ["urgent", "verify", "blocked"]:
        if k in text.lower():
            session["extracted"]["suspiciousKeywords"].append(k)

# ---------------- Final Callback ----------------
def send_final_callback(session_id: str):
    session = sessions.get(session_id)
    if not session:
        return

    payload = {
        "sessionId": session_id,
        "scamDetected": True,
        "totalMessagesExchanged": len(session["messages"]),
        "extractedIntelligence": session["extracted"],
        "agentNotes": "Scammer used urgency and payment redirection tactics"
    }

    print("Sending final callback to GUVI")
    print(payload)

    try:
        response = requests.post(
            "https://hackathon.guvi.in/api/updateHoneyPotFinalResult",
            json=payload,
            timeout=5
        )
        print("Final callback sent:", response.status_code)
    except Exception as e:
        print("Callback failed:", e)

# ---------------- API ----------------
@app.get("/")
def home():
    return {"message": "Agentic HoneyPot API is running"}

@app.post("/v1/message")
def receive_message(body: RequestBody):
    session_id = body.sessionId
    text = body.message.text

    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [],
            "extracted": {
                "bankAccounts": [],
                "upiIds": [],
                "phishingLinks": [],
                "phoneNumbers": [],
                "suspiciousKeywords": []
            },
            "callbackSent": False
        }

    sessions[session_id]["messages"].append(text)
    extract_intelligence(text, sessions[session_id])

    scam = is_scam(text)

    if scam and len(sessions[session_id]["messages"]) >= 2 and not sessions[session_id]["callbackSent"]:
        send_final_callback(session_id)
        sessions[session_id]["callbackSent"] = True

    if not scam:
        return {"status": "ok", "scamDetected": False}

    return {
        "status": "success",
        "scamDetected": True,
        "reply": "Can you explain this again? I’m not sure I understand."
    }

@app.get("/debug/session/{session_id}")
def debug_session(session_id: str):
    return sessions.get(session_id, {})
