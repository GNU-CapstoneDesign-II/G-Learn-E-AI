# repository.py
import json

from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from repository.models import TokenUsage, RequestLog


def add_token_usage(db: Session, request_tokens: int, response_tokens: int):
    usage = TokenUsage(request_tokens=request_tokens, response_tokens=response_tokens)
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage


def get_usage_by_period(db: Session, start: datetime, end: datetime):
    usages = db.query(TokenUsage).filter(TokenUsage.timestamp >= start, TokenUsage.timestamp < end).all()
    total_request = sum(u.request_tokens for u in usages)
    total_response = sum(u.response_tokens for u in usages)
    return total_request, total_response


def get_daily_usage(db: Session, date: datetime):
    start = datetime(date.year, date.month, date.day)
    end = start + timedelta(days=1)
    return get_usage_by_period(db, start, end)


def get_weekly_usage(db: Session, date: datetime):
    # 주의 시작일은 월요일로 가정
    start = date - timedelta(days=date.weekday())
    start = datetime(start.year, start.month, start.day)
    end = start + timedelta(days=7)
    return get_usage_by_period(db, start, end)


def get_monthly_usage(db: Session, date: datetime):
    start = datetime(date.year, date.month, 1)
    if date.month == 12:
        end = datetime(date.year + 1, 1, 1)
    else:
        end = datetime(date.year, date.month + 1, 1)
    return get_usage_by_period(db, start, end)


def create_request_log(db: Session, api_url: str, method: str, params: dict, max_len: int = 1000):
    """
    RequestLog 테이블에 API 요청 정보를 저장.
    params는 쿼리 스트링 또는 바디 파라미터 등을 딕셔너리로 받아 JSON 직렬화해서 저장.
    너무 긴 경우 일부만 저장하고, 생략된 문자 수를 표시한다.
    """
    # 1) JSON 직렬화
    param_str = json.dumps(params) if params else ""

    # 2) 길이 제한 적용
    if len(param_str) > max_len:
        truncated_count = len(param_str) - max_len
        param_str = f"{param_str[:max_len]}...(truncated {truncated_count} chars)"

    # 3) DB에 저장
    log = RequestLog(
        api_url=api_url,
        method=method,
        parameters=param_str
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def link_token_usage(db: Session, request_log_id: int, token_usage_id: int):
    """
    RequestLog와 TokenUsage를 연결 (1:1)
    """
    log = db.query(RequestLog).filter_by(id=request_log_id).first()
    if log:
        log.token_usage_id = token_usage_id
        db.commit()
        db.refresh(log)
    return log


def log_and_save_tokens(
        db: Session,
        api_url: str,
        method: str,
        params: dict,
        request_tokens: int,
        response_tokens: int
):
    """
    RequestLog 생성 → TokenUsage 생성 → 두 테이블 매핑 과정을
    한 번에 처리하는 헬퍼 함수.
    """
    # 1) RequestLog 생성
    log = create_request_log(db, api_url, method, params)

    # 2) TokenUsage 저장
    usage = add_token_usage(db, request_tokens, response_tokens)

    # 3) 두 개 연결
    link_token_usage(db, log.id, usage.id)

    return log, usage
