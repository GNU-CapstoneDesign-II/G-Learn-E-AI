# app/main.py
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.responses import HTMLResponse

from repository.database import engine
from repository.models import Base
from controller.DatabaseController import router as db_router
from controller.ProblemMakerController import router as maker_router
from controller.ConverterController import router as converter_router

load_dotenv()
app = FastAPI()

# DB 테이블 생성
Base.metadata.create_all(bind=engine)

app.include_router(db_router)
app.include_router(maker_router)
app.include_router(converter_router)

example_body = {
    "content": "시험 정리본",  # 사용자가 작성한 정리본
    "difficulty": "상",  # or "중", "하"
    "question_types": {
        "multiple_choice": {  # 객관식
            "enabled": True,
            "num_questions": 5,
            "num_options": 4
        },
        "ox": {  # OX
            "enabled": True,
            "num_questions": 3
        },
        "fill_in_the_blank": {  # 빈칸 채우기
            "enabled": True,
            "num_questions": 3
        },
        "descriptive": {  # 서술형
            "enabled": True,
            "num_questions": 2
        }
    }
}


# 간단한 웹 페이지를 제공하는 GET 엔드포인트
@app.get("/", response_class=HTMLResponse)
def get_index():
    html_content = """
    <html>
    <head>
        <title>Make Problem API Test</title>
    </head>
    <body>
        <h1>Make Problem API Test</h1>
        <form id="make-problem-form">
            <label for="content">Content (정리본):</label><br>
            <textarea id="content" name="content" rows="4" cols="50">시험 정리본</textarea><br><br>

            <label for="difficulty">Difficulty (난이도):</label>
            <input type="text" id="difficulty" name="difficulty" value="상"><br><br>

            <label for="question_types">Question Types (JSON 형식):</label><br>
            <textarea id="question_types" name="question_types" rows="10" cols="50">
{
  "multiple_choice": {
      "enabled": true,
      "num_questions": 5,
      "num_options": 4
  },
  "ox": {
      "enabled": true,
      "num_questions": 3
  },
  "fill_in_the_blank": {
      "enabled": true,
      "num_questions": 3
  },
  "descriptive": {
      "enabled": true,
      "num_questions": 2
  }
}
            </textarea><br><br>

            <button type="button" onclick="submitForm()">Submit</button>
        </form>

        <h2>Result</h2>
        <pre id="result"></pre>

        <script>
            async function submitForm(){
                const content = document.getElementById("content").value;
                const difficulty = document.getElementById("difficulty").value;
                let question_types;
                try {
                    question_types = JSON.parse(document.getElementById("question_types").value);
                } catch (e) {
                    alert("Invalid JSON for question_types");
                    return;
                }

                const response = await fetch("/make-problem", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        content: content,
                        difficulty: difficulty,
                        question_types: question_types
                    })
                });

                const data = await response.json();
                document.getElementById("result").textContent = JSON.stringify(data, null, 2);
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
