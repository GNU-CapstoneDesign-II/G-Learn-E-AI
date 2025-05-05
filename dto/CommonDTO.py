# dto/CommonDTO.py
from pydantic import BaseModel
from typing import List


# DTO
class PromptRequest(BaseModel):
    prompt: str


class MultipleChoiceItem(BaseModel):
    enable: bool  # 객관식 문제 사용 여부
    numQuestions: int  # 문제 개수
    numOptions: int  # 선택지 개수


class OxItem(BaseModel):
    enable: bool  # OX 문제 사용 여부
    numQuestions: int  # 문제 개수


class FillInTheBlankItem(BaseModel):
    enable: bool  # 빈칸 채우기 문제 사용 여부
    numQuestions: int  # 문제 개수


class DescriptiveItem(BaseModel):
    enable: bool  # 서술형 문제 사용 여부
    numQuestions: int  # 문제 개수


class QuestionTypes(BaseModel):
    multipleChoice: MultipleChoiceItem  # 객관식 문제 설정
    ox: OxItem  # OX 문제 설정
    fillInTheBlank: FillInTheBlankItem  # 빈칸 채우기 문제 설정
    descriptive: DescriptiveItem  # 서술형 문제 설정


class MakeProblemRequest(BaseModel):
    content: str
    difficulty: str
    questionTypes: QuestionTypes


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
