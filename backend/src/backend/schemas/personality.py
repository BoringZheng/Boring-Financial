from __future__ import annotations

from pydantic import BaseModel


class DimensionScore(BaseModel):
    name: str
    value: float
    side: str
    label: str
    theory_ref: str
    interpretation: str


class PersonalityProfile(BaseModel):
    code: str
    name: str
    tagline: str
    quote: str
    match_percent: float
    secondary_code: str
    secondary_name: str
    dimensions: list[DimensionScore]


class HealthDimension(BaseModel):
    name: str
    value: float
    label: str


class FinancialHealth(BaseModel):
    total_score: float
    grade: str
    dimensions: list[HealthDimension]
    suggestions: list[str]


class PersonalityResponse(BaseModel):
    personality: PersonalityProfile
    financial_health: FinancialHealth
    has_data: bool


class QuizOption(BaseModel):
    value: int
    text: str


class QuizQuestion(BaseModel):
    id: int
    dimension: str
    text: str
    options: list[QuizOption]


class QuizSubmitRequest(BaseModel):
    answers: list[int]


class BiggestGap(BaseModel):
    dimension: str
    self_score: float
    data_score: float
    gap: float
    analysis: str
    theory_ref: str


class QuizComparison(BaseModel):
    cosine_similarity: float
    biggest_gap: BiggestGap
    bias_analysis: str


class QuizSelfAssessment(BaseModel):
    dimensions: dict[str, float]


class QuizResultResponse(BaseModel):
    self_assessment: QuizSelfAssessment
    data_profile: PersonalityProfile
    comparison: QuizComparison
