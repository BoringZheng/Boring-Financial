# Boring Financial 期末报告绘图新版

本文档集中维护期末报告中的“图”。除页面截图组外，所有可绘制图均使用 PlantUML 支持的格式，便于统一渲染为 PNG/SVG 后放入 LaTeX。表格类图表（需求表、风险矩阵、测试用例表等）仍放在正文对应章节中，不在这里重复绘制。

排版原则：

- 大图按层、按职责分组，避免“所有节点一锅炖”。
- ER 图和类图拆成子图，报告中可作为同一图号下的 (a)(b) 子图。
- 用例图减少直连线，利用 actor 泛化和 usecase 分组提高可读性。
- 顺序图用 `box` 分组，突出前端、后端服务、数据/外部服务边界。
- PlantUML 渲染建议使用 SVG；若放入 Word/PDF，可导出 PNG。

本版基于当前 main 代码结构：

- 前端包含 `DashboardPage`、`ImportsPage`、`TransactionsPage`、`ReviewPage`、`CategoriesPage`、`PersonalityPage`、`OrganizationPage`、`ReportsPage`、`SettingsPage`。
- 后端包含 `routes_personality.py`、`routes_organizations.py`、`services/personality.py`、`services/organizations.py`。
- Dashboard、Personality、Reports 支持可选 `organization_id`，用于家庭组织聚合。
- 个人账本默认口径不变，家庭组织通过 owner/admin/member 角色控制访问。
- 类图按设计模式拆为四张：领域实体（Data Mapper + Mixin）、分类器策略（Strategy + Chain of Responsibility + Facade）、解析器（Strategy + Adapter + Registry）、报表构建器（Builder）。

## 1. 开发流程图

用于第 2 章“开发流程选择”。用泳道表达开发阶段和反馈回路。

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false
skinparam activity {
  BackgroundColor #F8FAFC
  BorderColor #2563EB
  ArrowColor #334155
  DiamondBackgroundColor #ECFDF5
  DiamondBorderColor #059669
}

start

partition "规划与设计" {
  :立项与可行性分析;
  :需求分析与范围确认;
  :原型与架构设计;
}

repeat
  partition "实现与联调" {
    :核心功能实现;
    :前后端联调;
  }

  if (发现需求、接口或设计问题?) then (是)
    partition "反馈修正" {
      :修正需求、接口或模块设计;
    }
  endif
repeat while (需要继续迭代?) is (是) not (否)

partition "交付" {
  :测试、部署与报告;
}

stop

note right
  反馈来源：
  账单格式差异、模型分类效果、
  消费人格与家庭组织联调结果
end note
@enduml
```

## 2. 简化甘特图

用于第 2 章“项目进度计划”。PlantUML 甘特图排版更适合横向放置。

```plantuml
@startgantt
printscale weekly
Project starts 2026-03-01

[选题与项目目标确认] starts 2026-03-01 and ends 2026-03-12
[可行性研究与团队分工] starts 2026-03-10 and ends 2026-03-25
[需求分析与需求建模] starts 2026-03-18 and ends 2026-04-09

[前端原型与 UX 设计] starts 2026-04-01 and ends 2026-04-20
[系统架构与部署设计] starts 2026-04-08 and ends 2026-04-30
[安全机制与运行维护设计] starts 2026-04-15 and ends 2026-04-30

[后端接口与数据模型] starts 2026-04-15 and ends 2026-05-18
[前端页面与交互] starts 2026-04-20 and ends 2026-05-25
[分类模型与重试机制] starts 2026-04-25 and ends 2026-05-25
[消费人格与家庭组织] starts 2026-05-20 and ends 2026-06-03
[前后端联调] starts 2026-05-10 and ends 2026-06-05

[测试与问题修复] starts 2026-05-25 and ends 2026-06-10
[部署文档与演示脚本] starts 2026-06-01 and ends 2026-06-15
[最终报告与答辩准备] starts 2026-06-08 and ends 2026-06-22
@endgantt
```

## 3. 用例图

用于第 3 章“用例建模”。用 actor 泛化减少普通用户和家庭管理员之间的重复连线。

```plantuml
@startuml
left to right direction
skinparam backgroundColor transparent
skinparam shadowing false
skinparam packageStyle rectangle
skinparam usecase {
  BackgroundColor #F8FAFC
  BorderColor #2563EB
  ArrowColor #334155
}

