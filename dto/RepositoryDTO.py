from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime


class TokenUsageDTO(BaseModel):
    requestTokens: int
    responseTokens: int
    costUsd: float
    costWon: float


class LogItemDTO(BaseModel):
    id: int
    timestamp: datetime
    apiUrl: str
    method: str
    parameters: str
    tokenUsage: Optional[TokenUsageDTO]


# --------------------------------
# 통계 응답 공용 (일/주/월)
# --------------------------------
class UsageStatsResponseDTO(BaseModel):
    # key: str  # daily면 "date", weekly면 "weekStarting" 등
    # keyValue: str
    requestTokens: int
    responseTokens: int
    costUsd: float
    costWon: float


# --------------------------------
# 로그 응답 공용 (일/주/월)
# --------------------------------
class LogsResponseDTO(BaseModel):
    # key: str         # "date" / "weekStarting" / "month"
    # keyValue: str
    logs: List[LogItemDTO]
