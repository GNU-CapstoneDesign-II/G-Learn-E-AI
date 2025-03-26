# app/gpt_service.py
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # .env 파일 불러오기
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
gpt_model = os.getenv("GPT_MODEL")

def ask_gpt(prompt: str) -> str:
    response = client.chat.completions.create(
        model=gpt_model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
