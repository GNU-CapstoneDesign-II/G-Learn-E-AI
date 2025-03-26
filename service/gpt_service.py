# app/gpt_service.py
import json
import os
import re
import tiktoken
import random

from dotenv import load_dotenv
from openai import OpenAI
from service.GptRequestDTO import GPTRequestDTO

load_dotenv()  # .env 파일 불러오기
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
gpt_model = os.getenv("GPT_MODEL")
gpt_problem_model = os.getenv("GPT_PROBLEM_MODEL")
tokenizer = tiktoken.encoding_for_model(gpt_model)

def ask_gpt(prompt: str) -> str:
    response = client.chat.completions.create(
        model=gpt_model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()



def fix_json_commas(json_string: str) -> str:
    # ,} 또는 ,] 같은 문법 오류 제거
    return re.sub(r',\s*([\]}])', r'\1', json_string)


def summary_prompt(content: str) -> str:
    print(GPTRequestDTO.summary_user_template.format(user_input=content))
    response = client.chat.completions.create(
        model=gpt_model,
        messages=[
            {
                "role": "system",
                "content": GPTRequestDTO.summary_system_template
            },
            {
                "role": "user",
                "content": GPTRequestDTO.summary_user_template.format(user_input=content)
            }
        ]
    )
    return response.choices[0].message.content.strip()


def build_followup_prompt(existing_questions: list[str], missing_counts: dict, difficulty: str, question_types: dict, summary: str) -> list[dict]:
    system_prompt = GPTRequestDTO.follow_up_system_template.format(
        difficulty=difficulty,
        mc_count=missing_counts["multiple_choice"],
        multiple_choice_num_options=question_types["multiple_choice"]["num_options"],
        ox_count=missing_counts["ox"],
        fib_count=missing_counts["fill_in_the_blank"],
        desc_count=missing_counts["descriptive"]
    )

    user_prompt = GPTRequestDTO.follow_up_user_template.format(
        summary=summary,
        existing_question_list="\n".join(existing_questions)
    )

    print(f"system_prompt: {system_prompt}")
    print(f"user_prompt: {user_prompt}")

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

def extract_question_texts(parsed_result: dict) -> list[str]:
    question_list = []
    for q_type in ["multiple_choice", "ox", "fill_in_the_blank", "descriptive"]:
        if q_type in parsed_result:
            for item in parsed_result[q_type]:
                question_list.append(item.get("question", "").strip())
    return question_list

def merge_problems(original: dict, additional: dict) -> dict:
    merged = {}
    for key in ["multiple_choice", "ox", "fill_in_the_blank", "descriptive"]:
        merged[key] = (original.get(key) or []) + (additional.get(key) or [])
    return merged



def trim_all_question_types(data: dict, question_types: dict) -> dict:
    """
    문제 유형별로 요청된 개수보다 많은 항목이 있을 경우, 랜덤으로 초과된 문제들을 제거합니다.
    - data: GPT로부터 생성된 문제들 (JSON)
    - question_types: {"multiple_choice": {...}, "ox": {...}, ...} 와 같은 요청 정보
    """
    trimmed = {}

    for q_type in ["multiple_choice", "ox", "fill_in_the_blank", "descriptive"]:
        if q_type not in data:
            trimmed[q_type] = []
            continue

        questions = data[q_type]
        requested_count = question_types[q_type]["num_questions"]

        if len(questions) > requested_count:
            trimmed[q_type] = random.sample(questions, requested_count)
        else:
            trimmed[q_type] = questions

    return trimmed


def make_problem(content: str, difficulty: str, question_types: dict) -> dict | str:
    # question_types 내부 구조를 미리 변수로 꺼냄
    mc = question_types["multiple_choice"]
    ox = question_types["ox"]
    fib = question_types["fill_in_the_blank"]
    desc = question_types["descriptive"]

    if not mc["enabled"]:
        mc["num_questions"] = 0
    if not ox["enabled"]:
        ox["num_questions"] = 0
    if not fib["enabled"]:
        fib["num_questions"] = 0
    if not desc["enabled"]:
        desc["num_questions"] = 0

    if mc["num_questions"] + ox["num_questions"] + fib["num_questions"] + desc["num_questions"] > 30:
        return "Total number of questions exceeds 20"


    request_token_sum = 0
    response_token_sum = 0

    request_token_sum += len(tokenizer.encode(GPTRequestDTO.summary_system_template))
    request_token_sum += len(tokenizer.encode(GPTRequestDTO.summary_user_template.format(user_input=content)))

    content = summary_prompt(content)
    response_token_sum += len(tokenizer.encode(content))


    system_template = GPTRequestDTO.system_template_kr.format(
        difficulty=difficulty,
        multiple_choice_enabled=mc["enabled"],
        multiple_choice_num_questions=mc["num_questions"],
        multiple_choice_num_options=mc["num_options"],
        ox_enabled=ox["enabled"],
        ox_num_questions=ox["num_questions"],
        fib_enabled=fib["enabled"],
        fib_num_questions=fib["num_questions"],
        descriptive_enabled=desc["enabled"],
        descriptive_num_questions=desc["num_questions"]
    )
    # 템플릿에 값 대입
    prompt = GPTRequestDTO.content_template_kr.format(
        summary=content
    )

    print(f"system_template: {system_template}")
    print(f"prompt: {prompt}")

    print(f"Request Token length: {len(tokenizer.encode(prompt + system_template))}")
    request_token_sum += len(tokenizer.encode(prompt + system_template))

    if len(tokenizer.encode(prompt + system_template)) > 10000:
        return "Request token length exceeds 10000"
    expected_token_count = GPTRequestDTO.expected_token_count
    expected_tokens = expected_token_count["multiple_choice"] * mc["num_questions"] + \
                        expected_token_count["ox"] * ox["num_questions"] + \
                        expected_token_count["fill_in_the_blank"] * fib["num_questions"] + \
                        expected_token_count["descriptive"] * desc["num_questions"] + \
                        expected_token_count["base"]
    print(f"Expected Token length: {expected_tokens}")
    if expected_tokens > 5000:
        return "Expected token length exceeds 5000"

    response = client.chat.completions.create(
        model=gpt_model,
        messages=[
            {
                "role": "system",
                "content": system_template
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        # max_tokens=expected_tokens
    ).choices[0].message.content.strip()

    print(f"Response Token length: {len(tokenizer.encode(response))}")
    response_token_sum += len(tokenizer.encode(response))
    response = fix_json_commas(response)
    print(f"Response: {response}")

    # 정규표현식을 사용해 ```json ... ``` 형태의 코드 블록을 제거합니다.
    match = re.search(r"```json\s*(\{.*\})\s*```", response, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        json_str = response

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        # JSON 파싱 실패 시, 오류 메시지를 반환합니다.
        return "Json parsing error: " + str(e)

    parsed = trim_all_question_types(parsed, question_types)
    regenerate_limit = 3
    while regenerate_limit > 0:
        regenerate_limit -= 1

        missing_counts = {
            "multiple_choice": max(0, mc["num_questions"] - len(parsed.get("multiple_choice", []))),
            "ox": max(0, ox["num_questions"] - len(parsed.get("ox", []))),
            "fill_in_the_blank": max(0, fib["num_questions"] - len(parsed.get("fill_in_the_blank", []))),
            "descriptive": max(0, desc["num_questions"] - len(parsed.get("descriptive", [])))
        }

        if any(count > 0 for count in missing_counts.values()):
            question_texts = extract_question_texts(parsed)
            followup_messages = build_followup_prompt(question_texts, missing_counts, difficulty, question_types, content)
            request_token_sum += len(tokenizer.encode(followup_messages[0]["content"] + followup_messages[1]["content"]))
            followup_response = client.chat.completions.create(
                model=gpt_model,
                messages=followup_messages
            ).choices[0].message.content.strip()

            followup_response = fix_json_commas(followup_response)
            response_token_sum += len(tokenizer.encode(followup_response))
            match = re.search(r"```json\s*(\{.*\})\s*```", followup_response, re.DOTALL)
            json_followup = match.group(1) if match else followup_response
            print(f"json_followup: {json_followup}")
            try:
                parsed_followup = json.loads(json_followup)
                parsed = merge_problems(parsed, parsed_followup)
            except json.JSONDecodeError as e:
                return "Follow-up Json parsing error: " + str(e)
            parsed = trim_all_question_types(parsed, question_types)
    print("Request Token Sum: ", request_token_sum)
    print("Response Token Sum: ", response_token_sum)
    return parsed