actor "普通用户" as User
actor "家庭组织\nowner/admin" as OrgAdmin
actor "系统运维人员" as Ops
OrgAdmin --|> User

rectangle "Boring Financial" {
  package "个人账本" {
    usecase "注册/登录" as UC1
    usecase "导入账单" as UC2
    usecase "查看交易与筛选" as UC3
    usecase "查看模型分类理由" as UC4
    usecase "人工校正分类" as UC5
    usecase "管理分类" as UC6
  }

  package "分析与输出" {
    usecase "查看 Dashboard" as UC7
    usecase "查看消费人格" as UC8
    usecase "生成 PDF 报表" as UC9
  }

  package "家庭组织" {
    usecase "创建家庭组织" as UC10
    usecase "管理家庭成员" as UC11
    usecase "查看家庭聚合分析" as UC12
    usecase "家庭范围重试/重分类" as UC13
  }

  package "运维配置" {
    usecase "配置模型 provider" as UC14
    usecase "查看重试队列状态" as UC15
  }
}

User --> UC1
User --> UC2
User --> UC3
User --> UC5
User --> UC6
User --> UC7
User --> UC8
User --> UC9
User --> UC10
User --> UC12

OrgAdmin --> UC11
OrgAdmin --> UC13

Ops --> UC14
Ops --> UC15

UC2 ..> UC4 : <<include>>
UC12 ..> UC7 : organization_id
UC12 ..> UC8 : organization_id
UC12 ..> UC9 : organization_id
@enduml
```

## 4. 核心业务活动图

用于第 3 章“业务流程建模”。按“导入分类”和“分析输出”分段，减少活动图过长带来的视觉拥挤。

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false
skinparam activity {
  BackgroundColor #F8FAFC
  BorderColor #0F766E
  ArrowColor #334155
  DiamondBackgroundColor #EFF6FF
  DiamondBorderColor #2563EB
}

start

partition "账单导入与标准化" {
  :用户登录系统;
  :上传微信/支付宝账单;
  :创建导入批次和上传文件记录;
  :解析账单文件;

  if (解析成功?) then (否)
    :记录错误并提示重新上传;
    stop
  endif

  :转换为统一交易结构;
  :生成 dedupe_hash 去重;
}

partition "语义分类与人工校正" {
  :大模型语义初分;
  if (置信度足够?) then (否)
    :进入人工校正队列;
    :用户人工校正;
  endif
  :写入最终分类;
}

partition "分析与报表" {
  fork
    :个人 Dashboard 聚合;
  fork again
    :个人消费人格与财务健康分析;
  end fork

  if (选择家庭组织?) then (否)
    :生成个人 PDF 报表;
    stop
  endif

  :校验 OrganizationMember 权限;
  if (是组织成员?) then (否)
    :拒绝访问;
    stop
  endif

  :按组织成员 user_id 聚合;
  :家庭 Dashboard / 家庭消费人格 / 家庭报表;
}

stop
@enduml
```

## 5. 系统总体架构图

用于第 5 章”总体架构”。自上而下分层，适合报告纵向排版。

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false
skinparam componentStyle rectangle
skinparam packageStyle rectangle

actor “Browser” as Browser

package “展示层” #EEF2FF {
  component “Vue 3 + Element Plus + ECharts” as Frontend
}

package “网关层” #F8FAFC {
  component “Nginx（静态文件 + /api 反向代理）” as Nginx
}

package “服务层” #ECFDF5 {
  component “FastAPI 后端” as API {
    port “Auth” as Auth
    port “Imports” as Imports
    port “Transactions” as Transactions
    port “Classification” as Classification
    port “Dashboard” as Analytics
    port “Personality” as Personality
    port “Organizations” as Organizations
    port “Reports” as Reports
  }
}

package “数据与外部服务层” #FFF7ED {
  database “PostgreSQL / SQLite” as DB
  database “Redis” as Redis
  component “Retry Queue Worker” as Retry
  cloud “OpenAI-compatible API” as OpenAI
  component “Local Model\nService / vLLM” as LocalModel
}

