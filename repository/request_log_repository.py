# repository/request_log_repository.py
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from repository.models import TokenUsage, RequestLog


def get_logs_in_period(db: Session, start: datetime, end: datetime):
    """
    특정 기간 [start, end) 안에 발생한 RequestLog를 모두 반환.
    """
    return db.query(RequestLog).filter(
        RequestLog.timestamp >= start,
        RequestLog.timestamp < end
    ).all()


def get_daily_logs(db: Session, date: datetime):
    start = datetime(date.year, date.month, date.day)
    end = start + timedelta(days=1)
    return get_logs_in_period(db, start, end)


def get_weekly_logs(db: Session, date: datetime):
    # 주의 시작일(월요일)을 구합니다.
    start = date - timedelta(days=date.weekday())
    start = datetime(start.year, start.month, start.day)
    end = start + timedelta(days=7)
    return get_logs_in_period(db, start, end)


def get_monthly_logs(db: Session, date: datetime):
    start = datetime(date.year, date.month, 1)
    if date.month == 12:
        end = datetime(date.year + 1, 1, 1)
    else:
        end = datetime(date.year, date.month + 1, 1)
    return get_logs_in_period(db, start, end)
