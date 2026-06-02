# 接口文档

## 1. 认证方式

除注册和登录外，业务接口都需要：

```http
Authorization: Bearer <access_token>
```

登录和注册返回 `access_token`、`refresh_token` 和当前用户信息。当前版本未实现 refresh token 黑名单，登出由前端清理本地 token。

## 2. Auth

### `POST /api/auth/register`

注册用户并直接登录。成功返回 token pair 和用户信息。

请求：

```json
{
  "username": "boring",
  "password": "secret123",
  "email": "boring@example.com"
}
```

响应：

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "boring",
    "email": "boring@example.com",
    "is_active": true,
    "is_admin": false
  }
}
```

### `POST /api/auth/login`

使用用户名和密码登录。成功返回 token pair 和用户信息。

请求：

```json
{
  "username": "boring",
  "password": "secret123"
}
```

响应：

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "boring",
    "email": "boring@example.com",
    "is_active": true,
    "is_admin": false
  }
}
```

### `POST /api/auth/logout`

登出当前用户。当前版本未实现服务端 token 黑名单，登出由前端清理本地 token。

请求：

```json
{}
```

响应：

```json
{
  "message": "logged out"
}
```

### `GET /api/auth/me`

返回当前登录用户。

响应：

```json
{
  "id": 1,
  "username": "boring",
  "email": "boring@example.com",
  "is_active": true,
  "is_admin": false
}
```

## 3. Categories

### `GET /api/categories`

返回系统分类（`is_system: true`）和当前用户自定义分类（`is_system: false`）。系统分类的 `user_id` 为 `null`。

响应：

```json
[
  {
    "id": 1,
    "user_id": null,
    "parent_id": null,
    "name": "餐饮",
    "description": null,
    "is_system": true,
    "is_active": true
  },
  {
    "id": 12,
    "user_id": 1,
    "parent_id": null,
    "name": "宠物",
    "description": "猫粮、猫砂等",
    "is_system": false,
    "is_active": true
  }
]
```

### `POST /api/categories`

新增用户自定义分类。用户只能创建自己的分类。

请求：

```json
{
  "name": "宠物",
  "description": "猫粮、猫砂等",
  "parent_id": null
}
```

响应：返回创建后的 `CategoryRead` 对象，格式同 `GET /api/categories` 中的单项。

### `PATCH /api/categories/{category_id}`

更新分类名称、父级、描述或启用状态。系统分类（`is_system: true`）不能被禁用（`is_active: false`），否则返回 `400`。所有字段均可选。

请求：

```json
{
  "name": "学习",
  "description": "课程、书籍、考试",
  "parent_id": null,
  "is_active": true
}
```

响应：返回更新后的 `CategoryRead` 对象，格式同 `GET /api/categories` 中的单项。

## 4. Imports

### `GET /api/imports`

返回当前用户的导入批次列表，按创建时间倒序。

响应：

```json
[
  {
    "id": 1,
    "user_id": 1,
    "status": "done",
    "source_count": 2,
    "total_count": 128,
    "processed_count": 128,
    "progress_percent": 100.0,
    "error_message": null,
    "created_at": "2026-03-08T10:00:00",
    "updated_at": "2026-03-08T10:01:00"
  }
]
```

### `POST /api/imports`

上传账单文件。字段名固定为 `files`，支持多文件。

```http
Content-Type: multipart/form-data
files=<wechat.csv>
files=<alipay.xlsx>
```

响应示例：

```json
{
  "batch": {
    "id": 1,
    "user_id": 1,
    "status": "processing",
    "source_count": 2,
    "total_count": 128,
    "processed_count": 64,
    "progress_percent": 50,
    "error_message": null,
    "created_at": "2026-03-08T10:00:00",
    "updated_at": "2026-03-08T10:01:00"
  },
  "message": "import started"
}
```

### `GET /api/imports/files`

返回当前用户所有上传过的文件列表，用于 Dashboard、交易列表和报表筛选。

响应：

```json
[
  {
    "id": 1,
    "batch_id": 1,
    "filename": "wechat.csv",
    "platform": "WeChat",
    "status": "done",
    "error_message": null,
    "created_at": "2026-03-08T10:00:00"
  }
]
```

### `GET /api/imports/{batch_id}`

获取导入批次详情。响应格式同 `GET /api/imports` 列表中的单项。

### `DELETE /api/imports/{batch_id}`