Browser -down-> Frontend
Frontend -down-> Nginx : HTTP
Nginx -down-> API : /api 代理
API -down-> DB
API -down-> Redis
Classification -down-> Retry
Retry -down-> DB
Retry -down-> OpenAI
Retry -down-> LocalModel
@enduml
```

## 6. UML 组件图

用于第 5 章”组件图”。自上而下分层，减少横向宽度。

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false
skinparam componentStyle rectangle
skinparam packageStyle rectangle

package “Frontend” #EEF2FF {
  component “AppLayout.vue\n（布局外壳）” as Layout
  component “Pages\n（10 个页面组件）” as Pages
  component “Pinia Auth Store\n（认证状态）” as Store
  component “api/client.ts\n（Axios + JWT）” as Client
  component “types/\n（TS 类型定义）” as Types

  Layout -down-> Pages
  Pages -down-> Store
  Pages -down-> Client
  Pages -down-> Types
}

package “Backend API” #ECFDF5 {
  component “api/router.py\n（路由注册中心）” as Router
  component “Core Routes\nAuth / Imports / Transactions\nClassification / Dashboard” as CoreRoutes
  component “Feature Routes\nPersonality / Organizations\nReports” as FeatureRoutes
}

package “Backend Services” #F8FAFC {
  component “imports / parsers\n（导入与解析）” as ImportSvc
  component “classifiers /\nretry_queue\n（分类与重试）” as ClassSvc
  component “analytics /\npersonality\n（聚合与人格）” as AnalysisSvc
  component “organizations\n（家庭组织）” as OrgSvc
  component “reports\n（报表生成）” as ReportSvc
}

package “Persistence & External” #FFF7ED {
  component “schemas/*\n（Pydantic DTO）” as Schemas
  component “models/entities.py\n（ORM 实体）” as Models
  database “Database\nPostgreSQL / SQLite” as DB
  database “Redis\n（缓存与队列）” as Redis
  cloud “Model Provider\nOpenAI / vLLM” as ModelProvider
  folder “File Storage\n（上传 + 报表）” as Storage
}

Client -down-> Router : HTTP
Router -down-> CoreRoutes
Router -down-> FeatureRoutes
CoreRoutes -down-> ImportSvc
CoreRoutes -down-> ClassSvc
CoreRoutes -down-> AnalysisSvc
FeatureRoutes -down-> AnalysisSvc
FeatureRoutes -down-> OrgSvc
FeatureRoutes -down-> ReportSvc
ImportSvc -down-> Models
ClassSvc -down-> Models
AnalysisSvc -down-> Models
OrgSvc -down-> Models
ReportSvc -down-> Models
Models -down-> DB
ClassSvc -down-> Redis
ClassSvc -down-> ModelProvider
ReportSvc -down-> Storage
@enduml
```

## 7. 包图

用于第 5 章“包图”。减少嵌套层级，用子包分组表达目录结构。

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false
skinparam packageStyle rectangle
skinparam nodesep 24
skinparam ranksep 28
skinparam defaultTextAlignment center

top to bottom direction

