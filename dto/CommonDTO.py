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
