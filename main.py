from fastapi import FastAPI, Header, HTTPException, Request
from typing import Optional, Dict
import re
import random
import requests

app = FastAPI(
    swagger_ui_parameters={"tryItOutEnabled": False}
)

API_KEY = "GUVI_SECRET_KEY_123"
FINAL_CALLBACK_URL = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"

sessions: Dict[str, dict] = {}

# ======================================================
# UTILITIES
# ======================================================
def is_scam(text: str) -> bool:
    keywords = ["blocked", "verify", "urgent", "upi", "click", "suspended"]
    return any(k in text.lower() for k in keywords)

def extract_intelligence(text: str, session: dict):
    session["extracted"]["phoneNumbers"] += re.findall(r'\+?\d{10,13}', text)
    session["extracted"]["upiIds"] += re.findall(r'\b[\w.\-]{2,}@\w+\b', text)
    session["extracted"]["phishingLinks"] += re.findall(r'https?://\S+', text)

def generate_agent_reply(text: str) -> str:
    fillers = ["umm", "uh", "hmm", "okay", "sorry"]
    filler = random.choice(fillers)

    if "upi" in text.lower():
        return f"{filler} I have two UPI IDs actually. Which one should I use?"
    if "click" in text.lower() or "http" in text.lower():
        return f"{filler} the link isn’t opening properly."
    if "blocked" in text.lower():
        return "This is confusing… my account was working fine today."

    return "Sorry, I’m not fully understanding this. Can you explain again?"

def send_final_callback(session_id: str):
    session = sessions.get(session_id)
    if not session:
        return

    payload = {
        "sessionId": session_id,
        "scamDetected": True,
        "totalMessagesExchanged": len(session["messages"]),
        "extractedIntelligence": session["extracted"]
    }

    try:
        requests.post(FINAL_CALLBACK_URL, json=payload, timeout=5)
    except:
        pass

# ======================================================
# ROUTES
# ======================================================
@app.get("/")
def health():
    return {"status": "running"}

# ------------------------------------------------------
# ✅ GUVI TESTER — 422 IMPOSSIBLE
# ------------------------------------------------------
@app.post("/webhook")
async def guvi_webhook(
    request: Request,
    x_api_key: Optional[str] = Header(None)
):
    if x_api_key and x_api_key != API_KEY:
        return {"status": "error", "reason": "Invalid API key"}

    try:
        body = await request.json()
    except:
        body = {}

    # extract message safely from ANY structure
    text = (
        body.get("message")
        or body.get("text")
        or body.get("data")
        or "unknown"
    )

    return {
        "status": "success",
        "received": text
    }

# ------------------------------------------------------
# HACKATHON / SCAMMER API ENDPOINT
# ------------------------------------------------------
@app.post("/v1/message")
async def receive_message(request: Request):
    body = await request.json()

    session_id = body.get("sessionId", "default-session")
    text = (
        body.get("message", {}).get("text")
        or body.get("text")
        or ""
    )

    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [],
            "extracted": {
                "phoneNumbers": [],
                "upiIds": [],
                "phishingLinks": []
            },
            "callbackSent": False
        }

    session = sessions[session_id]
    session["messages"].append(text)

    extract_intelligence(text, session)

    if is_scam(text):
        if len(session["messages"]) >= 2 and not session["callbackSent"]:
            send_final_callback(session_id)
            session["callbackSent"] = True

        return {
            "status": "success",
            "scamDetected": True,
            "reply": generate_agent_reply(text)
        }

    return {
        "status": "ok",
        "scamDetected": False
    }

# ------------------------------------------------------
# DEBUG
# ------------------------------------------------------
@app.get("/debug/session/{session_id}")
def debug(session_id: str):
    return sessions.get(session_id, {})