删除导入批次及其关联的上传文件、交易和分类结果。成功返回 `204 No Content`。

## 5. Transactions

交易记录中包含两个分类 ID 字段：

- `auto_category_id`：模型或规则自动给出的分类建议，每次重分类会更新。
- `final_category_id`：人工通过 `PATCH /api/transactions/{id}/category` 修正后的最终分类。非 `null` 时优先于 `auto_category_id`。
- `needs_review`：`true` 表示分类置信度低于阈值或 `auto_category_id` 为 `null`，需要人工校正。

### `GET /api/transactions`

分页查询交易列表。

支持参数：

- `page`: 页码，默认 `1`
- `page_size`: 每页数量，默认 `20`，最大 `200`
- `platform`: 平台，例如 `WeChat`、`Alipay`
- `needs_review`: 是否待人工校正
- `search`: 搜索商家、商品或备注
- `category_id`: 分类筛选，匹配 `final_category_id` 或 `auto_category_id`
- `date_from`: 起始时间，ISO datetime 字符串
- `date_to`: 结束时间，ISO datetime 字符串
- `uploaded_file_ids`: 可重复传入的上传文件 ID

响应结构：

```json
{
  "items": [
    {
      "id": 1,
      "platform": "WeChat",
      "occurred_at": "2026-03-08T12:30:00",
      "type": "支出",
      "amount": "35.50",
      "merchant": "KFC",
      "item": "午餐",
      "note": null,
      "auto_provider": "composite",
      "auto_reason": "matched category rule",
      "auto_confidence": "0.9900",
      "auto_category_id": 2,
      "final_category_id": null,
      "needs_review": false
    }
  ],
  "total": 128
}
```

### `PATCH /api/transactions/{transaction_id}/category`

人工修正最终分类。设置 `final_category_id`，并可同时标记为已校正（`mark_reviewed: true` 会将 `needs_review` 置为 `false`）。

```json
{
  "category_id": 3,
  "mark_reviewed": true
}
```

## 6. Classification

### `POST /api/classification/reclassify`

对指定交易重新分类。

```json
{
  "transaction_ids": [1, 2, 3],
  "provider": "local_model"
}
```

响应：

```json
{
  "processed": 2,
  "failed": 1,
  "failures": [
    {"transaction_id": 3, "error": "model timeout"}
  ]
}
```

支持 provider：

- `rule`
- `openai_compatible_api`
- `local_model`
- `composite`

说明：
- `openai_compatible_api`、`local_model` 和默认 `composite` 的外部模型请求会先进入统一重试池，接口返回的 `processed` 表示已成功入队或命中缓存，不代表模型请求已同步完成。
- 交易的 `auto_provider` 可能为 `retry_queue`（等待后台重试）或 `retry_failed`（超时重试耗尽，等待管理员重新入池）。

### `POST /api/classification/retry-all`

管理员接口。将历史外部 API 超时、等待重试或重试失败的交易重新放入统一重试池。请求体可为空对象；传入 `user_id` 时只处理该用户。

请求：
```json
{
  "user_id": 1
}
```

响应：
```json
{
  "queued": 12
}
```

权限：
- 需要 Bearer token。
- 当前用户必须 `is_admin = true`，否则返回 `403`。

### `GET /api/classification/retry-status`

管理员接口。返回重试池聚合状态，用于后台实时监控。接口不会返回商户、备注、交易明细或外部 provider 原始错误。

支持 query 参数：
- `user_id`：可选，只统计指定用户。

响应：
```json
{
  "queued": 8,
  "failed": 2,
  "total": 10,
  "max_retries": 10,
  "delay_seconds": 1.0,
  "poll_seconds": 15.0,
  "oldest_queued_at": "2026-05-25T12:00:00",
  "oldest_failed_at": "2026-05-25T12:10:00",
  "newest_activity_at": "2026-05-25T12:20:00",
  "providers": [
    {"provider": "openai_compatible_api", "queued": 8, "failed": 2}
  ],
  "retry_counts": [
    {"retry_count": 0, "queued": 6},
    {"retry_count": 1, "queued": 2}
  ]
}
```

权限：
- 需要 Bearer token。
- 当前用户必须 `is_admin = true`，否则返回 `403`。

## 7. Dashboard

### `GET /api/dashboard/summary`

返回 Dashboard 所需聚合数据。

支持参数：

