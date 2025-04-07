# content_preprocessor_gpt.py
import os
import tiktoken

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # .env 파일 불러오기
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
gpt_model = os.getenv("GPT_MODEL")
gpt_problem_model = os.getenv("GPT_PROBLEM_MODEL")

gpt_request_cost = float(os.getenv("GPT_REQUEST_COST"))
gpt_response_cost = float(os.getenv("GPT_RESPONSE_COST"))
exchange_rate = float(os.getenv("EXCHANGE_RATE"))

tokenizer = tiktoken.encoding_for_model(gpt_model)

pdf_text_processing_system_template = """
당신은 전문 텍스트 정제 및 편집 어시스턴트입니다.
PDF 파일에서 추출된 텍스트를 다룰 때 발생하는 글자 깨짐, 부자연스러운 문장 구조, 잘못된 줄바꿈, 불필요한 공백, 오타 등을 자동으로 감지하고, 원래 의미를 최대한 유지하면서 자연스럽고 명확한 문장으로 재구성하는 역할을 맡고 있습니다.
추출된 텍스트가 원본의 의미를 보존하면서도 읽기 쉽도록 개선되도록 주의 깊게 편집해주세요.

결과물의 길이는 4000토큰 이하로 유지해야 하며, 문장 구조와 의미를 최대한 자연스럽게 유지해야 합니다.
출력은 문자열 형태로 출력하고, 불필요한 안내문은 출력하지 마세요.
"""
# 이 때 구조적으로 정돈된 형태로 pdf 파일의 핵심 내용들을 요약해주세요 -> 써야될지 말아야될지... 비용 생각하면 쓰는게 맞음

pdf_text_processing_user_template = """
아래는 PDF 파일에서 변환된 텍스트입니다. 변환 과정에서 텍스트가 깨지거나 문장이 부자연스러운 부분들이 있습니다. 원래의 의미를 최대한 유지하면서, 문장을 자연스럽고 명확하게 다듬어 주세요.

{text}
"""


def pdf_text_processing(text: str) -> dict:
    """
    PDF에서 추출한 텍스트를 전처리하는 함수입니다.
    - 불필요한 공백 제거
    - 줄바꿈 문자 제거
    """
    request_token_sum = 0
    response_token_sum = 0

    request_token_sum += len(tokenizer.encode(text))

    response = client.chat.completions.create(
        model=gpt_model,
        messages=[
            {
                "role": "system",
                "content": pdf_text_processing_system_template
            },
            {
                "role": "user",
                "content": pdf_text_processing_user_template.format(text=text)
            }
        ]
    )
    response = response.choices[0].message.content.strip()
    response_token_sum += len(tokenizer.encode(response))

    return {
        "result": response,
        "request_tokens": request_token_sum,
        "response_tokens": response_token_sum,
    }
