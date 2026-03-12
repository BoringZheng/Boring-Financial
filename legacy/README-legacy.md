# Legacy Usage

这里保留旧版单体脚本工具的参考说明，供回溯原始实现和对比重构前后的演进思路使用。

## 旧版入口

- `merge_bills.py`
- `generate_report.py`
- `oneclick_bills.py`

## 旧版流程

1. 手动下载微信/支付宝账单并放入 `input/`
2. 按旧脚本要求清理表头
3. 调整 `category_map.csv`
4. 运行 `merge_bills.py`
5. 运行 `generate_report.py` 或 `oneclick_bills.py`

## 说明

- 旧版实现仍可作为账单解析、规则匹配和 PDF 输出逻辑的迁移参考
- 新系统开发请以 `backend/`、`frontend/`、`infra/` 和 `docs/` 为准
