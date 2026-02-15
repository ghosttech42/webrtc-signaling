from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Basit memory signaling (test için yeterli)
store = {}

class SDP(BaseModel):
    sdp: str
    type: str

@app.post("/offer")
def set_offer(offer: SDP):
    store["offer"] = offer
    return {"status": "offer saved"}

@app.get("/offer")
def get_offer():
    return store.get("offer")

@app.post("/answer")
def set_answer(answer: SDP):
    store["answer"] = answer
    return {"status": "answer saved"}

@app.get("/answer")
def get_answer():
    return store.get("answer")
