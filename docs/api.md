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
    "is_active": true
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
    "is_active": true
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
  "is_active": true
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

## 7. Dashboard

### `GET /api/dashboard/summary`

返回 Dashboard 所需聚合数据。

支持参数：

- `date_from`
- `date_to`
- `category_id`
- `uploaded_file_ids`

返回字段：

- `expense_total`
- `income_total`
- `net_total`
- `transaction_count`
- `pending_review_count`
- `top_merchants`
- `category_breakdown`
- `expense_trend`
- `recent_jobs`

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

## 9. 错误码

- `400`: 参数非法、用户名重复、系统分类非法更新。
- `401`: 未登录或 token 非法。
- `404`: 资源不存在或不属于当前用户。
- `422`: 请求体格式不符合 schema（例如缺少必填字段、类型错误）。
- `500`: 解析错误、模型调用失败、文件生成失败。

## 10. Health

### `GET /health`

无需认证，返回服务健康状态。

```json
{
  "status": "ok"
}
```

## 11. 任务状态约定

当前代码同时支持同步开发态和 Celery 任务形态。导入和报表相关状态建议按以下语义展示：

```text
queued -> processing -> done
queued -> processing -> partial_failed
queued -> processing -> failed
```

前端目前通过轮询 `GET /api/imports` 和 `GET /api/imports/{batch_id}` 展示导入进度。

## 12. OpenAPI

启动后端后可访问：

- `/docs`
- `/redoc`
