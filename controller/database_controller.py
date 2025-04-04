# controllers.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import os

from dto.CommonDTO import BlankRequestDTO
from repository.database import SessionLocal
from repository.repository import add_token_usage, get_daily_usage, get_weekly_usage, get_monthly_usage
from repository.request_log_repository import get_daily_logs, get_weekly_logs, get_monthly_logs
from service.gpt_service import grade_blank_items

router = APIRouter()


# DB 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


gpt_request_cost = float(os.getenv("GPT_REQUEST_COST", "0.00015"))
gpt_response_cost = float(os.getenv("GPT_RESPONSE_COST", "0.0006"))
exchange_rate = float(os.getenv("EXCHANGE_RATE", "1300"))


@router.post("/log/token_usage")
def log_token_usage(request_tokens: int, response_tokens: int, db: Session = Depends(get_db)):
    """
    API 요청에 사용된 토큰 값을 기록합니다.
    """
    usage = add_token_usage(db, request_tokens, response_tokens)
    return {"id": usage.id, "timestamp": usage.timestamp.isoformat()}


@router.get("/stats/daily")
def daily_stats(date: str, db: Session = Depends(get_db)):
    """
    YYYY-MM-DD 형식의 날짜를 받아 해당 날짜의 request, response 토큰과 비용(원, 달러)를 반환합니다.
    """
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    req_tokens, resp_tokens = get_daily_usage(db, dt)

    cost_usd = req_tokens * gpt_request_cost / 1000.0 + resp_tokens * gpt_response_cost / 1000.0
    cost_won = cost_usd * exchange_rate
    return {
        "date": date,
        "request_tokens": req_tokens,
        "response_tokens": resp_tokens,
        "cost_usd": round(cost_usd, 6),
        "cost_won": round(cost_won, 2)
    }


@router.get("/stats/weekly")
def weekly_stats(date: str, db: Session = Depends(get_db)):
    """
    YYYY-MM-DD 형식의 날짜를 받아 해당 주(월요일 시작)의 request, response 토큰과 비용(원, 달러)를 반환합니다.
    """
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    req_tokens, resp_tokens = get_weekly_usage(db, dt)

    cost_usd = req_tokens * gpt_request_cost / 1000.0 + resp_tokens * gpt_response_cost / 1000.0
    cost_won = cost_usd * exchange_rate
    return {
        "week_starting": dt.strftime("%Y-%m-%d"),
        "request_tokens": req_tokens,
        "response_tokens": resp_tokens,
        "cost_usd": round(cost_usd, 6),
        "cost_won": round(cost_won, 2)
    }


@router.get("/stats/monthly")
def monthly_stats(date: str, db: Session = Depends(get_db)):
    """
    YYYY-MM-DD 형식의 날짜를 받아 해당 달의 request, response 토큰과 비용(원, 달러)를 반환합니다.
    """
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    req_tokens, resp_tokens = get_monthly_usage(db, dt)

    cost_usd = req_tokens * gpt_request_cost / 1000.0 + resp_tokens * gpt_response_cost / 1000.0
    cost_won = cost_usd * exchange_rate
    return {
        "month": dt.strftime("%Y-%m"),
        "request_tokens": req_tokens,
        "response_tokens": resp_tokens,
        "cost_usd": round(cost_usd, 6),
        "cost_won": round(cost_won, 2)
    }


# ---------------------------------
# 일/주/월 간 RequestLog + TokenUsage 조회
# ---------------------------------

@router.get("/logs/daily")
def daily_logs(date: str, db: Session = Depends(get_db)):
    """
    YYYY-MM-DD 형식의 날짜를 받아 해당 날짜에 발생한 RequestLog와
    매핑된 TokenUsage를 모두 반환합니다.
    """
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    logs = get_daily_logs(db, dt)
    # 각 로그에 대해 token_usage를 함께 JSON 형태로 구성
    results = convert_logs_to_results(logs)
    return {"date": date, "logs": results}


@router.get("/logs/weekly")
def weekly_logs(date: str, db: Session = Depends(get_db)):
    """
    YYYY-MM-DD 형식의 날짜를 받아 해당 주(월요일 시작)에 발생한 RequestLog와
    매핑된 TokenUsage를 모두 반환합니다.
    """
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    logs = get_weekly_logs(db, dt)
    results = convert_logs_to_results(logs)
    return {"week_starting": dt.strftime("%Y-%m-%d"), "logs": results}


@router.get("/logs/monthly")
def monthly_logs(date: str, db: Session = Depends(get_db)):
    """
    YYYY-MM-DD 형식의 날짜를 받아 해당 월에 발생한 RequestLog와
    매핑된 TokenUsage를 모두 반환합니다.
    """
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    logs = get_monthly_logs(db, dt)
    results = convert_logs_to_results(logs)
    return {"month": dt.strftime("%Y-%m"), "logs": results}


def convert_logs_to_results(logs):
    """
    RequestLog와 TokenUsage를 JSON 형태로 변환합니다.
    """
    results = []
    for log in logs:
        usage = log.token_usage
        results.append({
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "api_url": log.api_url,
            "method": log.method,
            "parameters": log.parameters,
            "token_usage": {
                "id": usage.id if usage else None,
                "request_tokens": usage.request_tokens if usage else 0,
                "response_tokens": usage.response_tokens if usage else 0,
                "cost_usd": (usage.request_tokens * gpt_request_cost + usage.response_tokens * gpt_response_cost) / 1000.0 if usage else 0,
                "cost_won": ((usage.request_tokens * gpt_request_cost + usage.response_tokens * gpt_response_cost) / 1000.0) * exchange_rate if usage else 0,
                "timestamp": usage.timestamp.isoformat() if usage else None
            }
        })
    return results