- `date_from`: 起始时间，ISO datetime 字符串，可选
- `date_to`: 结束时间，ISO datetime 字符串，可选
- `category_id`: 按分类筛选，可选
- `uploaded_file_ids`: 按上传文件筛选，可重复传入，可选

响应：

```json
{
  "expense_total": "12345.67",
  "income_total": "20000.00",
  "net_total": "7654.33",
  "transaction_count": 128,
  "pending_review_count": 5,
  "top_merchants": [
    {
      "merchant": "KFC",
      "amount": "1234.50",
      "transaction_count": 15
    },
    {
      "merchant": "美团",
      "amount": "876.00",
      "transaction_count": 12
    }
  ],
  "category_breakdown": [
    {
      "category_id": 2,
      "category_name": "餐饮",
      "amount": "3456.00",
      "transaction_count": 42
    },
    {
      "category_id": 5,
      "category_name": "交通",
      "amount": "1234.00",
      "transaction_count": 18
    }
  ],
  "expense_trend": [
    {
      "date": "2026-03-01",
      "expense": "456.00",
      "income": "0.00"
    },
    {
      "date": "2026-03-02",
      "expense": "312.50",
      "income": "20000.00"
    }
  ],
  "recent_jobs": [
    {
      "id": 1,
      "status": "done",
      "processed_count": 128,
      "total_count": 128,
      "source_count": 2,
      "progress_percent": 100.0
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `expense_total` | string (Decimal) | 支出合计 |
| `income_total` | string (Decimal) | 收入合计 |
| `net_total` | string (Decimal) | 净收支（收入 - 支出） |
| `transaction_count` | int | 交易总笔数 |
| `pending_review_count` | int | 待人工校正笔数 |
| `top_merchants` | array | 支出 Top 10 商户，按金额降序 |
| `top_merchants[].merchant` | string | 商户名称 |
| `top_merchants[].amount` | string (Decimal) | 该商户支出合计 |
| `top_merchants[].transaction_count` | int | 该商户交易笔数 |
| `category_breakdown` | array | 分类支出分布，按金额降序 |
| `category_breakdown[].category_id` | int \| null | 分类 ID |
| `category_breakdown[].category_name` | string | 分类名称 |
| `category_breakdown[].amount` | string (Decimal) | 该分类支出合计 |
| `category_breakdown[].transaction_count` | int | 该分类交易笔数 |
| `expense_trend` | array | 每日收支趋势，按日期升序 |
| `expense_trend[].date` | string | 日期 (YYYY-MM-DD) |
| `expense_trend[].expense` | string (Decimal) | 当日支出 |
| `expense_trend[].income` | string (Decimal) | 当日收入 |
| `recent_jobs` | array | 最近 5 个导入批次 |
| `recent_jobs[].id` | int | 批次 ID |
| `recent_jobs[].status` | string | 批次状态 |
| `recent_jobs[].processed_count` | int | 已处理笔数 |
| `recent_jobs[].total_count` | int | 总笔数 |
| `recent_jobs[].source_count` | int | 源文件数 |
| `recent_jobs[].progress_percent` | float | 进度百分比 |


## 8. Reports

### `POST /api/reports`

生成 PDF 报表。所有字段均可选：`date_from` 和 `date_to` 接受 ISO datetime 字符串或空字符串（空字符串视为不限），`title` 不传则使用默认标题，`uploaded_file_ids` 不传则涵盖全部导入文件。

请求：

```json
{
  "title": "2026 年 5 月账单报告",
  "date_from": "2026-05-01T00:00:00",
  "date_to": "2026-05-31T23:59:59",
  "uploaded_file_ids": [1, 2]
}
```

响应：

```json
{
  "id": 1,
  "user_id": 1,
  "job_id": 1,
  "title": "2026 年 5 月账单报告",
  "file_path": "storage/reports/report-1-1.pdf"
}
```

### `GET /api/reports/{report_id}/download`

下载已生成的 PDF 报表。接口会校验报表归属，返回 `application/pdf` 文件流。

> **已知限制**：当前版本未提供 `GET /api/reports` 报表历史列表接口。跟踪状态请参考 [架构文档](./architecture.md) 可扩展方向。

## 9. Personality

消费人格分析模块基于行为经济学理论，从用户交易数据中提取四维人格画像，并提供自评测验与数据画像的偏差对比。

理论依据：
- **现时偏好 (Time Preference)**：基于 Laibson 双曲贴现模型，通过储蓄率和小额交易占比衡量延迟满足倾向。
- **心理账户 (Mental Accounting)**：基于 Thaler 心理账户理论，通过分类支出分布的方差衡量消费分区的严格程度。
- **炫耀性消费 (Conspicuous Consumption)**：基于 Veblen 炫耀性消费理论，通过餐饮/服饰/数码/娱乐等品类的支出占比衡量地位驱动消费。
- **消费开放性 (Openness)**：基于大五人格 Openness 维度，通过商户 Shannon 多样性指数和近期新商户比例衡量消费探索倾向。

人格分类体系包含 16 型三维编码（如 `P-S-U` 貔貅型、`I-E-V` 消费主义代言人等），每型含名称、标语、名人名言和学术依据。

### `GET /api/personality/profile`

返回当前用户的消费人格画像和财务健康评分。需要认证。

响应：

```json
{
  "personality": {
    "code": "P-S-U",
    "name": "貔貅型",
    "tagline": "只进不出，省钱界的传奇生物",
    "quote": "我的钱不是花掉了，只是暂时变成了用得上的东西。",
    "match_percent": 78.5,
    "secondary_code": "P-E-U",
    "secondary_name": "旅行青蛙",
    "dimensions": [
      {
        "name": "time_preference",
        "value": 32.1,
        "side": "Patient",
        "label": "延迟满足型",
        "theory_ref": "Laibson 双曲贴现模型",
        "interpretation": "你倾向于延迟满足，注重长期财务规划。你的消费决策受即时诱惑的影响较小，更关注未来的财务安全。"
      },
      {
        "name": "mental_accounting",
        "value": 45.3,
        "side": "Flexible",
        "label": "灵活调配",
        "theory_ref": "Thaler 心理账户理论",
        "interpretation": "你的心理账户较为灵活，不同类目的支出可以自由调配。"
      },
      {
        "name": "conspicuous_consumption",
        "value": 28.7,
        "side": "Utilitarian",
        "label": "实用主义",
        "theory_ref": "Veblen 炫耀性消费理论",
        "interpretation": "你是实用主义消费者，消费以功能和性价比为导向。"
      },
      {
        "name": "openness",
        "value": 41.2,
        "side": "Stable",
        "label": "习惯稳定",
        "theory_ref": "大五人格 Openness 维度",
        "interpretation": "你的消费习惯较为稳定，倾向于在熟悉的商家和品类中消费。"
      }
    ]
  },
  "financial_health": {
    "total_score": 72.4,
    "grade": "B",
    "dimensions": [
      {"name": "savings_rate", "value": 80.0, "label": "储蓄率"},
      {"name": "income_stability", "value": 65.0, "label": "收入稳定性"},
      {"name": "spending_diversity", "value": 53.3, "label": "消费多样性"},
      {"name": "expense_volatility", "value": 78.0, "label": "支出波动"},
      {"name": "emergency_capacity", "value": 85.7, "label": "应急能力"}
    ],
    "suggestions": [
      "你的消费多样性较低，生活支出较为单一，可以适当增加自我投资和体验类消费。"
    ]
  },
  "has_data": true
}
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `personality.code` | string | 三维人格编码，如 `P-S-U` |
| `personality.name` | string | 人格类型中文名称 |
| `personality.tagline` | string | 一句话描述 |
| `personality.quote` | string | 人格代表性引言 |
| `personality.match_percent` | float | 与人格原型的匹配度 (0-100) |
| `personality.secondary_code` | string | 次近人格编码 |
| `personality.secondary_name` | string | 次近人格中文名称 |
| `personality.dimensions` | array | 四维人格评分，各 0-100 |
| `personality.dimensions[].name` | string | 维度名 |
| `personality.dimensions[].value` | float | 维度分值 (0-100, 50 为中性) |
| `personality.dimensions[].side` | string | 英文维度侧标 (Patient/Impulsive 等) |
| `personality.dimensions[].label` | string | 中文维度标签 |
| `personality.dimensions[].theory_ref` | string | 学术理论依据 |
| `personality.dimensions[].interpretation` | string | 该维度得分的中文解释 |
| `financial_health.total_score` | float | 财务健康总分 (0-100) |
| `financial_health.grade` | string | 等级 (S/A/B/C/D) |
| `financial_health.dimensions` | array | 五维健康分项 |
| `financial_health.suggestions` | array of string | 改进建议列表 |
| `has_data` | bool | 是否有交易数据（无数据时返回默认中位画像） |

