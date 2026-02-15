from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

store = {
    "offer": None,
    "answer": None,
    "ice": []
}

class SDP(BaseModel):
    sdp: str
    type: str

@app.post("/offer")
def set_offer(offer: dict):
    global current_offer
    current_offer = offer

@app.get("/offer")
def get_offer():
    global current_offer
    offer = current_offer
    current_offer = None   # 🔥 KRİTİK SATIR
    return offer

@app.post("/answer")
def set_answer(answer: SDP):
    store["answer"] = answer.dict()
    return {"status": "answer saved"}

@app.get("/answer")
def get_answer():
    return store["answer"]

@app.post("/ice")
def add_ice(candidate: dict):
    store["ice"].append(candidate)
    return {"status": "ice added"}

@app.get("/ice")
def get_ice():
    ice = store["ice"]
    store["ice"] = []
    return ice
