from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import os

from dto.RepositoryDTO import (
    UsageStatsResponseDTO,
    LogsResponseDTO,
    LogItemDTO,
    TokenUsageDTO
)
from repository.database import SessionLocal
from repository.repository import (
    add_token_usage,
    get_daily_usage, get_weekly_usage, get_monthly_usage
)
from repository.request_log_repository import (
    get_daily_logs, get_weekly_logs, get_monthly_logs
)
from typing import Tuple, List

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


gpt_request_cost = float(os.getenv("GPT_REQUEST_COST", "0.00015"))
gpt_response_cost = float(os.getenv("GPT_RESPONSE_COST", "0.0006"))
exchange_rate = float(os.getenv("EXCHANGE_RATE", "1300"))


# -----------------------------------------------------------------------------
#  1) 공용 유틸 함수: 날짜 파싱
# -----------------------------------------------------------------------------
def parse_date_str(date_str: str) -> datetime:
    """
    YYYY-MM-DD 형태의 문자열을 datetime으로 파싱하고,
    형식이 잘못된 경우 HTTPException을 발생시킵니다.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


# -----------------------------------------------------------------------------
#  2) 공용 유틸 함수: 토큰 사용량 조회 + 비용 계산 (일/주/월)
# -----------------------------------------------------------------------------
def get_usage_stats(
        db: Session, dt: datetime, period: str
) -> Tuple[str, str, int, int, float, float]:
    """
    period: "daily", "weekly", "monthly"
    반환: (key, keyValue, req_tokens, resp_tokens, costUsd, costWon)
    """
    # 1) period별 usage 함수 매핑
    usage_func_map = {
        "daily": get_daily_usage,
        "weekly": get_weekly_usage,
        "monthly": get_monthly_usage
    }
    # 2) period별 key 이름 (date, weekStarting, month)
    key_map = {
        "daily": ("date", dt.strftime("%Y-%m-%d")),
        "weekly": ("weekStarting", dt.strftime("%Y-%m-%d")),
        "monthly": ("month", dt.strftime("%Y-%m"))
    }

    if period not in usage_func_map:
        raise HTTPException(status_code=400, detail="Invalid period")

    get_usage_func = usage_func_map[period]
    req_tokens, resp_tokens = get_usage_func(db, dt)

    cost_usd = (req_tokens * gpt_request_cost / 1000.0) + (resp_tokens * gpt_response_cost / 1000.0)
    cost_won = cost_usd * exchange_rate

    key, key_value = key_map[period]
    return (key, key_value, req_tokens, resp_tokens, cost_usd, cost_won)


# -----------------------------------------------------------------------------
#  3) 공용 유틸 함수: 로그 + TokenUsage 조회 (일/주/월)
# -----------------------------------------------------------------------------
def get_logs_data(db: Session, dt: datetime, period: str) -> Tuple[str, str, List[LogItemDTO]]:
    """
    period: "daily", "weekly", "monthly"
    반환: (key, keyValue, List[LogItemDTO])
    """
    logs_func_map = {
        "daily": get_daily_logs,
        "weekly": get_weekly_logs,
        "monthly": get_monthly_logs
    }
    key_map = {
        "daily": ("date", dt.strftime("%Y-%m-%d")),
        "weekly": ("weekStarting", dt.strftime("%Y-%m-%d")),
        "monthly": ("month", dt.strftime("%Y-%m"))
    }

    if period not in logs_func_map:
        raise HTTPException(status_code=400, detail="Invalid period")

    logs = logs_func_map[period](db, dt)
    key, key_value = key_map[period]

    # RequestLog + TokenUsage를 LogItemDTO로 변환
    results = []
    for log in logs:
        usage = log.token_usage
        cost_usd = 0
        cost_won = 0
        if usage:
            cost_usd = ((usage.request_tokens * gpt_request_cost) +
                        (usage.response_tokens * gpt_response_cost)) / 1000.0
            cost_won = cost_usd * exchange_rate

        token_usage_dto = TokenUsageDTO(
            requestTokens=usage.request_tokens if usage else 0,
            responseTokens=usage.response_tokens if usage else 0,
            costUsd=cost_usd,
            costWon=cost_won,
        ) if usage else None

        results.append(
            LogItemDTO(
                id=log.id,
                timestamp=log.timestamp,
                apiUrl=log.api_url,
                method=log.method,
                parameters=log.parameters,
                tokenUsage=token_usage_dto
            )
        )

    return (key, key_value, results)


# -----------------------------------------------------------------------------
#  4) 실제 라우터:  /stats/{period},  /logs/{period}
# -----------------------------------------------------------------------------

@router.post("/log/token_usage")
def log_token_usage(request_tokens: int, response_tokens: int, db: Session = Depends(get_db)):
    """API 요청에 사용된 토큰 값을 기록"""
    usage = add_token_usage(db, request_tokens, response_tokens)
    return {
        "id": usage.id,
        "timestamp": usage.timestamp.isoformat()
    }


@router.get("/stats/daily", response_model=UsageStatsResponseDTO)
def daily_stats(date: str, db: Session = Depends(get_db)):
    dt = parse_date_str(date)
    key, key_value, req, resp, cost_usd, cost_won = get_usage_stats(db, dt, "daily")
    return UsageStatsResponseDTO(
        # key=key,
        # keyValue=key_value,
        requestTokens=req,
        responseTokens=resp,
        costUsd=round(cost_usd, 6),
        costWon=round(cost_won, 2)
    )


@router.get("/stats/weekly", response_model=UsageStatsResponseDTO)
def weekly_stats(date: str, db: Session = Depends(get_db)):
    dt = parse_date_str(date)
    key, key_value, req, resp, cost_usd, cost_won = get_usage_stats(db, dt, "weekly")
    return UsageStatsResponseDTO(
        # key=key,
        # keyValue=key_value,
        requestTokens=req,
        responseTokens=resp,
        costUsd=round(cost_usd, 6),
        costWon=round(cost_won, 2)
    )


@router.get("/stats/monthly", response_model=UsageStatsResponseDTO)
def monthly_stats(date: str, db: Session = Depends(get_db)):
    dt = parse_date_str(date)
    key, key_value, req, resp, cost_usd, cost_won = get_usage_stats(db, dt, "monthly")
    return UsageStatsResponseDTO(
        # key=key,
        # keyValue=key_value,
        requestTokens=req,
        responseTokens=resp,
        costUsd=round(cost_usd, 6),
        costWon=round(cost_won, 2)
    )


@router.get("/logs/daily", response_model=LogsResponseDTO)
def daily_logs(date: str, db: Session = Depends(get_db)):
    dt = parse_date_str(date)
    key, key_value, logs = get_logs_data(db, dt, "daily")
    return LogsResponseDTO(logs=logs)


@router.get("/logs/weekly", response_model=LogsResponseDTO)
def weekly_logs(date: str, db: Session = Depends(get_db)):
    dt = parse_date_str(date)
    key, key_value, logs = get_logs_data(db, dt, "weekly")
    return LogsResponseDTO(logs=logs)


@router.get("/logs/monthly", response_model=LogsResponseDTO)
def monthly_logs(date: str, db: Session = Depends(get_db)):
    dt = parse_date_str(date)
    key, key_value, logs = get_logs_data(db, dt, "monthly")
    return LogsResponseDTO(logs=logs)
