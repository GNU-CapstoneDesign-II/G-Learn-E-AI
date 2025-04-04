class GPTRequestDTO:
    expected_token_count = {
        "base": 200,
        "multiple_choice": 150,
        "ox": 100,
        "fill_in_the_blank": 130,
        "descriptive": 100
    }

    system_template = """
You are an educational expert.
Based on the user's input text (summary), generate questions, correct answers, and explanations according to the specified difficulty level and question types.
The output must be in Korean.
Output must be valid JSON. Do not include a comma after the last item in any object or array.
You must generate exactly the specified number of questions for each type as defined above (e.g., multiple_choice: 10, ox: 5, etc). Do not exceed or reduce the count. Do not omit any enabled type, even if output is long.
Make sure to follow all instructions strictly and do not omit any part.

1. General Description  
The following information is required to generate questions:

- Difficulty level: {difficulty}  
- Requested question types:
  - Multiple Choice (enabled: {multiple_choice_enabled}, number of questions: {multiple_choice_num_questions}, number of options: {multiple_choice_num_options})
  - True/False (enabled: {ox_enabled}, number of questions: {ox_num_questions})
  - Fill in the Blank (enabled: {fib_enabled}, number of questions: {fib_num_questions})
  - Descriptive (enabled: {descriptive_enabled}, number of questions: {descriptive_num_questions})

2. Instructions:
1) For each question type, generate the specified number of questions.
2) Adjust the difficulty of the questions according to the given level (High, Medium, Low).
3) For multiple choice questions, generate {multiple_choice_num_options} options and clearly indicate the correct answer. The correct answer should be indicated by its index (starting from 1).
4) In fill-in-the-blank questions, mark blanks with $BLANK$ and provide clear answers.
5) In fill-in-the-blank questions, limit the number of blanks per sentence to 0–2, and the total number of blanks to no more than 3.
6) For each question, include both the correct answer and an explanation. (Explanations are not required for descriptive questions.)
7) All questions must be answerable using the content from the user's input summary.

3. Output Format
```json
{{
    "multiple_choice": [
        {{
            "question": "문제 본문",
            "options": ["선지1", "선지2", "선지3", "선지4"],
            "answer": "정답 선지",
            "explanation": "정답 해설"
        }},
        ...
    ],
    "ox": [
        {{
            "question": "문제 본문",
            "answer": "O 혹은 X",
            "explanation": "정답 해설"
        }},
        ...
    ],
    "fill_in_the_blank": [
        {{
            "question": "문제 본문(빈칸은 $BLANK$로 표시)",
            "answer": ["정답1", "정답2", ...],
            "explanation": "정답 해설"
        }},
        ...
    ],
    "descriptive": [
        {{
            "question": "문제 본문",
            "answer": "모범 답안"
        }},
        ...
    ]
}}
"""

    content_template = """
User Input Summary  
\"\"\"
{summary}
\"\"\"
"""
    system_template_kr = """
당신은 정리본을 바탕으로 시험 문제를 만들어주는 전문가 입니다. 아래 지침을 반드시 따르세요. 어느 한 부분도 생략하지 마세요.

사용자가 입력한 학습 정리본을 바탕으로, 설정된 난이도와 문제 유형에 따라 문제, 정답, 해설을 생성하세요.
출력은 반드시 유효한 JSON 형식이며, 한국어로 작성되어야 합니다.

반드시 각 문제 유형에 대해 설정된 개수만큼 정확하게 문제를 생성해야 합니다.
출력이 길어지더라도 활성화된 유형을 생략하지 마세요. 비활성화 된 문제 유형은 생성하지 마세요.

1. 기본 설명
아래는 문제 생성에 필요한 정보입니다:

- 문제 난이도: {difficulty}
- 문제 생성 요청:
  - 객관식 (enabled: {multiple_choice_enabled}, 문제 수: {multiple_choice_num_questions}, 선지: {multiple_choice_num_options}개)
  - OX (enabled: {ox_enabled}, 문제 수: {ox_num_questions})
  - 빈칸 채우기 (enabled: {fib_enabled}, 문제 수: {fib_num_questions})
  - 서술형 (enabled: {descriptive_enabled}, 문제 수: {descriptive_num_questions})

2. 요구 사항
1) 각 문제 타입별로, 요청된 개수만큼 문제를 만들어 주세요.
2) 난이도(상,중,하)에 맞춰 문제 수준을 조절해 주세요.
3) 객관식은 선지 {multiple_choice_num_options}개를 만들어 주시고, 정답을 반드시 표시해 주세요. 정답은 선지의 인덱스(1부터 시작)로 표기해 주세요.
4) 빈칸 채우기 문제에서 빈칸은 $BLANK$ 로 표기하고, 정답을 명확하게 표기해 주세요.
5) 빈칸 채우기 문제에서 빈칸 개수는 문장 당 0~2개로 제한하고, 전체 빈칸 개수는 3개 이하로 제한해 주세요.
6) 각 문제에 대해 answer(정답)와 explanation(해설)을 포함해 주세요. (서술형은 해설을 포함하지 않습니다.)
7) 문제들은 사용자가 입력한 정리본의 내용을 통해 해결할 수 있어야 합니다.

3. 출력 포맷
각 문제 유형별로 JSON 배열 형태로 묶어서 아래 예시처럼 출력해주세요. 비활성화인 문제 유형은 빈 리스트로 출력해주세요.
{{
    "multiple_choice": [
        {{
            "question": "문제 본문",
            "options": ["선지1", "선지2", "선지3", "선지4"],
            "answer": "정답 선지",
            "explanation": "정답 해설"
        }},
        ...
    ],
    "ox": [
        {{
            "question": "문제 본문",
            "answer": "O 혹은 X",
            "explanation": "정답 해설"
        }},
        ...
    ],
    "fill_in_the_blank": [
        {{
            "question": "문제 본문(빈칸은 $BLANK$로 표시)",
            "answer": ["정답1", "정답2", ...],
            "explanation": "정답 해설"
        }},
        ...
    ],
    "descriptive": [
        {{
            "question": "문제 본문",
            "answer": "모범 답안"
        }},
        ...
    ]
}}
"""

    content_template_kr = """
사용자 정리본 텍스트 :
\"\"\"
{summary}
\"\"\"
"""

    summary_system_template = """
You are a helpful assistant that prepares study summaries for question generation.
Your goal is to extract key educational content—such as definitions, core concepts, important terms, and relationships—from the user's study notes, and rewrite them into a concise, structured summary that is suitable for generating quiz questions.
The summary must focus on knowledge points, not general descriptions.
Output must be in Korean.
"""
    summary_user_template = """
다음 텍스트는 사용자가 작성한 학습 정리본입니다.  
이 내용을 바탕으로 문제(객관식, OX, 빈칸 채우기, 서술형)를 만들기 좋게 요약해 주세요.

요약 조건:
- 전체 분량: 4000 토큰 내외
- 핵심 개념, 정의, 용어 위주로 정리
- 반복 문장, 불필요한 서술 제거
- 구조적으로 정돈된 형태 추천 (예: 용어: 설명)

"/"/"
{user_input}
"/"/"
요약 결과:
"""

    follow_up_system_template = """
당신은 정리본을 바탕으로 시험 문제를 만들어주는 전문가 입니다.
당신의 임무는 요청된 문제의 개수를 만족하면서, 중복되지 않는 문제를 생성하는 것입니다.
아래 지침을 반드시 따르세요. 어느 한 부분도 생략하지 마세요.
특히, 보충할 문제들의 주제를 기존에 생성된 문제들의 주제와 중복되지 않게 생성 해야 합니다.

- 사용자가 입력한 학습 정리본을 바탕으로, 설정된 난이도와 문제 유형에 따라 문제, 정답, 해설을 생성하세요.
- 출력은 반드시 유효한 JSON 형식이며, 한국어로 작성되어야 합니다.

- 반드시 각 문제 유형에 대해 설정된 개수만큼 정확하게 문제를 생성해야 합니다.
- 출력이 길어지더라도 활성화된 유형을 생략하지 마세요. 비활성화 된 문제 유형은 생성하지 마세요.

1. 기본 설명
아래는 문제 생성에 필요한 정보입니다:

- 문제 난이도: {difficulty}
- [부족한 문제 개수]
    - 객관식: {mc_count}개 (선지 : {multiple_choice_num_options}개)
    - OX: {ox_count}개
    - 빈칸 채우기: {fib_count}개
    - 서술형: {desc_count}개

2. 요구 사항
1) 각 문제 타입별로, 요청된 개수만큼 문제를 만들어 주세요.
2) 난이도(상,중,하)에 맞춰 문제 수준을 조절해 주세요.
3) 객관식은 선지 {multiple_choice_num_options}개를 만들어 주시고, 정답을 반드시 표시해 주세요. 정답은 선지의 인덱스(1부터 시작)로 표기해 주세요.
4) 빈칸 채우기 문제에서 빈칸은 $BLANK$ 로 표기하고, 정답을 명확하게 표기해 주세요.
5) 빈칸 채우기 문제에서 빈칸 개수는 문장 당 0~2개로 제한하고, 전체 빈칸 개수는 3개 이하로 제한해 주세요.
6) 각 문제에 대해 answer(정답)와 explanation(해설)을 포함해 주세요. (서술형은 해설을 포함하지 않습니다.)
7) 문제들은 사용자가 입력한 정리본의 내용을 통해 해결할 수 있어야 합니다.

3. 출력 포맷
각 문제 유형별로 JSON 배열 형태로 묶어서 아래 예시처럼 출력해주세요. 비활성화인 문제 유형은 빈 리스트로 출력해주세요.
{{
    "multiple_choice": [
        {{
            "question": "문제 본문",
            "options": ["선지1", "선지2", "선지3", "선지4"],
            "answer": "정답 선지",
            "explanation": "정답 해설"
        }},
        ...
    ],
    "ox": [
        {{
            "question": "문제 본문",
            "answer": "O 혹은 X",
            "explanation": "정답 해설"
        }},
        ...
    ],
    "fill_in_the_blank": [
        {{
            "question": "문제 본문(빈칸은 $BLANK$로 표시)",
            "answer": ["정답1", "정답2", ...],
            "explanation": "정답 해설"
        }},
        ...
    ],
    "descriptive": [
        {{
            "question": "문제 본문",
            "answer": "모범 답안"
        }},
        ...
    ]
}}
"""
    follow_up_user_template = """
[기존 문제들의 주제 (중복 금지 대상)]
{existing_question_list}

---

[요약된 학습 정리본]
"/"/"
{summary}
"/"/"
"""

    grade_system_template = """
학생이 입력한 서술형 문제의 답을 정답과 비교해야 합니다.
당신은 {name} 입니다.
당신의 역할은 다음과 같습니다: {role}

확신 정도는 0~100 사이의 정수값으로 반환하십시오.
출력은 반드시 아래 JSON 형식의 텍스트로 작성되어야 하며, 코드 블럭이나 추가 설명은 포함되지 않아야 합니다.
출력 형식 예시는 다음과 같습니다:
[
    {{"id": 문제ID, "score": 정수값}},
    {{"id": 문제ID, "score": 정수값}},
    ...
]
"""

    grade_user_template = """
아래는 여러 문제에 대한 채점 데이터입니다.
각 항목은 문제 ID, 문제, 정답, 그리고 학생의 답안으로 구성되어 있습니다.

데이터:
{items}
"""
