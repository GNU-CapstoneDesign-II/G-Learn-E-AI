# controllers.py
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session

from controller.database_controller import get_db
from dto.CommonDTO import BlankRequestDTO, PromptRequest, MakeProblemRequest, GradeRequestDTO
from repository.repository import log_and_save_tokens
from service.gpt_service import grade_blank_items, ask_gpt, make_problem, grade_items

router = APIRouter()


@router.post("/ask")
def ask_endpoint(req: PromptRequest):
    result = ask_gpt(req.prompt)
    return {"answer": result}


@router.post("/make-problem")
def make_problems(req: MakeProblemRequest, db: Session = Depends(get_db), request: Request = None):
    try:
        result = make_problem(req.content, req.difficulty, req.question_types)

        # 리포지토리 함수 한 번으로 로깅 + 토큰 저장 + 매핑 처리
        log, usage = log_and_save_tokens(
            db=db,
            api_url=str(request.url),
            method=request.method,
            params=req.dict(),
            request_tokens=result["request_tokens"],
            response_tokens=result["response_tokens"]
        )

        return {"result": result["result"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/grade")
async def grade_endpoint(req: GradeRequestDTO, db: Session = Depends(get_db), request: Request = None):
    """
    여러 문제에 대한 채점을 처리하는 엔드포인트.
    요청으로부터 items를 받아 GPT API를 통해 채점 후 점수와 문제 ID를 반환.
    """
    try:
        result = grade_items(req.items)

        # 리포지토리 함수 한 번으로 로깅 + 토큰 저장 + 매핑 처리
        log, usage = log_and_save_tokens(
            db=db,
            api_url=str(request.url),
            method=request.method,
            params=req.dict(),
            request_tokens=result["request_tokens"],
            response_tokens=result["response_tokens"]
        )

        return {"result": result["result"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/grade/blank")
async def grade_blank_endpoint(req: BlankRequestDTO, db: Session = Depends(get_db), request: Request = None):
    """
    여러 빈칸 채우기 문제에 대한 채점을 처리하는 엔드포인트.
    요청으로부터 items를 받아 GPT API를 통해 채점 후, 각 문제의 ID와 맞았는지 여부를 반환합니다.
    반환 형식:
    {
        "result": [
            {"id": 1, "correct": true},
            {"id": 2, "correct": false},
            ...
        ]
    }
    """
    try:
        result = grade_blank_items(req.items)

        # 리포지토리 함수 한 번으로 로깅 + 토큰 저장 + 매핑 처리
        log, usage = log_and_save_tokens(
            db=db,
            api_url=str(request.url),
            method=request.method,
            params=req.dict(),
            request_tokens=result["request_tokens"],
            response_tokens=result["response_tokens"]
        )

        return {"result": result["result"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
