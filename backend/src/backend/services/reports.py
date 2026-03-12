from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models import Category, GeneratedReport, ReportJob, Transaction, UploadedFile


class ReportBuilder:
    def __init__(self) -> None:
        settings.reports_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_unicode_font(self) -> tuple[str, Path]:
        candidates = [
            ("MicrosoftYaHei", Path("C:/Windows/Fonts/msyh.ttc")),
            ("SimHei", Path("C:/Windows/Fonts/simhei.ttf")),
            ("SimSun", Path("C:/Windows/Fonts/simsun.ttc")),
        ]
        for font_name, font_path in candidates:
            if font_path.exists():
                return font_name, font_path
        raise FileNotFoundError("No suitable Unicode font found for PDF report generation")

    def _configure_pdf_font(self, pdf: FPDF) -> str:
        font_name, font_path = self._resolve_unicode_font()
        pdf.add_font(font_name, "", str(font_path))
        pdf.set_font(font_name, size=11)
        pdf.set_auto_page_break(auto=True, margin=15)
        return font_name

    @staticmethod
    def _money(value: Decimal) -> str:
        return f"{value:.2f}"

    @staticmethod
    def _safe_text(value: object) -> str:
        text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
        return text or "-"

    @staticmethod
    def _content_width(pdf: FPDF) -> float:
        return float(pdf.w - pdf.l_margin - pdf.r_margin)

    def _add_cover(self, pdf: FPDF, title: str, subtitle_lines: list[str]) -> None:
        pdf.set_fill_color(30, 58, 95)
        pdf.set_text_color(255, 255, 255)
        pdf.rect(0, 0, 210, 70, style="F")
        pdf.set_font_size(24)
        pdf.set_xy(15, 20)
        pdf.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font_size(11)
        for line in subtitle_lines:
            pdf.set_x(15)
            pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)
        pdf.set_text_color(48, 52, 63)

    def _section_title(self, pdf: FPDF, title: str, subtitle: str | None = None) -> None:
        pdf.ln(4)
        pdf.set_fill_color(239, 245, 252)
        pdf.set_text_color(20, 53, 86)
        pdf.set_font_size(15)
        pdf.cell(0, 10, title, fill=True, new_x="LMARGIN", new_y="NEXT")
        if subtitle:
            pdf.set_text_color(96, 102, 114)
            pdf.set_font_size(9)
            pdf.cell(0, 6, subtitle, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(48, 52, 63)
        pdf.set_font_size(11)

    def _metric_row(self, pdf: FPDF, metrics: list[tuple[str, str]]) -> None:
        col_width = 45
        gap = 5
        start_x = pdf.get_x()
        start_y = pdf.get_y()
        max_height = 0.0
        for index, (label, value) in enumerate(metrics):
            x = start_x + index * (col_width + gap)
            pdf.set_xy(x, start_y)
            pdf.set_fill_color(248, 245, 240)
            pdf.set_draw_color(220, 210, 198)
            pdf.rect(x, start_y, col_width, 24, style="DF")
            pdf.set_xy(x + 3, start_y + 4)
            pdf.set_text_color(126, 103, 79)
            pdf.set_font_size(8)
            pdf.cell(col_width - 6, 5, label, new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(x + 3)
            pdf.set_text_color(36, 40, 47)
            pdf.set_font_size(13)
            pdf.cell(col_width - 6, 8, value, new_x="LMARGIN", new_y="NEXT")
            max_height = max(max_height, 24)
        pdf.set_xy(start_x, start_y + max_height + 3)
        pdf.set_text_color(48, 52, 63)
        pdf.set_font_size(11)

    def _info_block(self, pdf: FPDF, rows: list[tuple[str, str]]) -> None:
        label_width = 32
        value_width = 160
        for label, value in rows:
            pdf.set_fill_color(248, 245, 240)
            pdf.set_text_color(126, 103, 79)
            pdf.cell(label_width, 8, label, fill=True)
            pdf.set_text_color(48, 52, 63)
            pdf.multi_cell(value_width, 8, value)

    def _simple_table(self, pdf: FPDF, headers: list[str], rows: list[list[str]], widths: list[float]) -> None:
        pdf.set_fill_color(234, 240, 246)
        pdf.set_text_color(24, 48, 72)
        pdf.set_font_size(9)
        for header, width in zip(headers, widths):
            pdf.cell(width, 8, header, border=1, fill=True)
        pdf.ln()
        pdf.set_text_color(48, 52, 63)
        for row in rows:
            for cell, width in zip(row, widths):
                pdf.cell(width, 8, self._safe_text(cell)[:32], border=1)
            pdf.ln()
        pdf.set_font_size(11)

    def _group_transactions(
        self,
        transactions: list[Transaction],
        category_lookup: dict[int, str],
    ) -> dict[str, list[Transaction]]:
        grouped: dict[str, list[Transaction]] = defaultdict(list)
        for transaction in transactions:
            resolved_category_id = transaction.final_category_id or transaction.auto_category_id
            category_name = category_lookup.get(resolved_category_id, "未分类")
            grouped[category_name].append(transaction)
        return dict(sorted(grouped.items(), key=lambda item: item[0]))

    def _build_context(
        self,
        db: Session,
        user_id: int,
        report_job: ReportJob,
        uploaded_file_ids: list[int] | None,
    ) -> dict:
        query = select(Transaction).where(Transaction.user_id == user_id)
        if report_job.date_from:
            query = query.where(Transaction.occurred_at >= report_job.date_from)
        if report_job.date_to:
            query = query.where(Transaction.occurred_at <= report_job.date_to)
        if uploaded_file_ids:
            query = query.where(Transaction.uploaded_file_id.in_(uploaded_file_ids))
        transactions = db.scalars(query.order_by(Transaction.occurred_at.asc())).all()

        category_ids = {
            resolved_category_id
            for transaction in transactions
            for resolved_category_id in [transaction.final_category_id or transaction.auto_category_id]
            if resolved_category_id is not None
        }
        category_lookup = (
            {
                category.id: category.name
                for category in db.scalars(select(Category).where(Category.id.in_(category_ids))).all()
            }
            if category_ids
            else {}
        )

        selected_files = (
            db.scalars(
                select(UploadedFile).where(
                    UploadedFile.batch_id.in_(
                        select(Transaction.batch_id).where(Transaction.user_id == user_id)
                    ),
                    UploadedFile.id.in_(uploaded_file_ids),
                )
            ).all()
            if uploaded_file_ids
            else []
        )

        expense_total = sum((transaction.amount for transaction in transactions if transaction.type == "支出"), Decimal("0"))
        income_total = sum((transaction.amount for transaction in transactions if transaction.type == "收入"), Decimal("0"))
        pending_review_count = sum(1 for transaction in transactions if transaction.needs_review)

        category_breakdown: dict[str, dict[str, Decimal | int]] = defaultdict(
            lambda: {"amount": Decimal("0"), "transaction_count": 0}
        )
        merchant_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for transaction in transactions:
            merchant_totals[transaction.merchant or "未知商户"] += transaction.amount
            if transaction.type != "支出":
                continue
            resolved_category_id = transaction.final_category_id or transaction.auto_category_id
            category_name = category_lookup.get(resolved_category_id, "未分类")
            category_breakdown[category_name]["amount"] += transaction.amount
            category_breakdown[category_name]["transaction_count"] += 1

        return {
            "transactions": transactions,
            "category_lookup": category_lookup,
            "grouped_transactions": self._group_transactions(transactions, category_lookup),
            "expense_total": expense_total,
            "income_total": income_total,
            "net_total": income_total - expense_total,
            "pending_review_count": pending_review_count,
            "transaction_count": len(transactions),
            "category_breakdown": sorted(category_breakdown.items(), key=lambda item: item[1]["amount"], reverse=True),
            "top_merchants": sorted(merchant_totals.items(), key=lambda item: item[1], reverse=True)[:10],
            "selected_files": selected_files,
        }

    def build(
        self,
        db: Session,
        user_id: int,
        report_job: ReportJob,
        title: str | None = None,
        uploaded_file_ids: list[int] | None = None,
    ) -> GeneratedReport:
        context = self._build_context(db, user_id, report_job, uploaded_file_ids)

        file_name = f"report-{user_id}-{report_job.id}.pdf"
        file_path = settings.reports_dir / file_name
        pdf = FPDF()
        self._configure_pdf_font(pdf)
        pdf.add_page()

        subtitle_lines = [
            "智能账单分类系统导出报告",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"交易笔数: {context['transaction_count']}",
        ]
        self._add_cover(pdf, title or "账单分析报告", subtitle_lines)

        selected_file_names = [file.filename for file in context["selected_files"]]
        self._section_title(pdf, "筛选范围", "本报告与总览页面使用同一批筛选条件")
        self._info_block(
            pdf,
            [
                ("时间范围", self._safe_text(f"{report_job.date_from or '不限'} 至 {report_job.date_to or '不限'}")),
                ("导入文件", "、".join(selected_file_names) if selected_file_names else "全部导入文件"),
            ],
        )

        self._section_title(pdf, "总览指标", "与 Dashboard 的总览口径保持一致")
        self._metric_row(
            pdf,
            [
                ("总支出", self._money(context["expense_total"])),
                ("总收入", self._money(context["income_total"])),
                ("净流入", self._money(context["net_total"])),
                ("交易笔数", str(context["transaction_count"])),
            ],
        )
        self._metric_row(
            pdf,
            [
                ("待复核", str(context["pending_review_count"])),
                ("分类数", str(len(context["category_breakdown"]))),
                ("Top商户数", str(len(context["top_merchants"]))),
                ("文件数", str(len(selected_file_names)) if uploaded_file_ids else "全部"),
            ],
        )

        self._section_title(pdf, "分类汇总", "按支出分类统计金额与笔数")
        category_rows = [
            [
                category_name,
                self._money(payload["amount"]),
                str(payload["transaction_count"]),
            ]
            for category_name, payload in context["category_breakdown"][:12]
        ] or [["无数据", "-", "-"]]
        self._simple_table(pdf, ["分类", "支出金额", "笔数"], category_rows, [80, 45, 25])

        self._section_title(pdf, "Top 商户", "按金额降序展示前 10 个商户")
        merchant_rows = [
            [merchant, self._money(amount)]
            for merchant, amount in context["top_merchants"]
        ] or [["无数据", "-"]]
        self._simple_table(pdf, ["商户", "金额"], merchant_rows, [120, 30])

        for category_name, items in context["grouped_transactions"].items():
            pdf.add_page()
            self._section_title(pdf, f"{category_name} 明细", f"共 {len(items)} 笔交易，按时间升序排列")
            for transaction in items:
                detail = (
                    f"{transaction.occurred_at:%Y-%m-%d %H:%M} | {transaction.type} | "
                    f"{self._money(transaction.amount)} | {self._safe_text(transaction.merchant)}"
                )
                summary = self._safe_text(transaction.item or transaction.note)
                block_width = self._content_width(pdf)
                pdf.set_x(pdf.l_margin)
                pdf.set_fill_color(250, 248, 244)
                pdf.set_text_color(48, 52, 63)
                pdf.multi_cell(block_width, 7, detail, border=1, fill=True)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(block_width, 7, f"摘要: {summary}", border="LRB")
                pdf.ln(1)

        pdf.output(str(file_path))

        report = GeneratedReport(user_id=user_id, job_id=report_job.id, title=title or "财务报告", file_path=str(file_path))
        db.add(report)
        db.commit()
        db.refresh(report)
        return report
