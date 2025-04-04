# app/gpt_service.py
import json
import os
import re
import tiktoken
import random

from dotenv import load_dotenv
from openai import OpenAI
from dto.GptRequestDTO import GPTRequestDTO
from dto.CommonDTO import GradeItem, GradeResult, BlankItem, BlankResult
from typing import List

load_dotenv()  # .env 파일 불러오기
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
gpt_model = os.getenv("GPT_MODEL")
gpt_problem_model = os.getenv("GPT_PROBLEM_MODEL")

gpt_request_cost = float(os.getenv("GPT_REQUEST_COST"))
gpt_response_cost = float(os.getenv("GPT_RESPONSE_COST"))
exchange_rate = float(os.getenv("EXCHANGE_RATE"))

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


def build_followup_prompt(existing_questions: list[str], missing_counts: dict, difficulty: str, question_types: dict,
                          summary: str) -> list[dict]:
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

    print(f"content token length: {len(tokenizer.encode(content))}")
    if len(tokenizer.encode(content)) > 5000:
        # 요청 토큰 길이가 5000을 초과하면 내용을 요약합니다.
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
            followup_messages = build_followup_prompt(question_texts, missing_counts, difficulty, question_types,
                                                      content)
            request_token_sum += len(
                tokenizer.encode(followup_messages[0]["content"] + followup_messages[1]["content"]))
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
    print(f"Request Token Sum: {request_token_sum},"
          f" cost: {request_token_sum / 1000.0 * gpt_request_cost * exchange_rate:.6f}원 ({request_token_sum / 1000.0 * gpt_request_cost:.6f}$)")
    print(f"Response Token Sum: {response_token_sum},"
          f" cost: {response_token_sum / 1000.0 * gpt_response_cost * exchange_rate:.6f}원 ({response_token_sum / 1000.0 * gpt_response_cost:.6f}$)")
    return parsed


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


def grade_items(items: List[GradeItem]) -> List[GradeResult]:
    """
    GPT API를 호출하여 각 GradeItem에 대해 여러 역할로 평가를 수행합니다.
    각 역할은 답안의 맞고 틀림에 대한 확신 정도(confidence)를 0~100 사이의 정수로 반환합니다.
    최종 결과는 각 문제에 대해 각 역할의 confidence 평균을 산출하고, 평균이 50 이상이면 맞음(true), 그렇지 않으면 틀림(false)으로 결정합니다.
    반환되는 결과는 각 문제의 ID와 최종 판정(correct)을 포함하는 GradeResult 리스트입니다.
    """
    prompt = create_grade_prompt(items)

    # 평가 역할 목록과 각 역할의 평가 기준 설명
    roles = [
        {
            "name": "전반적 평가자",
            "description": "전체적인 답안의 완성도, 정확성 및 정답과의 일치 정도를 평가하십시오. 답안이 정답에 부합한다고 판단되면 높은 확신(confidence)을, 그렇지 않으면 낮은 확신을 숫자로 반환하십시오."
        },
        {
            "name": "핵심 키워드 평가자",
            "description": "정답에 포함되어야 할 핵심 키워드나 유사 표현의 포함 여부를 평가하고, 포함되었다고 판단되면 높은 확신, 그렇지 않으면 낮은 확신을 숫자로 반환하십시오."
        },
        {
            "name": "논리성 평가자",
            "description": "답안의 논리적 전개, 일관성 및 근거의 명확성을 평가하고, 논리적으로 정답과 부합하면 높은 확신, 아니면 낮은 확신을 숫자로 반환하십시오."
        }
    ]

    role_confidences = []  # 각 역할별로 반환된 평가 결과 (JSON 배열)를 저장
    request_token_sum = 0  # 전체 GPT 호출에서 사용된 토큰 수를 누적
    response_token_sum = 0  # 전체 GPT 호출에서 반환된 토큰 수를 누적
    for role in roles:
        # 역할 정보를 시스템 프롬프트에 포함시키고, 각 역할이 confidence 값을 반환하도록 추가 설명합니다.
        system_prompt = GPTRequestDTO.grade_system_template.format(name=role["name"], role=role["description"])

        try:
            response = client.chat.completions.create(
                model=gpt_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
            ).choices[0].message.content.strip()

            request_token_sum += len(tokenizer.encode(system_prompt))
            request_token_sum += len(tokenizer.encode(prompt))
            response_token_sum += len(tokenizer.encode(response))

            print(f"[{role['name']}] Response:", response)
            answer_text = fix_json_commas(response)
            confidences = json.loads(answer_text)
            role_confidences.append(confidences)
        except Exception as e:
            print(f"[{role['name']}] Error:", e)
            raise Exception(f"{role['name']} 평가 중 오류 발생: " + str(e))

    # 역할별 결과를 문제 ID 기준으로 집계: {id: [confidence값, ...]}
    combined_confidences = {}
    for confidences in role_confidences:
        for item in confidences:
            id_val = item.get("id")
            conf_val = item.get("score")
            if id_val is None or conf_val is None:
                raise Exception(f"잘못된 평가 결과 형식: {item}")
            combined_confidences.setdefault(id_val, []).append(conf_val)

    # 각 문제별 평균 confidence를 산출하고, 평균이 50 이상이면 정답(true)으로 판정
    final_results = []
    for id_val, conf_list in combined_confidences.items():
        avg_conf = sum(conf_list) / len(conf_list)
        final_decision = avg_conf >= 50  # 임계값 50
        final_results.append(GradeResult(id=id_val, correct=final_decision))

    print(f"Request Token Sum: {request_token_sum},"
          f" cost: {request_token_sum / 1000.0 * gpt_request_cost * exchange_rate:.6f}원 ({request_token_sum / 1000.0 * gpt_request_cost:.6f}$)")
    print(f"Response Token Sum: {response_token_sum},"
          f" cost: {response_token_sum / 1000.0 * gpt_response_cost * exchange_rate:.6f}원 ({response_token_sum / 1000.0 * gpt_response_cost:.6f}$)")

    return final_results


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


