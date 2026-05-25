from __future__ import annotations

from backend.services.parsers import ParserRegistry


def test_parse_gbk_alipay_csv_with_preamble_and_generic_filename(tmp_path):
    csv_text = "\n".join(
        [
            "------------------------------------------------------------------------------------",
            "导出信息：",
            "支付宝交易明细",
            "导出时间,2026-05-25",
            "",
            "特别提示：",
            "1.本明细仅供个人对账使用。",
            "",
            "交易时间,交易分类,交易对方,商品说明,收/支,金额（元）,交易状态,支付方式,备注",
            "2026-04-01 10:00:00,餐饮,测试商户,午餐,支出,12.50,交易成功,余额,",
        ]
    )
    statement_path = tmp_path / "statement.csv"
    statement_path.write_bytes(csv_text.encode("gbk"))

    transactions = ParserRegistry().parse_file(statement_path)

    assert len(transactions) == 1
    assert transactions[0].platform == "Alipay"
    assert transactions[0].merchant == "测试商户"
