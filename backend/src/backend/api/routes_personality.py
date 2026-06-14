from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import Transaction, User
from backend.schemas.personality import (
    PersonalityProfile,
    PersonalityResponse,
    QuizQuestion,
    QuizResultResponse,
    QuizSubmitRequest,
)
from backend.services.personality import (
    QUIZ_QUESTIONS,
    compute_financial_health,
    compute_personality_profile,
    compute_quiz_result,
)

router = APIRouter()


@router.get("/profile", response_model=PersonalityResponse)
def get_profile(
    organization_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> PersonalityResponse:
    if organization_id is not None:
        from backend.services.organizations import get_member_user_ids, verify_org_membership
        try:
            verify_org_membership(db, organization_id, current_user.id)
        except ValueError:
            raise HTTPException(status_code=403, detail="not a member of this organization")
        user_ids = get_member_user_ids(db, organization_id)
    else:
        user_ids = [current_user.id]

    profile_data = compute_personality_profile(db, user_ids)
    health_data = compute_financial_health(db, user_ids)
    has_data = db.scalar(
        select(Transaction.id).where(Transaction.user_id.in_(user_ids)).limit(1)
    ) is not None

    return PersonalityResponse(
        personality=PersonalityProfile(**profile_data),
        financial_health=health_data,
        has_data=has_data,
    )


@router.get("/quiz", response_model=list[QuizQuestion])
def get_quiz() -> list[QuizQuestion]:
    return [QuizQuestion(**q) for q in QUIZ_QUESTIONS]


@router.post("/quiz/result", response_model=QuizResultResponse)
def submit_quiz(
    body: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> QuizResultResponse:
    if len(body.answers) != len(QUIZ_QUESTIONS):
        raise HTTPException(
            status_code=422,
            detail=f"需要恰好 {len(QUIZ_QUESTIONS)} 个答案，收到了 {len(body.answers)} 个",
        )
    for i, answer in enumerate(body.answers):
        if answer < 1 or answer > 4:
            raise HTTPException(
                status_code=422,
                detail=f"第 {i + 1} 题的答案必须在 1-4 之间，收到 {answer}",
            )

    profile_data = compute_personality_profile(db, [current_user.id])
    data_dimensions = profile_data["dimensions"]

    quiz_result = compute_quiz_result(body.answers, data_dimensions)

    return QuizResultResponse(
        self_assessment=quiz_result["self_assessment"],
        data_profile=PersonalityProfile(**profile_data),
        comparison=quiz_result["comparison"],
    )
