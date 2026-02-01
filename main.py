from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict
import time
import re

app = FastAPI(title="Safe Scam Detection API")

# ---------------- SECURITY CONFIG ----------------
API_KEY = "GUVI_SECRET_KEY_123"   # change this before deployment
RATE_LIMIT = 10                  # requests
RATE_WINDOW = 60                 # seconds

request_log: Dict[str, list] = {}

# ---------------- MODELS ----------------
class DetectRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=1000)

class DetectResponse(BaseModel):
    isScam: bool
    riskLevel: str
    reasons: list[str]

# ---------------- UTILS ----------------
def check_rate_limit(client_ip: str):
    now = time.time()
    history = request_log.get(client_ip, [])

    history = [t for t in history if now - t < RATE_WINDOW]

    if len(history) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down."
        )

    history.append(now)
    request_log[client_ip] = history

def analyze_text(text: str):
    reasons = []
    text_lower = text.lower()

    keywords = [
        "blocked", "verify", "urgent", "upi", "click",
        "refund", "prize", "lottery", "suspended"
    ]

    for word in keywords:
        if word in text_lower:
            reasons.append(f"Suspicious keyword: {word}")

    if re.search(r'https?://\S+', text):
        reasons.append("Suspicious link detected")

    if re.search(r'\+?\d{10,13}', text):
        reasons.append("Phone number detected")

    if re.search(r'\b[\w.\-]{2,}@\w+\b', text):
        reasons.append("UPI ID detected")

    is_scam = len(reasons) >= 2

    risk = "LOW"
    if len(reasons) >= 4:
        risk = "HIGH"
    elif len(reasons) >= 2:
        risk = "MEDIUM"

    return is_scam, risk, reasons

# ---------------- API ----------------
@app.post("/detect", response_model=DetectResponse)
def detect_scam(
    data: DetectRequest,
    request: Request,
    x_api_key: Optional[str] = Header(None)
):
    # API key check
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Rate limit check
    client_ip = request.client.host
    check_rate_limit(client_ip)

    is_scam, risk, reasons = analyze_text(data.text)

    return {
        "isScam": is_scam,
        "riskLevel": risk,
        "reasons": reasons
    }

@app.get("/")
def health():
    return {"status": "API running securely"}

