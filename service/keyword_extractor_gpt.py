# service/keyword_extractor_gpt.py
import json
import os
from typing import List, Dict, Any

import tiktoken
from dotenv import load_dotenv
from openai import OpenAI

from utils.GetTictoken import get_tokenizer_for_model

load_dotenv()

client              = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
gpt_problem_model   = os.getenv("GPT_PROBLEM_MODEL", "gpt-4o-mini")

gpt_request_cost    = float(os.getenv("GPT_REQUEST_COST", 0))
gpt_response_cost   = float(os.getenv("GPT_RESPONSE_COST", 0))
exchange_rate       = float(os.getenv("EXCHANGE_RATE", 1300))

tokenizer = get_tokenizer_for_model(gpt_problem_model)

# ─────────────────────────────────────────────────────────────
# Prompt 템플릿
# ─────────────────────────────────────────────────────────────
SYSTEM_TEMPLATE = """
당신은 한국어 문제지의 핵심 키워드를 추출해 주는 어시스턴트입니다.
답변은 반드시 JSON 배열만 반환하세요.
"""

USER_TEMPLATE = """
다음 JSON 배열은 문제 목록입니다. 각 문제 객체는 id·title·explanation·options·answers·type 필드를 가집니다.

요구 사항
- 문제별로 핵심 키워드 {top_n}개를 뽑아 주세요.
- 응답 포맷(예시):
[
  {{ "id": 9, "keywords": ["키워드1", "키워드2", ...] }},
  {{ "id": 10, "keywords": [...] }}
]
- JSON 외의 다른 텍스트는 절대 포함하지 마세요.

문제 목록:
{problems_json}
"""

# ─────────────────────────────────────────────────────────────
def extract_keywords_gpt(
        problems: List[Dict[str, Any]],
        top_n: int
) -> Dict[str, Any]:
    """
    GPT 호출로 문제별 키워드 추출
    :param problems: 문제 리스트
    :param top_n: 문제마다 추출할 키워드 수
    :return: {
        "keywords": List[ {id, keywords[]} ],
        "request_tokens": int,
        "response_tokens": int,
        "estimated_cost_krw": float
    }
    """
    problems_json = json.dumps(problems, ensure_ascii=False, indent=2)
    prompt_user   = USER_TEMPLATE.format(top_n=top_n, problems_json=problems_json)

    # ── 토큰 카운트 ──
    req_tokens = len(tokenizer.encode(prompt_user))

    response = client.chat.completions.create(
        model=gpt_problem_model,
        messages=[
            {"role": "system", "content": SYSTEM_TEMPLATE},
            {"role": "user",   "content": prompt_user}
        ],
        # temperature=0.0,
    )

    print(f"Response: {response}")

    content      = response.choices[0].message.content.strip()
    res_tokens   = len(tokenizer.encode(content))
    keywords_arr = json.loads(content)  # → List[ {id, keywords} ]

    # (선택) 비용 추정
    cost_usd = ((req_tokens / 1000) * gpt_request_cost +
                (res_tokens / 1000) * gpt_response_cost)
    cost_krw = round(cost_usd * exchange_rate, 2)

    return {
        "problems": keywords_arr,
        "requestTokens": req_tokens,
        "responseTokens": res_tokens,
        "estimatedCostKrw": cost_krw
    }
