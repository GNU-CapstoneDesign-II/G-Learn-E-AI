# models.py
from sqlalchemy import Column, Integer, DateTime, String, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

from sqlalchemy.orm import relationship

Base = declarative_base()


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    request_tokens = Column(Integer, nullable=False)
    response_tokens = Column(Integer, nullable=False)

    # RequestLog와 1:1 연관관계
    request_log = relationship("RequestLog", back_populates="token_usage", uselist=False)



class RequestLog(Base):
    __tablename__ = "request_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    api_url = Column(String(200), nullable=False)  # API URL
    method = Column(String(10), nullable=False)    # GET, POST 등
    parameters = Column(Text, nullable=True)       # 바디 또는 쿼리 파라미터를 JSON 직렬화해 저장

    # 토큰 사용량과 1:1 매핑한다고 가정 (한번의 요청마다 토큰 사용량이 기록된다고 보면 됨)
    token_usage_id = Column(Integer, ForeignKey("token_usage.id"), nullable=True)
    token_usage = relationship("TokenUsage", back_populates="request_log")