# controller/KeywordExtractorController.py
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, conint
from sqlalchemy.orm import Session

from controller.DatabaseController import get_db
from repository.repository import log_and_save_tokens
from service.keyword_extractor_gpt import extract_keywords_gpt

router = APIRouter()


# ─────────────────────────────────────────────────────────────
# Pydantic 스키마
# ─────────────────────────────────────────────────────────────
class ProblemIn(BaseModel):
    id: int
    title: str
    # ⬇️ 3.9에서는 Optional[List[Optional[Dict[str, Any]]]] 로 표기
    options: Optional[List[Optional[Dict[str, Any]]]] = None
    answers: Optional[List[str]] = None
    explanation: Optional[str] = None
    type: str = Field(..., pattern="MULTIPLE|BLANK|OX|DESCRIPTIVE")

class KeywordRequest(BaseModel):
    problems: List[ProblemIn]
    topN: conint(gt=0, le=10) = 5   # 1~10 사이

class KeywordResponse(BaseModel):
    problems: List[Dict[str, Any]]
    requestTokens: int
    responseTokens: int
    estimatedCostKrw: float


# ─────────────────────────────────────────────────────────────
# POST /keywords
# ─────────────────────────────────────────────────────────────
@router.post(
    "/extract-keywords",
    response_model=KeywordResponse,
    summary="문제 리스트에서 핵심 키워드 추출"
)
async def get_keywords(
        payload: KeywordRequest,
        db: Session = Depends(get_db),
        request: Request = None
):
    try:
        result = extract_keywords_gpt(
            [p.model_dump() for p in payload.problems],
            payload.topN
        )
        print(f"result: {result}")

        # 토큰 로그 저장
        log_and_save_tokens(
            db          = db,
            api_url     = str(request.url) if request else "/keywords",
            method      = request.method if request else "POST",
            params      = {"problem_count": len(payload.problems), "top_n": payload.topN},
            request_tokens  = result["requestTokens"],
            response_tokens = result["responseTokens"]
        )

        return result

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"키워드 추출 실패: {e}")
