# generate_report.py
# -*- coding: utf-8 -*-
"""
读取 merged.csv，输出 financial_report.pdf（最近12个月，按“近→远”）
包含：每月 KPI、支出分类、Top 商家（支出）、大额支出明细。
依赖：pandas, fpdf2
"""

import os
from datetime import datetime
import pandas as pd
from fpdf import FPDF, XPos, YPos

# ========= 可调参数 =========
CSV_PATH      = ".\output\merged.csv"             # 账单合并CSV
OUTPUT_PDF    = "financial_report.pdf"   # 输出PDF文件名
MONTHS_BACK   = 12                       # 本月起往前N个月（含本月）
TOP_MERCHANTS = 10                       # 每月Top商家条数（支出）
BIG_TOP       = 10                       # 每月大额支出条数
BIG_MIN       = 0                        # 大额支出金额门槛（0表示不限）
CURRENCY      = "¥"                      # 金额符号

# 常见中文字体候选（按顺序尝试，找到即用；可把字体放到 ./fonts/ 下）
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",            # 微软雅黑
    r"C:\Windows\Fonts\simhei.ttf",          # 黑体
    r"./fonts/msyh.ttf",
    r"./fonts/simhei.ttf",
    r"./fonts/NotoSansSC-Regular.otf",
]
FONT_FAMILY_NAME = "CJK"  # 在PDF中注册后的统一字体名
# ==========================


def pick_font_path() -> str:
    """从候选列表里找一个可用的中文字体路径。"""
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return ""


