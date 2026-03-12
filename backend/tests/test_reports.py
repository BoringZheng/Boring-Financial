from __future__ import annotations

import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.base_class import Base
from backend.models import ImportBatch, ReportJob, Transaction, UploadedFile, User
from backend.services import reports as reports_module
from backend.services.reports import ReportBuilder


def test_report_builder_filters_by_uploaded_files(monkeypatch) -> None:
    captured_lines: list[str] = []

    class FakePDF:
        def __init__(self) -> None:
            self.x = 10.0
            self.y = 10.0
            self.w = 210.0
            self.l_margin = 10.0
            self.r_margin = 10.0

        def add_page(self) -> None:
            self.x = 10.0
            self.y = 10.0

        def add_font(self, *_args, **_kwargs) -> None:
            return None

        def set_font(self, *_args, **_kwargs) -> None:
            return None

        def set_font_size(self, *_args, **_kwargs) -> None:
            return None

        def set_auto_page_break(self, *_args, **_kwargs) -> None:
            return None

        def set_fill_color(self, *_args, **_kwargs) -> None:
            return None

        def set_draw_color(self, *_args, **_kwargs) -> None:
            return None

        def set_text_color(self, *_args, **_kwargs) -> None:
            return None

        def rect(self, *_args, **_kwargs) -> None:
            return None

        def get_x(self) -> float:
            return self.x

        def get_y(self) -> float:
            return self.y

        def set_xy(self, x: float, y: float) -> None:
            self.x = x
            self.y = y

        def set_x(self, x: float) -> None:
            self.x = x

        def cell(self, _w, _h, txt="", **_kwargs) -> None:
            captured_lines.append(txt)
            self.y += 1

        def multi_cell(self, _w, _h, txt="", **_kwargs) -> None:
            captured_lines.append(txt)
            self.y += 1

        def ln(self, _h: float = 0) -> None:
            self.y += 1

        def output(self, path: str) -> None:
            with open(path, "wb") as file:
                file.write("\n".join(captured_lines).encode("utf-8"))

    temp_storage_dir = Path.cwd() / ".pytest-report-storage"
    temp_reports_dir = temp_storage_dir / "reports"
    temp_reports_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    db = Session(engine)

    user = User(username="report-user", email="report@example.com", hashed_password="hashed")
    db.add(user)
    db.commit()
    db.refresh(user)

    batch = ImportBatch(user_id=user.id, status="done", source_count=2, total_count=2, processed_count=2)
    db.add(batch)
    db.commit()
    db.refresh(batch)

    file_a = UploadedFile(batch_id=batch.id, filename="a.xlsx", stored_path="a.xlsx", platform="WeChat", status="done")
    file_b = UploadedFile(batch_id=batch.id, filename="b.xlsx", stored_path="b.xlsx", platform="Alipay", status="done")
    db.add_all([file_a, file_b])
    db.commit()
    db.refresh(file_a)
    db.refresh(file_b)

    db.add_all(
        [
            Transaction(
                user_id=user.id,
                batch_id=batch.id,
                uploaded_file_id=file_a.id,
                platform="WeChat",
                occurred_at=datetime(2026, 3, 1, 10, 0, 0),
                type="支出",
                amount=Decimal("12.00"),
                merchant="文件A商户",
                item="午餐",
                method="零钱",
                status="支付成功",
                note="",
                merchant_norm="文件a商户",
                item_norm="午餐",
                note_norm="",
                dedupe_hash="report-a",
            ),
            Transaction(
                user_id=user.id,
                batch_id=batch.id,
                uploaded_file_id=file_b.id,
                platform="Alipay",
                occurred_at=datetime(2026, 3, 1, 11, 0, 0),
                type="支出",
                amount=Decimal("34.00"),
                merchant="文件B商户",
                item="地铁",
                method="银行卡",
                status="支付成功",
                note="",
                merchant_norm="文件b商户",
                item_norm="地铁",
                note_norm="",
                dedupe_hash="report-b",
            ),
        ]
    )
    db.commit()

    report_job = ReportJob(user_id=user.id, status="processing")
    db.add(report_job)
    db.commit()
    db.refresh(report_job)

    report_builder = ReportBuilder()
    monkeypatch.setattr(reports_module, "FPDF", FakePDF)

    from backend.core.config import settings

    monkeypatch.setattr(settings, "storage_dir", "./.pytest-report-storage")

    try:
        report = report_builder.build(
            db,
            user.id,
            report_job,
            title="筛选报表",
            uploaded_file_ids=[file_a.id],
        )

        report_text = (temp_reports_dir / f"report-{user.id}-{report_job.id}.pdf").read_text(encoding="utf-8")
        assert report.id is not None
        assert "交易笔数: 1" in report_text
        assert "文件A商户" in report_text
        assert "文件B商户" not in report_text
        assert "总览指标" in report_text
        assert "分类汇总" in report_text
    finally:
        shutil.rmtree(temp_storage_dir, ignore_errors=True)
