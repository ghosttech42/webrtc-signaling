from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Basit memory signaling (test için yeterli)
store = {}
offer_data = None
answer_data = None

class SDP(BaseModel):
    sdp: str
    type: str

@app.post("/offer")
def set_offer(offer: SDP):
    global offer_data
    offer_data = data
    return {"status": "offer saved"}
ice_candidates = []

@app.post("/ice")
def post_ice(candidate: dict):
    ice_candidates.append(candidate)
    return {"status": "ice saved"}

@app.get("/ice")
def get_ice():
    global ice_candidates
    data = ice_candidates
    ice_candidates = []
    return data

@app.get("/offer")
def get_offer():
    global offer_data
    data = offer_data
    offer_data = None  # 🔥 KRİTİK
    return data

@app.post("/answer")
def set_answer(answer: SDP):
    store["answer"] = answer
    return {"status": "answer saved"}

@app.get("/answer")
def get_answer():
    return store.get("answer")