class ReportPDF(FPDF):
    """封装一些常用样式的 FPDF 子类。统一使用注册的 CJK 字体。"""
    def __init__(self, font_path: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=12)
        self.font_path = font_path
        if font_path:
            self.add_font(FONT_FAMILY_NAME, "", font_path, uni=True)
            self.add_font(FONT_FAMILY_NAME, "B", font_path, uni=True)
            self.set_font(FONT_FAMILY_NAME, "", 12)
        else:
            # 若未找到中文字体：仍设英文字体，但中文将无法渲染（建议提供字体）
            self.set_font("Helvetica", "", 12)

    @property
    def epw(self) -> float:
        """有效页面宽度（去掉左右边距）。"""
        return self.w - self.l_margin - self.r_margin

    def h1(self, text: str):
        self.set_font(FONT_FAMILY_NAME, "B", 18)
        self.cell(0, 10, txt=text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.ln(2)
        self.set_font(FONT_FAMILY_NAME, "", 12)

    def h2(self, text: str):
        self.set_font(FONT_FAMILY_NAME, "B", 15)
        self.cell(0, 9, txt=text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font(FONT_FAMILY_NAME, "", 12)

    def h3(self, text: str):
        self.set_font(FONT_FAMILY_NAME, "B", 13)
        self.cell(0, 8, txt=text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font(FONT_FAMILY_NAME, "", 12)

    def table(self, title: str, data: list[list], headers: list[str], col_widths: list[float] | None = None):
        """简单表格（不自动换行，长文本会截断以避免溢出）。"""
        if title:
            self.set_font(FONT_FAMILY_NAME, "B", 12)
            self.cell(0, 7, txt=title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_font(FONT_FAMILY_NAME, "", 12)

        if col_widths is None:
            col_widths = [self.epw / len(headers)] * len(headers)

        # 表头
        self.set_fill_color(230, 230, 230)
        for w, h in zip(col_widths, headers):
            self.cell(w, 8, txt=str(h), border=1, fill=True)
        self.ln(8)

        # 表体
        for row in data:
            for w, cell in zip(col_widths, row):
                text = str(cell)
                # 简单截断（更精细可用 string_width 测宽）
                max_chars = max(1, int(w / 3.0))
                if len(text) > max_chars:
                    text = text[:max_chars - 1] + "…"
                self.cell(w, 8, txt=text, border=1)
            self.ln(8)
        self.ln(2)


def fmt_money(x: float) -> str:
    return f"{CURRENCY}{(round(float(x) * 100) / 100):.2f}"


def load_data(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"未找到文件：{path}")
    df = pd.read_csv(path, encoding="utf-8-sig", parse_dates=["date"])
    # 清洗列名 & 校验
    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]
    need = ["date","type","category","subcategory","amount","platform","merchant","item","method","status","note"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise ValueError(f"缺少列：{', '.join(miss)}")
    # 只保留有效行
    df = df.dropna(subset=["date", "amount"]).copy()
    df["month"] = df["date"].dt.to_period("M")
    return df


def month_periods_recent(n: int) -> list[pd.Period]:
    """返回 [本月, 上月, …] 共 n 个 Period('M')，用于“近→远”顺序输出。"""
    now = pd.Period(datetime.now(), freq="M")
    return [now - i for i in range(n)]


def add_month_section(pdf: ReportPDF, df: pd.DataFrame, period_m: pd.Period):
    dfm = df[df["month"] == period_m]
    if dfm.empty:
        return

    # 标题：YYYY-MM
    pdf.h2(str(period_m))

    exp = dfm[dfm["type"].astype(str).str.contains("支出", na=False)]
    inc = dfm[dfm["type"].astype(str).str.contains("收入", na=False)]

    exp_total = float(exp["amount"].sum())
    inc_total = float(inc["amount"].sum())
    net_total = inc_total - exp_total

    # KPI
    pdf.table(
        title="KPI",
        headers=["指标", "金额"],
        data=[
            ["支出", fmt_money(exp_total)],
            ["收入", fmt_money(inc_total)],
            ["净流", fmt_money(net_total)],
        ],
        col_widths=[pdf.epw * 0.35, pdf.epw * 0.65],
    )

    # 支出分类
    pdf.h3("支出分类")
    if not exp.empty:
        cats = (exp.groupby("category")["amount"]
                  .sum()
                  .sort_values(ascending=False))
        cat_rows = [[k, fmt_money(v)] for k, v in cats.items()]
        pdf.table(
            title="",
            headers=["分类", "金额"],
            data=cat_rows,
            col_widths=[pdf.epw * 0.55, pdf.epw * 0.45],
        )
    else:
        pdf.cell(0, 6, txt="本月无支出数据", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Top 商家（支出）
    pdf.h3(f"Top 商家（支出，前 {TOP_MERCHANTS}）")
    if not exp.empty:
        merchants = (exp.groupby("merchant")["amount"]
                       .sum()
                       .sort_values(ascending=False)
                       .head(TOP_MERCHANTS))
        mer_rows = [[k, fmt_money(v)] for k, v in merchants.items()]
        pdf.table(
            title="",
            headers=["商家", "金额"],
            data=mer_rows,
            col_widths=[pdf.epw * 0.7, pdf.epw * 0.3],
        )
    else:
        pdf.cell(0, 6, txt="本月无支出商家", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # 大额支出
    pdf.h3(f"大额支出（Top {BIG_TOP}" + (f"，门槛≥{fmt_money(BIG_MIN)}" if BIG_MIN>0 else "") + "）")
    if not exp.empty:
        big_df = exp.copy()
        if BIG_MIN > 0:
            big_df = big_df[big_df["amount"] >= BIG_MIN]
        big_df = big_df.sort_values("amount", ascending=False).head(BIG_TOP)

        big_rows = []
        for _, r in big_df.iterrows():
            dstr = pd.Timestamp(r["date"]).strftime("%Y-%m-%d")
            big_rows.append([dstr, str(r["merchant"]), str(r.get("item") or r.get("note") or ""), fmt_money(r["amount"]), str(r["category"])])

        pdf.table(
            title="",
            headers=["日期", "商家", "摘要", "金额", "分类"],
            data=big_rows,
            col_widths=[pdf.epw*0.18, pdf.epw*0.28, pdf.epw*0.30, pdf.epw*0.14, pdf.epw*0.10],
        )
    else:
        pdf.cell(0, 6, txt="无大额支出", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # 分隔线
    pdf.ln(2)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)


def main():
    df = load_data(CSV_PATH)

    # 创建PDF + 字体
    font_path = pick_font_path()
    if not font_path:
        print("⚠️ 未找到中文字体，将尝试使用内置字体（中文将无法渲染，建议把 msyh.ttc 或 simhei.ttf 放到 ./fonts/ 并重跑）。")
    pdf = ReportPDF(font_path)
    pdf.add_page()

    # 封面 & 总览
    pdf.h1("年度财务总览（最近12个月）")
    date_min = df["date"].min().strftime("%Y-%m-%d")
    date_max = df["date"].max().strftime("%Y-%m-%d")
    pdf.cell(0, 8, txt=f"数据区间：{date_min} 至 {date_max}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # 12个月累计 KPI
    exp_all = float(df[df["type"].astype(str).str.contains("支出", na=False)]["amount"].sum())
    inc_all = float(df[df["type"].astype(str).str.contains("收入", na=False)]["amount"].sum())
    pdf.table(
        title="12个月累计 KPI",
        headers=["指标", "金额"],
        data=[
            ["累计支出", fmt_money(exp_all)],
            ["累计收入", fmt_money(inc_all)],
            ["累计净流", fmt_money(inc_all - exp_all)],
        ],
        col_widths=[pdf.epw * 0.35, pdf.epw * 0.65],
    )

    # 最近12个月（近→远）
    months = month_periods_recent(MONTHS_BACK)
    for m in months:
        add_month_section(pdf, df, m)

    pdf.output(OUTPUT_PDF)
    print(f"✅ 报告已生成：{OUTPUT_PDF}")


if __name__ == "__main__":
    main()
