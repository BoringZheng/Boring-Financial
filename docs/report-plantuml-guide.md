# Boring Financial 报告 PlantUML 绘图说明

本目录维护期末报告新增或重画图的 PlantUML 源码。所有文件均为单文件图，不依赖外部主题或网络资源，统一使用白色背景、深色文字和浅色模块填充。
图中启用了 PlantUML 内置的 Smetana 布局引擎，因此渲染时不要求单独安装 Graphviz。

## 导出方式

安装 PlantUML 后，在仓库根目录执行：

```bash
plantuml -charset UTF-8 -tpng docs/report-diagrams/*.puml
plantuml -charset UTF-8 -tsvg docs/report-diagrams/*.puml
```

将报告使用的 PNG 复制到 `docs/final-report-latex/figures/`。PNG 建议至少 1800 px 宽；若本地 LaTeX 环境稳定支持 SVG，也可转为 PDF 后插入。

## 图表清单

| 源文件 | 建议图题 | 报告位置 | 导出文件名 | 推荐尺寸 |
| --- | --- | --- | --- | --- |
| `usecase-overview.puml` | 系统模块级用例总览 | 第 3 章“用例建模”开头 | `usecase-overview.png` | `0.92\textwidth` |
| `usecase-auth.puml` | 用户认证与数据隔离模块用例图 | 功能需求模块 1 | `usecase-auth.png` | `0.78\textwidth` |
| `usecase-import.puml` | 账单导入与解析模块用例图 | 功能需求模块 2 | `usecase-import.png` | `0.88\textwidth` |
| `usecase-classification.puml` | 智能分类与重试模块用例图 | 功能需求模块 3 | `usecase-classification.png` | `0.92\textwidth` |
| `usecase-transactions.puml` | 交易、人工校正与分类管理模块用例图 | 功能需求模块 4 | `usecase-transactions.png` | `0.90\textwidth` |
| `usecase-analysis-report.puml` | 分析与报表模块用例图 | 功能需求模块 5 | `usecase-analysis-report.png` | `0.90\textwidth` |
| `usecase-organization.puml` | 家庭组织与聚合分析模块用例图 | 功能需求模块 6 | `usecase-organization.png` | `0.92\textwidth` |
| `usecase-operations.puml` | 系统配置与运维模块用例图 | 功能需求模块 7 | `usecase-operations.png` | `0.82\textwidth` |
| `architecture-overview.puml` | 系统总体运行时架构图 | 第 5 章“总体架构” | `architecture-overview.png` | `0.92\textwidth` |
| `billing-data-flow.puml` | 账单处理核心数据流图 | 第 5 章模块设计之后 | `billing-data-flow.png` | `0.96\textwidth` |
| `entity-domain-model.puml` | 领域实体类图 | 第 6 章“面向对象分析与设计” | `entity-domain-model.png` | `0.92\textwidth`，建议单独浮动页 |

另外维护两张对现有图的修正版：

| 源文件 | 建议图题 | 报告位置 | 导出文件名 |
| --- | --- | --- | --- |
| `component-overview.puml` | UML 组件图 | 第 5 章“前端架构/后端架构” | 渲染后替换 `UML组件图.png` |
| `deployment-overview.puml` | 系统部署图 | 第 5 章“部署架构” | 渲染后替换 `部署图.png` |

## 正文衔接说明

### 系统模块级用例总览

总览图只表达三类参与者与七个功能模块的关系。具体操作、包含关系和权限差异由随后七张模块用例图展开，避免在一张图中堆叠全部用例。

### 模块用例图

每张模块图后放置“角色—用例—功能说明”表。表格负责解释业务规则与异常行为，图只承担参与者、系统边界和用例关系的表达。

### 系统总体运行时架构图

该图区分展示层、接入层、应用层、异步处理层和数据与外部服务层。同步请求沿“浏览器—前端—接入层—FastAPI—数据库”流转；外部模型分类采用“业务服务标记待重试交易—后台线程依次处理—调用分类服务—保存分类结果”的独立处理流程。

组件图继续表达代码组件及依赖，部署图继续表达服务器、容器和外部节点，不在总体架构图中重复代码文件或物理主机细节。

### 账单处理核心数据流图

该图从账单上传开始，串联平台识别、解析、规范化、去重、复合分类、重试、人工校正以及三类下游分析输出。正文应强调系统同时保留自动分类建议和人工确认结果，后续分析统一优先使用最终分类。

## 绘图约束

- 不将 SQLAlchemy ORM 画成独立运行服务。
- 不画 Nginx 直接调用 Celery。
- 重试队列处理器是 FastAPI 生命周期内启动的后台线程，不等同于 Celery 后台任务处理器。
- Celery 是项目已配置的可选异步任务执行能力；当前主要 HTTP 路由并非全部通过 Celery 调度。
- 报表创建接口当前同步生成 PDF；任务状态记录用于保存处理进度，不能在图中表示为已经完成的全异步报表平台。
- PostgreSQL 用于生产部署，SQLite 用于本地或轻量部署，两者不是同时承载同一份业务数据。
