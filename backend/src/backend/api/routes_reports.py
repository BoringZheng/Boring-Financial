from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import GeneratedReport, ReportJob, User
from backend.schemas.reports import ReportCreateRequest, ReportRead
from backend.services.reports import ReportBuilder

router = APIRouter()
report_builder = ReportBuilder()


@router.post("", response_model=ReportRead)
def create_report(
    payload: ReportCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ReportRead:
    job = ReportJob(user_id=current_user.id, status="processing", date_from=payload.date_from, date_to=payload.date_to)
    db.add(job)
    db.commit()
    db.refresh(job)
    report = report_builder.build(
        db,
        current_user.id,
        job,
        payload.title,
        uploaded_file_ids=payload.uploaded_file_ids,
    )
    job.status = "done"
    db.commit()
    return ReportRead.model_validate(report)


@router.get("/{report_id}/download")
def download_report(report_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db_session)):
    report = db.get(GeneratedReport, report_id)
    if report is None or report.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="report not found")
    return FileResponse(report.file_path, filename=f"report-{report.id}.pdf", media_type="application/pdf")