def grade_blank_items(items: List[BlankItem], confidence_threshold: int) -> List[BlankResult]:
    """
    GPT API를 호출하여 각 BlankItem에 대해 여러 역할(예: 전반적 평가자, 핵심 단어 평가자, 논리성 평가자)로 채점을 수행합니다.
    각 역할은 학생의 빈칸 채우기 문제 답안이 정답(리스트)과 일치하는지 여부를 true/false로 평가합니다.
    최종 결과는 각 문제에 대해 역할별 평가를 집계하여 다수결(majority vote)로 최종 판정을 내며,
    각 문제의 ID와 최종 판정(correct)을 포함하는 BlankResult 리스트를 반환합니다.
    """
    prompt = create_blank_prompt(items)
    print(f"Prompt: {prompt}")

    # 평가 역할 목록 및 각 역할의 평가 기준 설명
    roles = [
        {
            "name": "전반적 평가자",
            "description": "문제 전체의 맥락과 정답과의 일치 여부를 평가하십시오."
        },
        {
            "name": "핵심 단어 평가자",
            "description": "정답에 포함되어야 할 핵심 단어의 포함 여부를 중점적으로 평가하십시오."
        },
        {
            "name": "논리성 평가자",
            "description": "학생의 답안이 문제의 의도와 논리적으로 부합하는지 평가하십시오."
        }
    ]

    role_confidences = []  # 각 역할별로 반환된 평가 결과 (JSON 배열)를 저장
    request_token_sum = 0  # 전체 GPT 호출에서 사용된 토큰 수를 누적
    response_token_sum = 0  # 전체 GPT 호출에서 반환된 토큰 수를 누적


    for role in roles:
        system_prompt = GPTRequestDTO.blank_system_template.format(
            name=role["name"],
            role=role["description"]
        )
        try:
            response = client.chat.completions.create(
                model=gpt_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
            ).choices[0].message.content.strip()

            request_token_sum += len(tokenizer.encode(system_prompt))
            request_token_sum += len(tokenizer.encode(prompt))
            response_token_sum += len(tokenizer.encode(response))

            print(f"[{role['name']}] Response:", response)
            answer_text = fix_json_commas(response)
            confidences = json.loads(answer_text)
            role_confidences.append(confidences)
        except Exception as e:
            print(f"[{role['name']}] Error:", e)
            raise Exception(f"{role['name']} 평가 중 오류 발생: " + str(e))

    # 역할별 결과를 문제 ID 기준으로 집계: {id: [confidence값, ...]}
    combined_confidences = {}
    for confidences in role_confidences:
        for item in confidences:
            id_val = item.get("id")
            conf_val = item.get("score")
            if id_val is None or conf_val is None:
                raise Exception(f"잘못된 평가 결과 형식: {item}")
            combined_confidences.setdefault(id_val, []).append(conf_val)

    # 각 문제별 평균 confidence를 산출하고, 평균이 50 이상이면 정답(true)으로 판정
    final_results = []
    for id_val, conf_list in combined_confidences.items():
        avg_conf = sum(conf_list) / len(conf_list)
        final_decision = avg_conf >= confidence_threshold  # 임계값 50
        final_results.append(BlankResult(id=id_val, correct=final_decision))

    print(f"Request Token Sum: {request_token_sum},"
          f" cost: {request_token_sum / 1000.0 * gpt_request_cost * exchange_rate:.6f}원 ({request_token_sum / 1000.0 * gpt_request_cost:.6f}$)")
    print(f"Response Token Sum: {response_token_sum},"
          f" cost: {response_token_sum / 1000.0 * gpt_response_cost * exchange_rate:.6f}원 ({response_token_sum / 1000.0 * gpt_response_cost:.6f}$)")
    return final_results
