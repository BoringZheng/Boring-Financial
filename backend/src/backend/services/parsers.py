from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pandas as pd

from backend.utils.normalizers import clean_amount, normalize_text, parse_datetime


@dataclass
class ParsedTransaction:
    platform: str
    occurred_at: object
    type: str
    amount: Decimal
    merchant: str | None
    item: str | None
    method: str | None
    status: str | None
    note: str | None


class StatementReader:
    def read(self, path: Path) -> pd.DataFrame:
        lower = str(path).lower()
        if lower.endswith((".xls", ".xlsx")):
            return self._read_excel(path)
        return self._read_csv(path)

    def _read_excel(self, path: Path) -> pd.DataFrame:
        df = pd.read_excel(path)
        if self._looks_like_statement(df):
            return df

        header_row = self._detect_header_row_excel(path)
        if header_row is not None:
            return pd.read_excel(path, header=header_row)

        for skiprows in [1, 2, 3, 4, 5, 10, 15, 16, 20]:
            try:
                df2 = pd.read_excel(path, skiprows=skiprows)
                if self._looks_like_statement(df2):
                    return df2
            except Exception:
                continue
        return df

    def _read_csv(self, path: Path) -> pd.DataFrame:
        for encoding in ["utf-8-sig", "utf-8", "gbk", "gb18030", "cp936", "latin1"]:
            try:
                df = pd.read_csv(path, encoding=encoding)
                if self._looks_like_statement(df):
                    return df
                header_row = self._detect_header_row_csv(path, encoding)
                if header_row is not None:
                    return pd.read_csv(path, encoding=encoding, header=header_row)
                for skiprows in [1, 2, 3, 4, 5, 10, 15, 16, 20]:
                    try:
                        df2 = pd.read_csv(path, encoding=encoding, skiprows=skiprows)
                        if self._looks_like_statement(df2):
                            return df2
                    except Exception:
                        continue
            except Exception:
                continue
        return pd.read_csv(path)

    def _looks_like_statement(self, df: pd.DataFrame) -> bool:
        columns = [str(column) for column in df.columns]
        return any("交易" in column or "时间" in column for column in columns)

    def _detect_header_row_excel(self, path: Path, scan_rows: int = 40) -> int | None:
        sample = pd.read_excel(path, header=None, nrows=scan_rows)
        return self._find_header_row(sample)

    def _detect_header_row_csv(self, path: Path, encoding: str, scan_rows: int = 40) -> int | None:
        sample = pd.read_csv(path, encoding=encoding, header=None, nrows=scan_rows, on_bad_lines="skip")
        return self._find_header_row(sample)

    def _find_header_row(self, sample: pd.DataFrame) -> int | None:
        for row_index, row in sample.iterrows():
            values = [str(value).strip() for value in row.tolist() if not pd.isna(value)]
            if not values:
                continue
            has_time = any("交易时间" in value or value == "时间" or "支付时间" in value for value in values)
            has_amount = any("金额" in value for value in values)
            has_direction = any(value in {"收/支", "收支"} for value in values)
            if has_time and has_amount and (has_direction or any("交易类型" in value for value in values)):
                return int(row_index)
        return None


class AlipayParser:
    def parse(self, df: pd.DataFrame) -> list[ParsedTransaction] | None:
        columns = {str(column).strip(): column for column in df.columns}
        c_time = next((columns.get(key) for key in ["交易时间", "时间", "创建时间", "支付时间"] if key in columns), None)
        c_io = next((columns.get(key) for key in ["收/支", "收支", "收支类型"] if key in columns), None)
        c_amount = next((columns.get(key) for key in ["金额（元）", "金额(元)", "金额", "交易金额"] if key in columns), None)
        c_merchant = next((columns.get(key) for key in ["交易对方", "对方", "商家", "商户名称"] if key in columns), None)
        c_item = next((columns.get(key) for key in ["商品说明", "商品", "商品名称", "标题", "事由"] if key in columns), None)
        c_status = next((columns.get(key) for key in ["交易状态", "状态"] if key in columns), None)
        c_method = next((columns.get(key) for key in ["支付方式", "付款方式", "资金渠道"] if key in columns), None)
        c_note = next((columns.get(key) for key in ["备注", "用户备注", "附言"] if key in columns), None)
        if not (c_time and c_amount):
            return None

        rows: list[ParsedTransaction] = []
        for _, record in df.dropna(how="all").iterrows():
            occurred_at = parse_datetime(record.get(c_time))
            amount = clean_amount(record.get(c_amount))
            if occurred_at is None or amount is None:
                continue
            io_value = str(record.get(c_io, "")).strip()
            transaction_type = "支出" if io_value in {"支出", "转出"} else "收入" if io_value in {"收入", "转入"} else "支出"
            rows.append(
                ParsedTransaction(
                    platform="Alipay",
                    occurred_at=occurred_at,
                    type=transaction_type,
                    amount=abs(amount),
                    merchant=record.get(c_merchant, ""),
                    item=record.get(c_item, ""),
                    method=record.get(c_method, ""),
                    status=record.get(c_status, ""),
                    note=record.get(c_note, ""),
                )
            )
        return rows


