# app/main.py
from fastapi import FastAPI
from pydantic import BaseModel
from service.gpt_service import ask_gpt

app = FastAPI()


# DTO
class PromptRequest(BaseModel):
    prompt: str


@app.post("/ask")
def ask_endpoint(req: PromptRequest):
    result = ask_gpt(req.prompt)
    return {"answer": result}
