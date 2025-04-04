# dto/CommonDTO.py
from pydantic import BaseModel
from typing import List


class GradeItem(BaseModel):
    id: int
    question: str
    answer: str
    input: str


class GradeRequestDTO(BaseModel):
    items: List[GradeItem]


class GradeResult(BaseModel):
    id: int
    correct: bool


class BlankItem(BaseModel):
    id: int
    question: str
    answer: List[str]  # 정답은 리스트로 제공 (예: ["시험"])
    input: List[str]  # 학생이 작성한 답안


class BlankRequestDTO(BaseModel):
    items: List[BlankItem]


class BlankResult(BaseModel):
    id: int
    correct: bool  # 최종 판정: 정답이면 true, 오답이면 false
