# app/gpt_service.py
import json
import os
import re
import tiktoken
import random

from dotenv import load_dotenv
from openai import OpenAI
from dto.GptRequestDTO import GPTRequestDTO
from dto.CommonDTO import GradeItem, GradeResult, BlankItem, BlankResult, QuestionTypes
from typing import List, Dict, Any

from utils.GetTictoken import get_tokenizer_for_model

load_dotenv()  # .env 파일 불러오기
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
gpt_model = os.getenv("GPT_MODEL", "gpt-4o-mini")
gpt_problem_model = os.getenv("GPT_PROBLEM_MODEL")

gpt_request_cost = float(os.getenv("GPT_REQUEST_COST"))
gpt_response_cost = float(os.getenv("GPT_RESPONSE_COST"))
exchange_rate = float(os.getenv("EXCHANGE_RATE"))

tokenizer = get_tokenizer_for_model(gpt_model)

def ask_gpt(prompt: str) -> str:
    response = client.chat.completions.create(
        model=gpt_model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def fix_json_commas(json_string: str) -> str:
    # ,} 또는 ,] 같은 문법 오류 제거
    return re.sub(r',\s*([\]}])', r'\1', json_string)


def remove_json_block(json_string: str) -> str:
    # ```json ... ``` 형태의 코드 블록을 제거합니다.
    return re.sub(r"```json\s*(.*?)\s*```", r"\1", json_string, flags=re.DOTALL)


def replace_underscores(text):
    """
    문자열 내에서 연속된 밑줄(_)을 [[BLANK]]로 치환합니다.

    Args:
        text (str): 원본 문자열

    Returns:
        str: 변환된 문자열
    """
    # 한 개 이상의 밑줄을 찾아서 [[BLANK]]로 대체
    return re.sub(r'_+', '[[BLANK]]', text)


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


def build_followup_prompt(existing_questions: list[str], missing_counts: dict, difficulty: str,
                          question_types: QuestionTypes,
                          summary: str) -> list[dict]:
    system_prompt = GPTRequestDTO.follow_up_system_template.format(
        difficulty=difficulty,
        mc_count=missing_counts["multipleChoice"],
        multiple_choice_num_options=question_types.multipleChoice.numOptions,
        ox_count=missing_counts["ox"],
        fib_count=missing_counts["fillInTheBlank"],
        desc_count=missing_counts["descriptive"]
    )

    user_prompt = GPTRequestDTO.follow_up_user_template.format(
        summary=summary,
        existing_question_list="\n".join(existing_questions)
    )

    # print(f"system_prompt: {system_prompt}")
    # print(f"user_prompt: {user_prompt}")

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


def extract_question_texts(parsed_result: dict) -> list[str]:
    question_list = []
    for q_type in ["multipleChoice", "ox", "fillInTheBlank", "descriptive"]:
        if q_type in parsed_result:
            for item in parsed_result[q_type]:
                question_list.append(item.get("question", "").strip())
    return question_list


def merge_problems(original: dict, additional: dict) -> dict:
    merged = {}
    for key in ["multipleChoice", "ox", "fillInTheBlank", "descriptive"]:
        merged[key] = (original.get(key) or []) + (additional.get(key) or [])
    return merged


def trim_all_question_types(data: dict, question_types: QuestionTypes) -> dict:
    """
    문제 유형별로 요청된 개수보다 많은 항목이 있을 경우, 랜덤으로 초과된 문제들을 제거합니다.
    - data: GPT로부터 생성된 문제들 (JSON)
    - question_types: {"multiple_choice": {...}, "ox": {...}, ...} 와 같은 요청 정보
    """
    trimmed = {}

    for q_type in ["multipleChoice", "ox", "fillInTheBlank", "descriptive"]:
        if q_type not in data:
            trimmed[q_type] = []
            continue

        questions = data[q_type]

        if q_type == "multipleChoice":
            requested_count = question_types.multipleChoice.numQuestions
        elif q_type == "ox":
            requested_count = question_types.ox.numQuestions
        elif q_type == "fillInTheBlank":
            requested_count = question_types.fillInTheBlank.numQuestions
        elif q_type == "descriptive":
            requested_count = question_types.descriptive.numQuestions
        else:
            requested_count = 0

        if len(questions) > requested_count:
            trimmed[q_type] = random.sample(questions, requested_count)
        else:
            trimmed[q_type] = questions

    return trimmed


def make_problem(content: str, difficulty: str, question_types: QuestionTypes) -> dict:
    # question_types 내부 구조를 미리 변수로 꺼냄
    mc = question_types.multipleChoice
    ox = question_types.ox
    fib = question_types.fillInTheBlank
    desc = question_types.descriptive

    if not mc.enable:
        mc.numQuestions = 0
    if not ox.enable:
        ox.numQuestions = 0
    if not fib.enable:
        fib.numQuestions = 0
    if not desc.enable:
        desc.numQuestions = 0

    if mc.numQuestions + ox.numQuestions + fib.numQuestions + desc.numQuestions > 30:
        return "Total number of questions exceeds 20"

    request_token_sum = 0
    response_token_sum = 0

    if len(tokenizer.encode(content)) > 8000:
        # 요청 토큰 길이가 8000을 초과하면 내용을 요약합니다.
        request_token_sum += len(tokenizer.encode(GPTRequestDTO.summary_system_template))
        request_token_sum += len(tokenizer.encode(GPTRequestDTO.summary_user_template.format(user_input=content)))
        content = summary_prompt(content)
        response_token_sum += len(tokenizer.encode(content))

    system_template = GPTRequestDTO.system_template_kr.format(
        difficulty=difficulty,
        multipleChoiceEnabled=mc.enable,
        multipleChoiceNumQuestions=mc.numQuestions,
        multipleChoiceNumOptions=mc.numOptions,
        oxEnabled=ox.enable,
        oxNumQuestions=ox.numQuestions,
        fibEnabled=fib.enable,
        fibNumQuestions=fib.numQuestions,
        descriptiveEnabled=desc.enable,
        descriptiveNumQuestions=desc.numQuestions
    )
    # 템플릿에 값 대입
    prompt = GPTRequestDTO.content_template_kr.format(
        summary=content
    )

    # print(f"Request Token length: {len(tokenizer.encode(prompt + system_template))}")
    request_token_sum += len(tokenizer.encode(prompt + system_template))

    if len(tokenizer.encode(prompt + system_template)) > 10000:
        return {"result": "Request token length exceeds 10000",
                "request_tokens": request_token_sum,
                "response_tokens": response_token_sum}

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

    # 응답 토큰 길이 추가
    response_token_sum += len(tokenizer.encode(response))

    # JSON 블록을 제거합니다.
    json_str = fix_json_commas(remove_json_block(response))
    # print(f"Response: {json_str}")

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        # JSON 파싱 실패 시, 오류 메시지를 반환합니다.
        return {"result": "Json parsing error: " + str(e),
                "request_tokens": request_token_sum,
                "response_tokens": response_token_sum}

    parsed = trim_all_question_types(parsed, question_types)
    regenerate_limit = 3
    while regenerate_limit > 0:
        regenerate_limit -= 1

        missing_counts = {
            "multipleChoice": max(0, mc.numQuestions - len(parsed.get("multipleChoice", []))),
            "ox": max(0, ox.numQuestions - len(parsed.get("ox", []))),
            "fillInTheBlank": max(0, fib.numQuestions - len(parsed.get("fillInTheBlank", []))),
            "descriptive": max(0, desc.numQuestions - len(parsed.get("descriptive", [])))
        }
        print(f"Missing_counts: {missing_counts}")
        if any(count > 0 for count in missing_counts.values()):
            question_texts = extract_question_texts(parsed)
            followup_messages = build_followup_prompt(question_texts, missing_counts, difficulty, question_types,
                                                      content)
            request_token_sum += len(
                tokenizer.encode(followup_messages[0]["content"] + followup_messages[1]["content"]))
            followup_response = client.chat.completions.create(
                model=gpt_model,
                messages=followup_messages
            ).choices[0].message.content.strip()
            # 응답 토큰 길이 추가
            response_token_sum += len(tokenizer.encode(followup_response))

            json_followup = fix_json_commas(remove_json_block(followup_response))

            print(f"json_followup: {json_followup}")
            try:
                parsed_followup = json.loads(json_followup)
                parsed = merge_problems(parsed, parsed_followup)
            except json.JSONDecodeError as e:
                return {"result": "Follow-up Json parsing error: " + str(e),
                        "request_tokens": request_token_sum,
                        "response_tokens": response_token_sum}
            parsed = trim_all_question_types(parsed, question_types)
        else:
            break

    if "fillInTheBlank" in parsed:
        for item in parsed["fillInTheBlank"]:
            item["question"] = replace_underscores(item["question"])

    return {
        "result": parsed,
        "request_tokens": request_token_sum,
        "response_tokens": response_token_sum,
    }


def gpt_role_eval(
        role_name: str,
        role_desc: str,
        user_prompt: str,
        tokenizer,
        request_token_sum: int,
        response_token_sum: int
) -> tuple[list[dict], int, int]:
    """
    단일 역할에 대해 GPT API를 호출하고, 결과(JSON)를 반환.
    호출에 사용된 토큰 수(request_token_sum, response_token_sum)를 갱신해 반환한다.
    """
    # 시스템 프롬프트 생성
    system_prompt = GPTRequestDTO.grade_system_template.format(name=role_name, role=role_desc)

    # GPT 요청
    response = client.chat.completions.create(
        model=gpt_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0,
    ).choices[0].message.content.strip()

    # 토큰 계산
    request_token_sum += len(tokenizer.encode(system_prompt))
    request_token_sum += len(tokenizer.encode(user_prompt))
    response_token_sum += len(tokenizer.encode(response))

    print(f"[{role_name}] Response:", response)

    # JSON 파싱
    answer_text = fix_json_commas(response)
    confidences = json.loads(answer_text)
    return confidences, request_token_sum, response_token_sum


def run_role_evaluations(
        prompt: str,
        roles: list[dict],
        tokenizer,
        request_token_sum: int,
        response_token_sum: int
) -> tuple[list[list[dict]], int, int]:
    """
    여러 역할에 대해 GPT 호출을 반복 실행.
    각 호출 결과(리스트 형태 JSON)를 묶어서 반환.
    """
    role_confidences = []
    for role in roles:
        try:
            result, request_token_sum, response_token_sum = gpt_role_eval(
                role_name=role["name"],
                role_desc=role["description"],
                user_prompt=prompt,
                tokenizer=tokenizer,
                request_token_sum=request_token_sum,
                response_token_sum=response_token_sum
            )
            role_confidences.append(result)
        except Exception as e:
            print(f"[{role['name']}] Error:", e)
            raise Exception(f"{role['name']} 평가 중 오류 발생: " + str(e))
    return role_confidences, request_token_sum, response_token_sum


def create_grade_prompt(items: List[GradeItem]) -> str:
    """
    입력된 GradeItem 리스트를 기반으로 채점 프롬프트 문자열을 생성합니다.
    각 항목은 문제 ID, 문제, 정답, 학생 답안을 포함합니다.
    """
    item_prompts = []
    for item in items:
        item_prompt = (
            f"문제 ID: {item.id}\n"
            f"문제: {item.question}\n"
            f"정답: {item.answer}\n"
            f"학생 답안: {item.input}"
        )
        item_prompts.append(item_prompt)
    all_items_text = "\n\n".join(item_prompts)
    return GPTRequestDTO.grade_user_template.format(items=all_items_text)


def grade_items(items: List[GradeItem]) -> dict[str, Any]:
    """
    서술형 답안을 여러 역할로 평가 후, 평균 확신도가 50 이상이면 정답(true)으로 판정.
    """
    prompt = create_grade_prompt(items)

    roles = [
        {
            "name": "전반적 평가자",
            "description": "전체적인 답안의 완성도, 정확성 및 정답과의 일치 정도를 평가하십시오. 답안이 정답에 부합한다고 판단되면 높은 확신(confidence)을, 그렇지 않으면 낮은 확신을 숫자로 반환하십시오."
        },
        {
            "name": "핵심 키워드 평가자",
            "description": "정답에 포함되어야 할 핵심 키워드나 유사 표현, (영어/한국어 등의)언어가 다른 유사 표현의 포함 여부를 평가하고, 포함되었다고 판단되면 높은 확신, 그렇지 않으면 낮은 확신을 숫자로 반환하십시오."
        },
        {
            "name": "논리성 평가자",
            "description": "답안의 논리적 전개, 일관성 및 근거의 명확성을 평가하고, 논리적으로 정답과 부합하면 높은 확신, 아니면 낮은 확신을 숫자로 반환하십시오."
        }
    ]

    request_token_sum = 0
    response_token_sum = 0

    # 중복 제거: run_role_evaluations 사용
    role_confidences, request_token_sum, response_token_sum = run_role_evaluations(
        prompt, roles, tokenizer, request_token_sum, response_token_sum
    )

    # 결과 집계
    combined_confidences = {}
    for confidences in role_confidences:
        for item in confidences:
            id_val = item.get("id")
            conf_val = item.get("score")
            if id_val is None or conf_val is None:
                raise Exception(f"잘못된 평가 결과 형식: {item}")
            combined_confidences.setdefault(id_val, []).append(conf_val)

    final_results = []
    for id_val, conf_list in combined_confidences.items():
        avg_conf = sum(conf_list) / len(conf_list)
        final_decision = avg_conf >= 50
        final_results.append(GradeResult(id=id_val, correct=final_decision))

    return {
        "result": final_results,
        "request_tokens": request_token_sum,
        "response_tokens": response_token_sum
    }


def create_blank_prompt(items: List[BlankItem]) -> str:
    """
    입력된 BlankItem 리스트를 기반으로 빈칸 채우기 문제 채점 프롬프트 문자열을 생성합니다.
    각 항목은 문제 ID, 문제, 정답(리스트), 학생 답안을 포함합니다.
    """
    item_prompts = []
    for item in items:
        # 정답 리스트를 쉼표로 구분하여 문자열로 변환
        answers_str = ", ".join(item.answer)
        input_str = ", ".join(item.input)
        item_prompt = (
            f"문제 ID: {item.id}\n"
            f"문제: {item.question}\n"
            f"정답: {answers_str}\n"
            f"학생 답안: {input_str}"
        )
        item_prompts.append(item_prompt)
    all_items_text = "\n\n".join(item_prompts)
    return GPTRequestDTO.blank_user_template.format(items=all_items_text)


def grade_blank_items(items: List[BlankItem], confidence_threshold: int = 50) -> dict[str, Any]:
    """
    빈칸 채우기 문제를 여러 역할로 평가 후, 평균이 threshold 이상이면 정답(true).
    """
    prompt = create_blank_prompt(items)

    roles = [
        {
            "name": "전반적 평가자",
            "description": "문제 전체의 맥락과 정답과의 일치 여부를 평가하십시오."
        },
        {
            "name": "핵심 단어 평가자",
            "description": "정답에 포함되어야 할 핵심 키워드나 유사 표현, (영어/한국어 등의)언어가 다른 유사 표현의 포함 여부를 평가하고, 포함되었다고 판단되면 높은 확신, 그렇지 않으면 낮은 확신을 숫자로 반환하십시오."
        },
        {
            "name": "논리성 평가자",
            "description": "학생의 답안이 문제의 의도와 논리적으로 부합하는지 평가하십시오"
        }
    ]

    request_token_sum = 0
    response_token_sum = 0

    # 마찬가지로 중복 제거
    role_confidences, request_token_sum, response_token_sum = run_role_evaluations(
        prompt, roles, tokenizer, request_token_sum, response_token_sum
    )

    # 결과 집계
    combined_confidences = {}
    for confidences in role_confidences:
        for item in confidences:
            id_val = item.get("id")
            conf_val = item.get("score")
            if id_val is None or conf_val is None:
                raise Exception(f"잘못된 평가 결과 형식: {item}")
            combined_confidences.setdefault(id_val, []).append(conf_val)

    final_results = []
    for id_val, conf_list in combined_confidences.items():
        avg_conf = sum(conf_list) / len(conf_list)
        final_decision = avg_conf >= confidence_threshold
        final_results.append(BlankResult(id=id_val, correct=final_decision))

    return {
        "result": final_results,
        "request_tokens": request_token_sum,
        "response_tokens": response_token_sum
    }