package "Boring-Financial" as Root {
  package "backend/" as Backend #ECFDF5 {
    package "api/" as BackendApi {
      component "auth / categories" as ApiBasic
      component "imports / transactions\nclassification" as ApiBills
      component "dashboard / personality\norganizations / reports" as ApiInsights

      ApiBasic -[hidden]down-> ApiBills
      ApiBills -[hidden]down-> ApiInsights
    }

    package "services/" as BackendServices {
      component "auth / bootstrap\nimports / parsers" as ServiceBasic
      component "classifiers / retry_queue\nreliability_metrics" as ServiceAsync
      component "analytics / personality\norganizations / reports" as ServiceInsights

      ServiceBasic -[hidden]down-> ServiceAsync
      ServiceAsync -[hidden]down-> ServiceInsights
    }

    package "models/\n（ORM 实体）" as BackendModels
    package "schemas/\n（Pydantic DTO）" as BackendSchemas
    package "db/\n（会话 + 基类）" as BackendDb
    package "core/\n（配置 + 安全）" as BackendCore
    package "tasks/\n（Celery 异步任务）" as BackendTasks
    package "utils/\n（数据规范化）" as BackendUtils
    package "tests/\n（pytest）" as BackendTests
    package "alembic/\n（数据库迁移）" as BackendAlembic

    BackendApi -[hidden]right-> BackendServices
    BackendApi -[hidden]down-> BackendModels
    BackendServices -[hidden]down-> BackendSchemas
    BackendModels -[hidden]right-> BackendSchemas
    BackendModels -[hidden]down-> BackendDb
    BackendSchemas -[hidden]down-> BackendCore
    BackendDb -[hidden]right-> BackendCore
    BackendDb -[hidden]down-> BackendTasks
    BackendCore -[hidden]down-> BackendUtils
    BackendTasks -[hidden]right-> BackendUtils
    BackendTasks -[hidden]down-> BackendTests
    BackendUtils -[hidden]down-> BackendAlembic
    BackendTests -[hidden]right-> BackendAlembic
  }

  package "frontend/src/" as Frontend #EEF2FF {
    package "pages/\n（10 个页面组件）" as FrontendPages
    package "layouts/\n（AppLayout）" as FrontendLayouts
    package "router/\n（Vue Router）" as FrontendRouter
    package "stores/\n（Pinia Auth）" as FrontendStores
    package "api/\n（Axios Client）" as FrontendApi
    package "types/\n（TypeScript 接口）" as FrontendTypes
    package "composables/\n（重试进度复用）" as FrontendComposables
    package "main.ts / App.vue\n（应用入口）" as FrontendEntry

    FrontendPages -[hidden]right-> FrontendLayouts
    FrontendPages -[hidden]down-> FrontendRouter
    FrontendLayouts -[hidden]down-> FrontendStores
    FrontendRouter -[hidden]right-> FrontendStores
    FrontendRouter -[hidden]down-> FrontendApi
    FrontendStores -[hidden]down-> FrontendTypes
    FrontendApi -[hidden]right-> FrontendTypes
    FrontendApi -[hidden]down-> FrontendComposables
    FrontendTypes -[hidden]down-> FrontendEntry
    FrontendComposables -[hidden]right-> FrontendEntry
  }

  package "infra/" as Infra #FFF7ED {
    component "Docker Compose\nNginx / systemd\nmock model service" as InfraContent
  }

  package "docs/\n（架构 / 接口 / 测试 / 部署）" as Docs #F8FAFC
  package "scripts/\n（部署辅助脚本）" as Scripts #F8FAFC

  Backend -[hidden]down-> Frontend
  Frontend -[hidden]down-> Infra
  Infra -[hidden]right-> Docs
  Docs -[hidden]right-> Scripts
}
@enduml
```

## 8. 部署图

用于第 5 章”部署图”。自上而下，服务器内部组件分组展示。

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false

actor “Browser” as Browser

node “应用服务器” as Server #ECFDF5 {
  node “Nginx” as Nginx {
    artifact “Vue 静态资源” as Static
    artifact “/api 反向代理” as Proxy
  }

  node “FastAPI / Uvicorn” as Uvicorn
  node “Retry Queue\nWorker（后台线程）” as Retry
  database “PostgreSQL\n（生产）/ SQLite\n（轻量）” as DB
  database “Redis\n（缓存 + 队列）” as Redis
  folder “storage/\n上传文件 + PDF” as Storage
  node “Local Model\nService / vLLM” as LocalModel
}

cloud “OpenAI-compatible\nAPI（外部服务）” as OpenAI

Browser -down-> Nginx : HTTP/HTTPS
Nginx -down-> Uvicorn : /api
Uvicorn -down-> DB : SQL
Uvicorn -down-> Redis
Uvicorn -down-> Storage : 读写文件
Uvicorn -down-> Retry : 任务入队
Retry -down-> DB
Retry --> LocalModel : HTTP
Retry --> OpenAI : HTTPS
@enduml
```

## 9. ER 图

用于第 6 章“数据库设计”。建议拆成两张子图：核心账单 ER 和家庭/报表扩展 ER。这样比一张巨型 ER 图更适合报告排版。

### 9.1 核心账单 ER 图

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false

entity users {
  * id : int <<PK>>
  --
  username : string <<UK>>
  email : string <<UK>>
  is_admin : bool
}

