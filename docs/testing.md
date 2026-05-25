# 测试文档

## 1. 测试目标

验证系统在课程交付范围内的关键闭环：

- 用户注册、登录和资源隔离有效。
- 微信/支付宝账单可以导入、解析、去重和分类。
- 自动分类、重分类、人工校正链路可工作。
- Dashboard 聚合和 PDF 报表口径一致。
- 前端重设计后所有主要页面可访问、无乱码、无明显布局错误。
- provider 可从规则/外部 API 切换到本地模型服务。
- 外部模型请求会进入统一 `retry_queue`，后台 worker 串行处理；超时耗尽后应显示为 `retry_failed`，不应批量进入人工校正。

## 2. 自动化测试

后端测试位于 `backend/tests`。

当前测试文件：

- `test_security.py`: 密码哈希、token 编解码。
- `test_normalizers.py`: 文本规范化和哈希稳定性。
- `test_classifiers.py`: 分类器行为。
- `test_imports.py`: 导入服务。
- `test_analytics.py`: Dashboard 聚合。
- `test_reports.py`: PDF 报表生成。

运行方式：

```bash
cd backend
uv run pytest
```

如需覆盖率：

```bash
uv run pytest --cov=backend
```

## 3. 前端构建测试

前端当前使用 TypeScript + Vue 模板类型检查。

```bash
cd frontend
npm.cmd run build
```

非 Windows 环境：

```bash
npm run build
```

构建通过表示：

- `vue-tsc --noEmit` 类型检查通过。
- Vite 能正常构建生产静态资源。
- 主要模板语法没有明显错误。

如果 Vite 提示 chunk 超过 500 KB，通常来自 Element Plus 和 ECharts，不影响课程 demo。后续生产优化可考虑路由级 code splitting。

## 4. 手工联调流程

建议按以下顺序完成一次完整 demo 验证：

1. 启动后端和前端。
2. 注册新用户并登录。
3. 进入导入账单页，上传微信或支付宝账单。
4. 检查最近导入结果和批次进度。
5. 进入 Dashboard，检查收入、支出、储蓄率、分类图和导入任务状态。
6. 进入交易列表，按日期、平台、分类、导入文件和关键词筛选。
7. 打开交易详情抽屉，检查分类来源、置信度和分类理由。
8. 进入分类校正工作台，确认一笔待校正交易。
9. 进入分类管理，新增一个用户自定义分类。
10. 进入报表中心，选择日期和导入文件，生成并下载 PDF。
11. 进入系统设置，确认 provider 和阈值配置展示正常。
12. 使用管理员账号进入系统设置，确认“一键重试历史超时”按钮可见；普通用户不可见。

## 5. 前端视觉验收

重设计后的前端应满足：

- 页面无可见中文乱码。
- 左侧深色导航和顶部栏在桌面视口稳定显示。
- 窄屏下导航和内容不会明显重叠。
- 表格、筛选栏、按钮和标签文本不溢出。
- Dashboard 和报表图表可渲染。
- 主要 loading、empty、error 状态有明确反馈。

建议检查视口：

- 桌面投屏：`1440 x 900`
- 笔记本：`1280 x 720`
- 窄屏：`390 x 844`

## 6. 测试数据

仓库已有 `input/` 目录下的示例账单，可用于本地联调。

后续建议新增稳定 fixture：

- `tests/fixtures/wechat.csv`
- `tests/fixtures/alipay.xlsx`
- `tests/fixtures/expected_transactions.json`

## 7. 分类评测建议

为了比较规则版、API 版和本地模型版，建议建立小型人工标注集。

字段建议：

- `platform`
- `merchant`
- `item`
- `note`
- `amount`
- `expected_category`
- `expected_subcategory`

建议规模：100 到 300 条。

记录指标：

| 方案 | Accuracy | Macro-F1 | 平均耗时 | 人工修正率 |
| --- | --- | --- | --- | --- |
| Rule | - | - | - | - |
| Composite + API | - | - | - | - |
| Local Model | - | - | - | - |

## 8. 后续自动化方向

- 为认证、导入、交易、分类和报表接口增加 API 测试。
- 为前端增加 Playwright 端到端测试。
- 为 Dashboard 聚合增加更多边界条件断言。
- 为 PDF 报表生成增加文件存在性和核心文本断言。
- 为分类器 provider 增加 mock HTTP 测试。
