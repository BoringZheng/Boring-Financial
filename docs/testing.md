# 测试文档

## 1. 测试目标

验证系统在课程交付范围内的关键闭环：

- 账单解析正确
- 自动分类可工作
- 多用户隔离有效
- 统计与报表口径一致
- provider 可从外部 API 切到本地模型

## 2. 当前测试组成

### 单元测试

- `test_security.py`: 密码哈希与 token 编解码
- `test_normalizers.py`: 文本规范化与哈希稳定性

### 手工联调建议

1. 注册新用户
2. 上传微信与支付宝账单
3. 检查导入批次状态是否为 `done` 或 `partial_failed`
4. 进入交易列表查看自动分类来源
5. 进入分类校正页面对低置信度交易重分类
6. 生成 PDF 报表并下载
7. 切换 `provider=local_model` 验证接口兼容性

## 3. 测试数据

当前仓库已有 `input/` 目录下的示例账单，可用于本地联调。

后续建议新增：

- `tests/fixtures/wechat.csv`
- `tests/fixtures/alipay.xlsx`
- `tests/fixtures/expected_transactions.json`

## 4. 评测集说明

为了比较规则版、API 版和本地模型版，建议建立小型人工标注集，字段至少包含：

- `platform`
- `merchant`
- `item`
- `note`
- `amount`
- `expected_category`
- `expected_subcategory`

建议规模：100 到 300 条。

## 5. 指标记录格式

建议在答辩前输出一张对比表：

| 方案 | Accuracy | Macro-F1 | 平均耗时 | 人工修正率 |
| --- | --- | --- | --- | --- |
| Rule | - | - | - | - |
| Composite + API | - | - | - | - |
| Local Model | - | - | - | - |

## 6. 后续自动化方向

- 为解析器增加 fixture 测试
- 为导入接口增加 API 测试
- 为分类器 provider 增加 mock HTTP 测试
- 为 Dashboard 聚合增加断言测试
- 为报表生成增加快照测试