entity categories {
  * id : int <<PK>>
  --
  user_id : int <<FK, nullable>>
  parent_id : int <<FK, nullable>>
  name : string
  is_system : bool
}

entity import_batches {
  * id : int <<PK>>
  --
  user_id : int <<FK>>
  status : string
  processed_count : int
  total_count : int
}

entity uploaded_files {
  * id : int <<PK>>
  --
  batch_id : int <<FK>>
  filename : string
}

entity transactions {
  * id : int <<PK>>
  --
  user_id : int <<FK>>
  batch_id : int <<FK>>
  uploaded_file_id : int <<FK>>
  amount : decimal
  merchant : string
  dedupe_hash : string
  auto_category_id : int <<FK>>
  final_category_id : int <<FK>>
  needs_review : bool
}

entity classification_results {
  * id : int <<PK>>
  --
  transaction_id : int <<FK>>
  category_id : int <<FK>>
  provider : string
  confidence : decimal
  reason : string
}

entity classification_caches {
  * id : int <<PK>>
  --
  user_id : int <<FK>>
  category_id : int <<FK>>
  cache_key : string
}

users ||--o{ categories : owns
categories ||--o{ categories : parent
users ||--o{ import_batches : owns
import_batches ||--o{ uploaded_files : contains
import_batches ||--o{ transactions : imports
uploaded_files ||--o{ transactions : source
users ||--o{ transactions : owns
categories ||--o{ transactions : auto/final
transactions ||--o{ classification_results : has
categories ||--o{ classification_results : assigned
users ||--o{ classification_caches : owns
categories ||--o{ classification_caches : cached
@enduml
```

### 9.2 家庭组织与报表扩展 ER 图

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false

entity users {
  * id : int <<PK>>
  --
  username : string
  is_admin : bool
}

entity organizations {
  * id : int <<PK>>
  --
  name : string
  created_by_user_id : int <<FK>>
  plan : string
  subscription_status : string
}

entity organization_members {
  * id : int <<PK>>
  --
  organization_id : int <<FK>>
  user_id : int <<FK>>
  role : owner/admin/member
}

entity transactions {
  * id : int <<PK>>
  --
  user_id : int <<FK>>
  amount : decimal
  final_category_id : int
}

entity report_jobs {
  * id : int <<PK>>
  --
  user_id : int <<FK>>
  status : string
  date_from : datetime
  date_to : datetime
}

entity generated_reports {
  * id : int <<PK>>
  --
  user_id : int <<FK>>
  job_id : int <<FK>>
  file_path : string
}

users ||--o{ organizations : creates
users ||--o{ organization_members : joins
organizations ||--o{ organization_members : has
users ||--o{ transactions : owns
users ||--o{ report_jobs : owns
report_jobs ||--o{ generated_reports : produces
users ||--o{ generated_reports : owns

note right of organizations
  家庭聚合不改变交易归属。
  organization_id 只用于查询时
  取组织成员 user_id 列表。
end note
@enduml
```

## 10. 类图

用于第 6 章”面向对象组织方式”。按设计模式拆为四张独立类图：领域实体（Data Mapper + Mixin）、分类器策略（Strategy + Chain of Responsibility + Facade）、解析器（Strategy + Adapter + Registry）、报表构建器（Builder）。

### 10.1 领域实体类图

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false
skinparam classAttributeIconSize 0
hide circle

class TimestampMixin {
  +created_at : datetime
  +updated_at : datetime
}

class User {
  +id : int <<PK>>
  +username : str <<UK>>
  +email : str <<UK>>
  +hashed_password : str
  +is_active : bool
  +is_admin : bool
}

class Organization {
  +id : int <<PK>>
  +name : str
  +created_by_user_id : int <<FK>>
  +plan : str
}

class OrganizationMember {
  +id : int <<PK>>
  +organization_id : int <<FK>>
  +user_id : int <<FK>>
  +role : str
}

class Category {
  +id : int <<PK>>
  +user_id : int <<FK, nullable>>
  +parent_id : int <<FK, nullable>>
  +name : str
  +is_system : bool
}

class CategoryRule {
  +id : int <<PK>>
  +user_id : int <<FK>>
  +category_id : int <<FK>>
  +priority : int
  +merchant_pattern : str
  +keyword_pattern : str
}

class ImportBatch {
  +id : int <<PK>>
  +user_id : int <<FK>>
  +status : str
  +total_count : int
  +processed_count : int
}

class UploadedFile {
  +id : int <<PK>>
  +batch_id : int <<FK>>
  +filename : str
  +platform : str
}

class Transaction {
  +id : int <<PK>>
  +user_id : int <<FK>>
  +batch_id : int <<FK>>
  +amount : decimal
  +merchant : str
  +item : str
  +dedupe_hash : str <<UK>>
  +auto_category_id : int <<FK>>
  +final_category_id : int <<FK>>
  +auto_confidence : decimal
  +auto_provider : str
  +needs_review : bool
}

class ClassificationResult {
  +id : int <<PK>>
  +transaction_id : int <<FK>>
  +category_id : int <<FK>>
  +provider : str
  +confidence : decimal
  +reason : str
}

class ClassificationCache {
  +id : int <<PK>>
  +user_id : int <<FK>>
  +text_hash : str <<UK>>
  +category_id : int <<FK>>
}

class ReportJob {
  +id : int <<PK>>
  +user_id : int <<FK>>
  +status : str
  +date_from : datetime
  +date_to : datetime
}

class GeneratedReport {
  +id : int <<PK>>
  +user_id : int <<FK>>
  +job_id : int <<FK>>
  +title : str
  +file_path : str
}

' Mixin inheritance
User -up-|> TimestampMixin
Organization -up-|> TimestampMixin
OrganizationMember -up-|> TimestampMixin
Category -up-|> TimestampMixin
ImportBatch -up-|> TimestampMixin
Transaction -up-|> TimestampMixin
ReportJob -up-|> TimestampMixin

' Relationships
User “1” --> “*” Organization : creates
User “1” --> “*” OrganizationMember
Organization “1” --> “*” OrganizationMember
User “1” --> “*” Category
Category ||--o{ Category : parent
User “1” --> “*” CategoryRule
Category “1” --> “*” CategoryRule
User “1” --> “*” ImportBatch
ImportBatch “1” --> “*” UploadedFile
ImportBatch “1” --> “*” Transaction : imports
UploadedFile “1” --> “*” Transaction : source
User “1” --> “*” Transaction
Category “1” --> “*” Transaction : auto_category
Category “1” --> “*” Transaction : final_category
Transaction “1” --> “*” ClassificationResult
Category “1” --> “*” ClassificationResult
User “1” --> “*” ClassificationCache
Category “1” --> “*” ClassificationCache
User “1” --> “*” ReportJob
ReportJob “1” --> “*” GeneratedReport
User “1” --> “*” GeneratedReport
@enduml
```

### 10.2 分类器策略类图

用于第 6 章 §6.1.2，展示 Strategy + Chain of Responsibility + Facade 模式。

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false
skinparam classAttributeIconSize 0
hide circle

class ClassificationOutput <<dataclass>> {
  +category_id : int
  +confidence : decimal
  +reason : str
  +provider : str
}

class RuleBasedClassifier {
  +classify(transaction, db)
  -_match_pattern(text, pattern)
}

class OpenAICompatibleClassifier {
  +classify(transaction, db)
  -_build_prompt(transaction)
  -_call_model(messages)
  -_parse_response(response)
}

class LocalModelClassifier {
  +classify(transaction, db)
}

class CompositeClassifier {
  +classify(transaction, db)
  -_lookup_cache(text_hash)
  -_save_cache(text_hash, result)
  -_enqueue_external(transaction)
  -_rule_fallback(transaction)
}

LocalModelClassifier -up-|> OpenAICompatibleClassifier : 继承

CompositeClassifier --> RuleBasedClassifier : 规则兜底
CompositeClassifier --> OpenAICompatibleClassifier : API 调用
CompositeClassifier ..> ClassificationOutput : 输出

note right of CompositeClassifier
  Facade + Chain of Responsibility
  classify() 编排降级链路：
  缓存 → API → 规则
  外部模型异步入队重试池
end note
@enduml
```

### 10.3 解析器类图

用于第 6 章 §6.1.3，展示 Strategy + Adapter + Registry 模式。

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false
skinparam classAttributeIconSize 0
hide circle

class ParsedTransaction <<dataclass>> {
  +platform : str
  +occurred_at : datetime
  +type : str
  +amount : decimal
  +merchant : str
  +item : str
}

interface StatementParser {
  +parse(df) : list[ParsedTransaction]
}

class AlipayParser {
  +parse(df)
}

class WeChatParser {
  +parse(df)
}

class StatementReader {
  +read(file_path)
  -_detect_encoding()
  -_find_header_row()
}

class ParserRegistry {
  +parse_file(path)
  -_detect_platform_hint()
  -_ordered_parsers()
}

class TransactionNormalizer {
  +normalize(tx)
  +build_dedupe_hash(tx)
}

AlipayParser ..|> StatementParser
WeChatParser ..|> StatementParser
ParserRegistry --> StatementReader
ParserRegistry --> StatementParser
ParserRegistry --> TransactionNormalizer

note right of ParserRegistry
  Registry / Factory
  检测平台 → 选择解析器
end note

note right of StatementReader
  Adapter：封装 pandas
  编码检测 + 表头定位
@end note
@enduml
```

### 10.4 报表构建器类图

用于第 6 章 §6.1.4，展示 Builder 模式。

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false
skinparam classAttributeIconSize 0
hide circle

class ReportBuilder {
  +build(db, user_ids, job, title)
  -_resolve_unicode_font()
  -_configure_pdf_font(pdf)
  -_add_cover(pdf, title, context)
  -_section_title(pdf, title, subtitle?)
  -_metric_row(pdf, metrics)
  -_simple_table(pdf, headers, rows)
  -_group_transactions(txs, categories)
  -_build_context(db, user_ids, ...)
}

class FPDF <<fpdf2>> {
  +add_page()
  +set_font()
  +cell()
  +multi_cell()
  +output()
}

class GeneratedReport <<ORM>> {
  +id : int
  +user_id : int
  +job_id : int
  +title : str
  +file_path : str
}

ReportBuilder --> FPDF : 渲染 PDF
ReportBuilder --> GeneratedReport : 写入记录

note right of ReportBuilder
  Builder 模式
  build() 编排步骤：
  ① _build_context 聚合数据
  ② _add_cover 封面
  ③ _section_title + _metric_row 摘要
  ④ _simple_table 分类/商户表
  ⑤ 逐分类明细页
  ⑥ 保存 → GeneratedReport
end note
@enduml
```

## 11. 对象图

用于第 6 章“面向对象组织方式”。对象图只展示家庭聚合场景，不把所有交易对象都摊开。

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false

object "owner:User" as U1 {
  id = 1
}

object "member:User" as U2 {
  id = 2
}

object "org:Organization" as Org {
  id = 10
  name = 我的家庭
}

object "ownerMembership" as OM1 {
  role = owner
}

object "memberMembership" as OM2 {
  role = member
}

object "tx1:Transaction" as Tx1 {
  user_id = 1
  amount = 100
}

object "tx2:Transaction" as Tx2 {
  user_id = 2
  amount = 200
}

object "familySummary" as Summary {
  user_ids = [1, 2]
}

object "familyPersonality" as Profile {
  organization_id = 10
}

U1 -- OM1
U2 -- OM2
OM1 -- Org
OM2 -- Org
U1 -- Tx1
U2 -- Tx2
Org -- Summary
Org -- Profile
Tx1 -- Summary
Tx2 -- Summary
Tx1 -- Profile
Tx2 -- Profile
@enduml
```

## 12. 账单导入与大模型初分顺序图

用于第 6 章“核心顺序设计”。用 `box` 分组，减少参与者横向散乱。

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false
skinparam sequenceMessageAlign center
autonumber

actor 用户 as User

box "Frontend" #EEF2FF
participant "ImportsPage" as FE
end box

box "Backend" #ECFDF5
participant "Imports API" as API
participant "ImportService" as IS
participant "ParserRegistry" as PR
participant "TransactionNormalizer" as NM
participant "CompositeClassifier" as CC
end box

box "Data & External" #FFF7ED
database "Database" as DB
participant "RetryQueue" as RQ
participant "Model Provider" as MP
end box

User -> FE : 上传微信/支付宝账单
FE -> API : POST /api/imports
API -> IS : 创建批次并保存文件
IS -> DB : 写入 ImportBatch / UploadedFile
IS -> PR : 选择账单解析器
PR --> IS : 标准化前交易记录
IS -> NM : 规范化字段并生成 dedupe_hash
NM --> IS : 统一交易结构
IS -> DB : 去重并写入 Transaction
IS -> CC : classify(transaction)

alt 命中规则或缓存
  CC -> DB : 查询规则/缓存
  DB --> CC : 分类结果
else 需要外部模型
  CC -> RQ : 写入 retry_queue
  RQ --> CC : 返回排队状态
  RQ -> MP : 后台串行请求模型
  MP --> RQ : 返回分类结果
  RQ -> DB : 更新分类结果和交易状态
end

CC --> IS : 分类、置信度、理由
IS -> DB : 写入 ClassificationResult
IS --> API : 导入结果
API --> FE : 批次状态和处理数量
FE --> User : 展示导入进度与待校正交易
@enduml
```

## 13. 家庭聚合查询顺序图

新增图，可用于第 6 章或作为家庭组织功能补充图。若报告篇幅紧张，可以不放，正文引用组件图和活动图即可。

```plantuml
@startuml
skinparam backgroundColor transparent
skinparam shadowing false
skinparam sequenceMessageAlign center
autonumber

actor "家庭成员" as User

box "Frontend" #EEF2FF
participant "OrganizationPage" as FE
end box

box "Backend API" #ECFDF5
participant "Organizations API" as ORG
participant "Dashboard API" as DASH
participant "Personality API" as PERS
end box

box "Services" #F8FAFC
participant "OrganizationService" as OS
participant "AnalyticsService" as AS
participant "PersonalityService" as PS
end box

database "Database" as DB

User -> FE : 进入家庭组织页
FE -> ORG : GET /api/organizations
ORG -> OS : get_organizations_for_user(user_id)
OS -> DB : 查询 OrganizationMember
DB --> OS : 组织与角色
OS --> ORG : 组织列表
ORG --> FE : organizations

FE -> DASH : GET /api/dashboard/summary?organization_id=10
DASH -> OS : verify_org_membership()
OS -> DB : 查询成员身份与 user_id
DB --> OS : user_ids=[1,2,...]
DASH -> AS : dashboard_summary(user_ids)
AS -> DB : 聚合家庭交易
DB --> AS : 聚合结果
AS --> DASH : DashboardSummary
DASH --> FE : 家庭财务概览

FE -> PERS : GET /api/personality/profile?organization_id=10
PERS -> OS : verify_org_membership()
OS --> PERS : user_ids=[1,2,...]
PERS -> PS : compute_personality_profile(user_ids)
PS -> DB : 查询家庭成员交易
DB --> PS : transactions
PS --> PERS : 家庭人格与财务健康
PERS --> FE : family personality
@enduml
```

## 14. 页面截图组

用于第 4 章“主要页面原型”。这部分不建议画页面导航图，直接放截图即可。

建议截图顺序：

1. 登录/注册页
2. Dashboard 财务驾驶舱
3. 导入账单页
4. 交易列表页
5. 分类校正工作台
6. 分类管理页
7. 消费人格页
8. 家庭组织页
9. 报表中心
10. 系统设置页

截图说明重点：

- Dashboard 展示个人统计口径。
- 消费人格页展示个人消费人格、财务健康和问卷自评。
- 家庭组织页展示 owner/admin/member 角色、家庭成员列表、家庭财务概览和家庭消费人格。
- 报表中心说明个人报表和家庭聚合报表共用报表生成能力。

## 15. 不再绘制的图

以下图与新版主流程或其他图功能重合，建议继续不画：

- 页面导航图：由截图组和活动图覆盖。
- 用户旅程图：由用户场景文字和活动图覆盖。
- 登录顺序图：认证流程较常规，报告重点不在此。
- 报表顺序图：可由组件图、活动图和接口设计说明覆盖。
- 安全边界图：和总体架构图高度重合。
- 性能请求链路图：用性能瓶颈表说明即可。
