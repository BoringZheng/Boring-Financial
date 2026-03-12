# 接口文档

## 认证方式

- 使用 `Authorization: Bearer <access_token>`
- 登录与注册返回 `access_token` 和 `refresh_token`
- 当前版本未实现 refresh token 黑名单，登出为客户端清理令牌

## 核心接口

### `POST /api/auth/register`

注册并直接返回 token。

请求示例：

```json
{
  "username": "boring",
  "password": "secret123",
  "email": "boring@example.com"
}
```

### `POST /api/auth/login`

登录并返回 token。

### `GET /api/auth/me`

获取当前用户信息。

### `GET /api/categories`

获取系统分类与当前用户分类。

### `POST /api/categories`

新增用户分类。

请求示例：

```json
{
  "name": "宠物",
  "description": "猫粮、猫砂等"
}
```

### `POST /api/imports`

上传账单文件。字段名固定为 `files`，支持多文件。

响应示例：

```json
{
  "batch": {
    "id": 1,
    "user_id": 1,
    "status": "done",
    "source_count": 2,
    "processed_count": 128,
    "error_message": null,
    "created_at": "2026-03-08T10:00:00",
    "updated_at": "2026-03-08T10:01:00"
  },
  "message": "import completed"
}
```

### `GET /api/imports/{batch_id}`

获取导入批次详情。

### `GET /api/transactions`

查询交易列表，支持参数：

- `page`
- `page_size`
- `platform`
- `needs_review`
- `search`

### `PATCH /api/transactions/{transaction_id}/category`

人工修正最终分类。

```json
{
  "category_id": 3,
  "mark_reviewed": true
}
```

### `POST /api/classification/reclassify`

对指定交易重新分类。

```json
{
  "transaction_ids": [1, 2, 3],
  "provider": "local_model"
}
```

### `GET /api/dashboard/summary`

返回 Dashboard 所需聚合数据：

- 总支出
- 总收入
- 净流入
- 待校正数量
- Top 商户
- 分类分布
- 最近导入任务

### `POST /api/reports`

生成 PDF 报表。

```json
{
  "title": "2025 暑期账单报告",
  "date_from": "2025-07-01T00:00:00",
  "date_to": "2025-08-31T23:59:59"
}
```

### `GET /api/reports/{report_id}/download`

下载已生成的 PDF 报表。

## 错误码

- `400`: 参数非法、用户名重复、系统分类非法更新
- `401`: 未登录或 token 非法
- `404`: 资源不存在或不属于当前用户
- `500`: 解析错误、模型调用失败、文件生成失败

## 任务轮询约定

当前开发版本大部分任务在请求内同步完成，但保留了 Celery 任务形态。若切换到异步模式，建议采用：

- 创建任务后返回 `job_id`
- 前端定时轮询 `GET /api/imports/{id}` 或未来的 `GET /api/jobs/{id}`
- 状态流转：`queued -> processing -> done / partial_failed / failed`

## OpenAPI

运行后端后可访问：

- `/docs`
- `/redoc`
