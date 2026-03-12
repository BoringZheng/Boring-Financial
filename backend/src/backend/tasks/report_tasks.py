from __future__ import annotations

from backend.core.celery_app import celery_app
from backend.db.session import SessionLocal
from backend.models import ReportJob
from backend.services.reports import ReportBuilder


@celery_app.task(name="reports.build")
def build_report(user_id: int, report_job_id: int, title: str | None = None) -> dict:
    db = SessionLocal()
    try:
        report_job = db.get(ReportJob, report_job_id)
        if report_job is None:
            return {"status": "missing"}
        report = ReportBuilder().build(db, user_id, report_job, title)
        report_job.status = "done"
        db.commit()
        return {"report_id": report.id, "status": "done"}
    finally:
        db.close()