### `GET /api/personality/quiz`

返回 10 道消费心理测验题。每题包含 4 个选项，各维度分布为：现时偏好 3 题、心理账户 2 题、炫耀性消费 2 题、消费开放性 2 题、综合 1 题。无需认证。

响应：

```json
[
  {
    "id": 1,
    "dimension": "time_preference",
    "text": "看到「限时优惠」你会？",
    "options": [
      {"value": 1, "text": "完全无视，我只买需要的"},
      {"value": 2, "text": "会看一眼，但很少被影响"},
      {"value": 3, "text": "经常会因为限时而下单"},
      {"value": 4, "text": "立刻下单，万一错过了呢"}
    ]
  }
]
```

### `POST /api/personality/quiz/result`

提交测验答案，返回自评画像与数据驱动画像的对比分析。需要认证。

请求：

```json
{
  "answers": [2, 1, 3, 4, 2, 1, 2, 3, 1, 2]
}
```

`answers` 为 10 个 1-4 的整数，顺序对应测验题目顺序。

响应：

```json
{
  "self_assessment": {
    "dimensions": {
      "time_preference": 33.3,
      "mental_accounting": 44.4,
      "conspicuous_consumption": 55.6,
      "openness": 66.7
    }
  },
  "data_profile": {
    "code": "P-S-U",
    "name": "貔貅型",
    "tagline": "只进不出，省钱界的传奇生物",
    "quote": "我的钱不是花掉了，只是暂时变成了用得上的东西。",
    "match_percent": 78.5,
    "secondary_code": "P-E-U",
    "secondary_name": "旅行青蛙",
    "dimensions": [
      {
        "name": "time_preference",
        "value": 32.1,
        "side": "Patient",
        "label": "延迟满足型",
        "theory_ref": "Laibson 双曲贴现模型",
        "interpretation": "你倾向于延迟满足，注重长期财务规划。"
      }
    ]
  },
  "comparison": {
    "cosine_similarity": 0.8521,
    "biggest_gap": {
      "dimension": "openness",
      "self_score": 66.7,
      "data_score": 41.2,
      "gap": 25.5,
      "analysis": "你自认为在「消费开放性」维度上得分较高（67），但实际消费数据得分较低（41）。这可能意味着你高估了自己在这一维度的消费倾向。",
      "theory_ref": "大五人格 Openness 维度"
    },
    "bias_analysis": "你的自评人格与数据人格高度一致。说明你对自身消费习惯有较准确的认知。最大的认知偏差出现在「消费开放性」维度（差距 25.5 分），你对该维度的自我认知与实际消费数据存在明显差异。"
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `self_assessment.dimensions` | object | 自评四维得分 (0-100)，key 为维度名 |
| `data_profile` | PersonalityProfile | 基于交易数据的人格画像，结构同 `/profile` 中的 `personality` |
| `comparison.cosine_similarity` | float | 自评向量与数据向量的余弦相似度 (0-1) |
| `comparison.biggest_gap.dimension` | string | 偏差最大的维度名 |
| `comparison.biggest_gap.self_score` | float | 该维度自评得分 |
| `comparison.biggest_gap.data_score` | float | 该维度数据得分 |
| `comparison.biggest_gap.gap` | float | 绝对差值 |
| `comparison.biggest_gap.analysis` | string | 偏差方向与心理学解释 |
| `comparison.biggest_gap.theory_ref` | string | 学术理论依据 |
| `comparison.bias_analysis` | string | 综合偏差分析文本 |

## 10. 错误码

- `400`: 参数非法、用户名重复、系统分类非法更新。
- `401`: 未登录或 token 非法。
- `404`: 资源不存在或不属于当前用户。
- `422`: 请求体格式不符合 schema（例如缺少必填字段、类型错误）。
- `500`: 解析错误、模型调用失败、文件生成失败。

## 11. Health

### `GET /health`

无需认证，返回服务健康状态。

```json
{
  "status": "ok"
}
```

## 12. 任务状态约定

当前代码同时支持同步开发态和 Celery 任务形态。导入和报表相关状态建议按以下语义展示：

```text
queued -> processing -> done
queued -> processing -> partial_failed
queued -> processing -> failed
```

前端目前通过轮询 `GET /api/imports` 和 `GET /api/imports/{batch_id}` 展示导入进度。

## 13. OpenAPI

启动后端后可访问：

- `/docs`
- `/redoc`
