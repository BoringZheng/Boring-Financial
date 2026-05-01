# 接口文档

## 1. 认证方式

除注册和登录外，业务接口都需要：

```http
Authorization: Bearer <access_token>
```

登录和注册返回 `access_token`、`refresh_token` 和当前用户信息。当前版本未实现 refresh token 黑名单，登出由前端清理本地 token。

## 2. Auth

### `POST /api/auth/register`

注册用户并直接登录。

```json
{
  "username": "boring",
  "password": "secret123",
  "email": "boring@example.com"
}
```

### `POST /api/auth/login`

使用用户名和密码登录。

```json
{
  "username": "boring",
  "password": "secret123"
}
```

### `GET /api/auth/me`

返回当前登录用户。

## 3. Categories

### `GET /api/categories`

返回系统分类和当前用户自定义分类。

### `POST /api/categories`

新增用户自定义分类。

```json
{
  "name": "宠物",
  "description": "猫粮、猫砂等",
  "parent_id": null
}
```

### `PATCH /api/categories/{category_id}`

更新分类名称、父级、描述或启用状态。系统分类不能在当前接口中禁用。

```json
{
  "name": "学习",
  "description": "课程、书籍、考试",
  "parent_id": null,
  "is_active": true
}
```

## 4. Imports

### `GET /api/imports`

返回当前用户的导入批次列表，按创建时间倒序。

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

返回当前用户上传过的文件，用于 Dashboard、交易列表和报表筛选。

### `GET /api/imports/{batch_id}`

获取导入批次详情。

### `DELETE /api/imports/{batch_id}`

删除导入批次及其关联上传文件、交易和分类结果。

## 5. Transactions

### `GET /api/transactions`

分页查询交易列表。

支持参数：

- `page`: 页码，默认 `1`
- `page_size`: 每页数量，默认 `20`，最大 `200`
- `platform`: 平台，例如 `WeChat`、`Alipay`
- `needs_review`: 是否待人工校正
- `search`: 搜索商家、商品或备注
- `category_id`: 分类筛选，匹配最终分类或自动分类
- `date_from`: 起始时间，ISO datetime 字符串
- `date_to`: 结束时间，ISO datetime 字符串
- `uploaded_file_ids`: 可重复传入的上传文件 ID

响应结构：

```json
{
  "items": [],
  "total": 0
}
```

### `PATCH /api/transactions/{transaction_id}/category`

人工修正最终分类。

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

生成 PDF 报表。

```json
{
  "title": "2026 年 5 月账单报告",
  "date_from": "2026-05-01T00:00:00",
  "date_to": "2026-05-31T23:59:59",
  "uploaded_file_ids": [1, 2]
}
```

### `GET /api/reports/{report_id}/download`

下载已生成的 PDF 报表。接口会校验报表归属。

## 9. 错误码

- `400`: 参数非法、用户名重复、系统分类非法更新。
- `401`: 未登录或 token 非法。
- `404`: 资源不存在或不属于当前用户。
- `500`: 解析错误、模型调用失败、文件生成失败。

## 10. 任务状态约定

当前代码同时支持同步开发态和 Celery 任务形态。导入和报表相关状态建议按以下语义展示：

```text
queued -> processing -> done
queued -> processing -> partial_failed
queued -> processing -> failed
```

前端目前通过轮询 `GET /api/imports` 和 `GET /api/imports/{batch_id}` 展示导入进度。

## 11. OpenAPI

启动后端后可访问：

- `/docs`
- `/redoc`
