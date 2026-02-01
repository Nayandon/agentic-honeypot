from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import re
import requests
import random

# ✅ Swagger UI enabled, but "Try it out" DISABLED
app = FastAPI(
    swagger_ui_parameters={
        "tryItOutEnabled": False
    }
)

# ---------------- OPTIONAL API KEY ----------------
API_KEY = "GUVI_SECRET_KEY_123"

# ---------------- In-memory storage ----------------
sessions = {}

# ---------------- Models (GUVI FLEXIBLE) ----------------
class Message(BaseModel):
    sender: Optional[str] = ""
    text: str
    timestamp: Optional[str] = ""

    class Config:
        extra = "allow"


class RequestBody(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: Optional[List[Message]] = []
    metadata: Optional[dict] = {}

    class Config:
        extra = "allow"

# ---------------- Scam Detection (INTERNAL ONLY) ----------------
def is_scam(text: str) -> bool:
    keywords = ["blocked", "verify", "urgent", "upi", "click", "suspended"]
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

    for k in ["urgent", "verify", "blocked", "suspended"]:
        if k in text.lower():
            session["extracted"]["suspiciousKeywords"].append(k)

# ---------------- Human-like Agent Reply ----------------
def generate_agent_reply(text: str, session):
    text_lower = text.lower()
    messages = session["messages"]
    full_context = " ".join(messages).lower()

    fillers = ["umm", "uh", "hmm", "wait", "sorry", "okay"]
    filler = random.choice(fillers)

    if "upi" in text_lower:
        return f"{filler} I actually have two UPI IDs. Which one should I use?"

    if "http" in text_lower or "click" in text_lower:
        return f"{filler} this link isn’t opening properly on my phone. Is there another way?"

    if "blocked" in text_lower or "suspended" in text_lower:
        return "This is really sudden… my account was working fine today. Why is it blocked?"

    if "call" in text_lower or "number" in text_lower:
        return "I’m at work right now and can’t take calls. Can you explain it here?"

    if len(messages) == 1:
        return "I just got this message and I’m honestly confused… what exactly is the issue?"

    return random.choice([
        "Sorry, I’m still not fully getting this. Can you explain again?",
        "This is a bit confusing for me… what should I do first?",
        "I don’t usually handle these things. Can you guide me step by step?"
    ])

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
        "agentNotes": "Human-like confusion, clarification, and adaptive probing used"
    }

    try:
        requests.post(
            "https://hackathon.guvi.in/api/updateHoneyPotFinalResult",
            json=payload,
            timeout=5
        )
    except:
        pass

# ---------------- API ----------------
@app.get("/")
def home():
    return {"message": "Agentic HoneyPot API is running"}

@app.post("/v1/message")
def receive_message(
    body: RequestBody,
    x_api_key: Optional[str] = Header(None)
):
    # ✅ Optional API key (GUVI-safe)
    if x_api_key is not None and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

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
    reply = generate_agent_reply(text, sessions[session_id])

    if scam and len(sessions[session_id]["messages"]) >= 2 and not sessions[session_id]["callbackSent"]:
        send_final_callback(session_id)
        sessions[session_id]["callbackSent"] = True

    if not scam:
        return {
            "status": "ok",
            "scamDetected": False
        }

    return {
        "status": "success",
        "scamDetected": True,
        "reply": reply
    }

@app.get("/debug/session/{session_id}")
def debug_session(session_id: str):
    return sessions.get(session_id, {})