class WeChatParser:
    def parse(self, df: pd.DataFrame) -> list[ParsedTransaction] | None:
        columns = {str(column).strip(): column for column in df.columns}
        c_time = next((columns.get(key) for key in ["交易时间", "时间", "支付时间"] if key in columns), None)
        c_type = next((columns.get(key) for key in ["交易类型", "类型"] if key in columns), None)
        c_amount = next((columns.get(key) for key in ["金额(元)", "金额（元）", "金额", "交易金额(元)"] if key in columns), None)
        c_io = next((columns.get(key) for key in ["收/支", "收支"] if key in columns), None)
        c_merchant = next((columns.get(key) for key in ["交易对方", "商户名称", "付款方"] if key in columns), None)
        c_item = next((columns.get(key) for key in ["商品", "商品说明", "商品名称"] if key in columns), None)
        c_status = next((columns.get(key) for key in ["当前状态", "交易状态", "状态"] if key in columns), None)
        c_method = next((columns.get(key) for key in ["支付方式", "付款方式", "资金渠道"] if key in columns), None)
        c_note = next((columns.get(key) for key in ["备注", "用户备注", "附言"] if key in columns), None)
        if not (c_time and c_amount):
            return None

        rows: list[ParsedTransaction] = []
        for _, record in df.dropna(how="all").iterrows():
            occurred_at = parse_datetime(record.get(c_time))
            amount = clean_amount(record.get(c_amount))
            if occurred_at is None or amount is None:
                continue
            io_value = str(record.get(c_io, "")).strip()
            type_guess = str(record.get(c_type, "")).strip()
            if io_value == "支出":
                transaction_type = "支出"
            elif io_value == "收入":
                transaction_type = "收入"
            elif any(token in type_guess for token in ["退款", "转入", "收入"]):
                transaction_type = "收入"
            else:
                transaction_type = "支出"
            rows.append(
                ParsedTransaction(
                    platform="WeChat",
                    occurred_at=occurred_at,
                    type=transaction_type,
                    amount=abs(amount),
                    merchant=record.get(c_merchant, ""),
                    item=record.get(c_item, ""),
                    method=record.get(c_method, ""),
                    status=record.get(c_status, ""),
                    note=record.get(c_note, ""),
                )
            )
        return rows


class TransactionNormalizer:
    @staticmethod
    def normalize_text_fields(transaction: ParsedTransaction) -> dict:
        return {
            "merchant_norm": normalize_text(transaction.merchant),
            "item_norm": normalize_text(transaction.item),
            "note_norm": normalize_text(transaction.note),
        }


class ParserRegistry:
    def __init__(self) -> None:
        self.reader = StatementReader()
        self.alipay_parser = AlipayParser()
        self.wechat_parser = WeChatParser()

    def parse_file(self, path: str | Path) -> list[ParsedTransaction]:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(os.fspath(file_path))
        raw_df = self.reader.read(file_path)
        parsers = self._ordered_parsers(file_path)
        for parser in parsers:
            parsed = parser.parse(raw_df)
            if parsed is not None:
                return parsed
        raise ValueError(f"Unrecognized statement format: {file_path.name}")

    def _ordered_parsers(self, file_path: Path):
        hint = self._detect_platform_hint(file_path)
        if hint == "wechat":
            return [self.wechat_parser, self.alipay_parser]
        if hint == "alipay":
            return [self.alipay_parser, self.wechat_parser]
        return [self.wechat_parser, self.alipay_parser]

    def _detect_platform_hint(self, file_path: Path) -> str | None:
        filename = file_path.name.lower()
        if "微信" in file_path.name or "wechat" in filename:
            return "wechat"
        if "支付宝" in file_path.name or "alipay" in filename:
            return "alipay"

        try:
            if str(file_path).lower().endswith((".xls", ".xlsx")):
                preview = pd.read_excel(file_path, header=None, nrows=5)
            else:
                preview = pd.read_csv(file_path, header=None, nrows=5, encoding="utf-8-sig")
            text = " ".join(str(value) for value in preview.fillna("").to_numpy().flatten())
            if "微信支付账单明细" in text:
                return "wechat"
            if "支付宝" in text:
                return "alipay"
        except Exception:
            return None
        return None
