from __future__ import annotations

from decimal import Decimal

import pytest

from backend.services.parsers import ParserRegistry


def test_wechat_csv_parses_common_columns_and_direction(tmp_path) -> None:
    statement = tmp_path / "wechat.csv"
    statement.write_text(
        "\ufeff交易时间,交易类型,交易对方,商品,收/支,金额(元),支付方式,当前状态,备注\n"
        "2026-03-01 10:00:00,商户消费,瑞幸咖啡,生椰拿铁,支出,¥18.50,零钱,支付成功,上午加班\n"
        "2026-03-01 11:00:00,退款,瑞幸咖啡,退款,收入,(3.50),零钱,已退款,\n",
        encoding="utf-8",
    )

    parsed = ParserRegistry().parse_file(statement)

    assert len(parsed) == 2
    assert parsed[0].platform == "WeChat"
    assert parsed[0].type == "支出"
    assert parsed[0].amount == Decimal("18.50")
    assert parsed[0].merchant == "瑞幸咖啡"
    assert parsed[1].type == "收入"
    assert parsed[1].amount == Decimal("3.50")


def test_alipay_csv_parses_common_columns_and_direction(tmp_path) -> None:
    statement = tmp_path / "alipay.csv"
    statement.write_text(
        "交易时间,交易对方,商品说明,收/支,金额（元）,支付方式,交易状态,备注\n"
        "2026/03/02 09:30:00,早餐店,早餐,支出,12.00,余额宝,交易成功,\n"
        "2026/03/02 18:30:00,公司,报销,收入,+100.00,余额,交易成功,餐补\n",
        encoding="utf-8",
    )

    parsed = ParserRegistry().parse_file(statement)

    assert len(parsed) == 2
    assert parsed[0].platform == "Alipay"
    assert parsed[0].type == "支出"
    assert parsed[0].amount == Decimal("12.00")
    assert parsed[1].type == "收入"
    assert parsed[1].amount == Decimal("100.00")


def test_csv_header_row_is_detected_after_preface(tmp_path) -> None:
    statement = tmp_path / "wechat-preface.csv"
    statement.write_text(
        "微信支付账单明细,,,,,,,\n"
        "导出时间,2026-03-03,,,,,,\n"
        "交易时间,交易类型,交易对方,商品,收/支,金额(元),支付方式,当前状态\n"
        "2026-03-03 12:00:00,商户消费,便利店,矿泉水,支出,2.50,零钱,支付成功\n",
        encoding="utf-8",
    )

    parsed = ParserRegistry().parse_file(statement)

    assert len(parsed) == 1
    assert parsed[0].platform == "WeChat"
    assert parsed[0].merchant == "便利店"


def test_unrecognized_statement_raises_value_error(tmp_path) -> None:
    statement = tmp_path / "unknown.csv"
    statement.write_text("foo,bar\n1,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unrecognized statement format"):
        ParserRegistry().parse_file(statement)
