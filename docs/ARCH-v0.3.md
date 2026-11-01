# Bridge 架构设计文档（V1 只读版）

| 项 | 内容 |
|---|---|
| 文档版本 | v0.3（待评审） |
| 日期 | 2026-11-01 |
| 对应 PRD | v0.5（开发基线） |
| 架构形态 | 单体 + 全 API 接入 |
| 部署形态 | 内部验证环境，Docker Compose（可平移到客户内网） |
| 团队 | 1 名全栈 |

## 1. 范围与约束

本文档回答"只读版怎么实现"：5 个指标、3 个对象、零写入，6 周 1 人交付。

| 约束 | 取值 | 来源 |
|---|---|---|
| ERP | ERPNext v16（可跟随客户 v15） | PRD 6.2 |
| 接入 | 仅 REST API；不直连库、不抓页面 | PRD 6.3 |
| 身份 | 每用户 API Token；可降级服务账号 | PRD 6.2 |
| 写入 | 无写接口 | PRD 3 |
| 指标 | 5 个：销售额、回款额、回款率、订单数、逾期应收 | PRD 13.2 |
| 规模 | 10 并发、10 个试用账号 | PRD 9 |
| 性能 | 查数 P95 ≤ 10s | PRD 9 |
| 资源 | 4C8G，Docker Compose | PRD 9 |
| 人力 | 1 人 × 6 周 = 24 有效人日 | 本方案 |

## 2. 架构原则

| # | 原则 | 含义 |
|---|---|---|
| 1 | 单体 | 一个进程，按模块分包，不拆服务 |
| 2 | 确定性优先 | LLM 只填槽位，绝不生成 SQL/URL |
| 3 | 能力即配置 | 5 个指标 = 5 个查询模板，改配置不改代码 |
| 4 | 不复制数据 | 只存语义、审计、缓存 |
| 5 | 治理内建 | 每次调用都带 trace_id，可回放 |
| 6 | 为 V1.1 留口 | 草稿引擎只预留接口，不实现 |

## 3. 总体架构

| 层 | 组件 | 职责 | 关键接口 |
|---|---|---|---|
| 交互 | Web 前端 | 对话、结果卡、明细、审计台 | REST/JSON |
| 应用 | API 服务 | 鉴权、限流、编排、错误处理 | `/api/v1/*` |
| 引擎 | 查询引擎 | 槽位解析、计划校验、执行、聚合 | 进程内模块 |
| 语义 | 语义仓库 | 3 对象、5 指标、5 模板、权限映射 | YAML + 数据库 |
| 接入 | ERP 适配器 | Token、REST 调用、分页、重试 | ERPNext REST API |
| 治理 | 审计 | trace/span 落库、脱敏 | 异步写入 |

### 3.1 组件清单

| 组件 | 技术 | 部署 | 说明 |
|---|---|---|---|
| bridge-web | React 18 + TypeScript + Ant Design 5 | nginx 静态托管 | 单页应用，支持企微内嵌 |
| bridge-api | Python 3.12 + FastAPI + SQLAlchemy 2 | uvicorn，2 worker | 单体模块化 |
| postgres | PostgreSQL 16 | 容器 | 语义、审计、缓存 |
| erpnext | 客户现有实例 | 外部 | 只读 API |

### 3.2 部署拓扑

```
验证环境（本地或客户内网）
  ├─ bridge-web   nginx :443 → :8080
  ├─ bridge-api   uvicorn :8000（仅容器网络）
  ├─ postgres     :5432（仅容器网络）
  └─ 出站 → https://erp.customer.local
```

### 3.3 资源预算

| 服务 | CPU | 内存 | 说明 |
|---|---|---|---|
| bridge-web | 0.5 核 | 0.5 GB | 静态资源与代理 |
| bridge-api | 2 核 | 2 GB | 含 LLM 调用 |
| postgres | 1.5 核 | 3 GB | 语义 + 审计 + 缓存 |
| 预留 | — | 2.5 GB | 系统与突发 |
| 合计 | 4 核 | 8 GB | 满足 10 并发 |

## 4. 核心流程

### 4.1 查数流程

| 步骤 | 组件 | 输入 | 输出 | 失败处理 |
|---|---|---|---|---|
| 1 | Web | 用户问题 | 请求体 | 前端提示重试 |
| 2 | API | 会话 JWT | 用户上下文 | 401 跳登录 |
| 3 | 查询引擎 | 问题 + 5 指标清单 | 槽位 JSON | 解析失败转澄清 |
| 4 | 校验器 | 槽位 JSON | 合法计划 | 非法则拒答 |
| 5 | 适配器 | 计划 + 用户 Token | ERP 原始数据 | 超时重试 1 次 |
| 6 | 查询引擎 | 原始数据 | 聚合结果 | 超上限提示缩小范围 |
| 7 | 查询引擎 | 结果 | 口径 + 缓存 | 缓存失败不影响返回 |
| 8 | API | 结果 + trace | 响应 + 审计 | 审计异步补写 |

### 4.2 回放流程

输入 trace_id → 读取 trace 与 span → 按时间序还原问题、计划、API 调用、结果 → 前端展示只读 JSON。

回放**不重新调用 ERP**，避免二次副作用。

## 5. 语义层设计

### 5.1 对象（3 个）

| 对象 | DocType | 用途 | 关键字段 |
|---|---|---|---|
| 销售订单 | Sales Order | 订单数、客户维度 | name、customer、transaction_date、grand_total、status |
| 销售发票 | Sales Invoice | 销售额、逾期应收 | name、customer、posting_date、grand_total、outstanding_amount、due_date |
| 回款 | Payment Entry | 回款额、回款率 | name、party、posting_date、paid_amount、payment_type |

客户（Customer）不单列对象，作为发票/订单上的维度字段使用。

### 5.2 指标定义

```yaml
code: collection_rate
name: 回款率
domain: sales
owner: 销售运营
version: 1
formula: "sum(payment.paid_amount) / sum(invoice.grand_total)"
grain: [month, region, customer]
dimensions: [region, customer, sales_person]
sources:
  - doctype: Payment Entry
    filters: {docstatus: 1, payment_type: Receive}
  - doctype: Sales Invoice
    filters: {docstatus: 1}
```

### 5.3 查询模板

```yaml
metric: collection_rate
params: [from, to, region?, customer?]
steps:
  - id: pay
    doctype: Payment Entry
    fields: [paid_amount, posting_date]
    filters: "posting_date between {from} and {to}"
  - id: inv
    doctype: Sales Invoice
    fields: [grand_total]
    filters: "posting_date between {from} and {to}"
aggregate: "sum(pay.paid_amount) / sum(inv.grand_total)"
drilldown:
  doctype: Sales Invoice
  fields: [name, customer, grand_total, outstanding_amount]
```

### 5.4 权限映射

| 层 | 规则 | 裁决方 |
|---|---|---|
| 对象级 | 角色 → 可访问对象 | Bridge 前置 |
| 字段级 | 角色 → 可见字段 | Bridge 前置 |
| 行级 | 用户 → 区域/客户范围 | ERPNext 最终 |

## 6. 查询引擎

### 6.1 意图解析

LLM 输出严格 JSON，只允许从 5 个指标中选择：

```json
{
  "metric": "collection_rate",
  "time": {"from": "2026-10-01", "to": "2026-10-31"},
  "filters": {"region": "华东"},
  "group_by": ["customer"]
}
```

### 6.2 计划校验

| 规则 | 处理 |
|---|---|
| 指标不在清单 | 拒答，给出最接近的候选 |
| 过滤值不在白名单 | 拒答，列出可选值 |
| 时间范围 > 24 个月 | 拒答，要求缩小 |
| 预计行数 > 5000 | 改用报表接口或要求加过滤 |
| 涉及写操作 | 直接拒绝（V1 无写能力） |

### 6.3 执行与聚合

- 按模板调用 API，统一分页（单页 100）。
- 聚合用 `Decimal`，避免浮点误差。
- 行数超限优先走 ERPNext 报表接口；不可用则返回"请缩小范围"。

### 6.4 缓存

| 项 | 设计 |
|---|---|
| Key | `hash(metric + 归一化参数 + 权限范围)` |
| TTL | 5 分钟 |
| 存储 | Postgres `cache_entry`，不引入 Redis |

### 6.5 拒答

未命中指标、维度不支持、时间超范围、涉及写操作——一律拒答并说明原因，记录到审计与评测集。

## 7. 治理与安全

| 项 | 设计 |
|---|---|
| 登录 | 企微 OAuth / SSO → 会话 JWT（2 小时） |
| Token | 每用户 API Token，AES-256-GCM 加密存储，仅请求期解密 |
| 密钥 | `BRIDGE_MASTER_KEY`（32 字节），不落库 |
| 降级 | 服务账号 + 行级过滤，审计标 `degraded_auth=true` |
| 审计 | trace/span append-only，每日哈希链 |
| 脱敏 | 手机号、邮箱掩码；成本、折扣按角色隐藏 |

## 8. 接口设计

### 8.1 内部 API

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/v1/auth/sso` | POST | 登录换会话 |
| `/api/v1/query` | POST | 提问，返回结果 + trace_id |
| `/api/v1/query/{trace_id}` | GET | 查询历史结果 |
| `/api/v1/audit/traces` | GET | 审计列表 |
| `/api/v1/audit/traces/{id}` | GET | 回放数据 |
| `/api/v1/health` | GET | 健康检查 |

### 8.2 ERPNext API

| 用途 | 端点形态 | 说明 |
|---|---|---|
| 列表查询 | `GET /api/resource/{DocType}` | filters、fields、分页 |
| 单据详情 | `GET /api/resource/{DocType}/{name}` | 明细与校验 |
| 计数 | `GET /api/method/frappe.client.get_count` | 订单数 |
| 报表 | `GET /api/method/frappe.desk.query_report.run` | 复杂聚合优先 |

具体路径以 v16 实际接口为准，差异只在适配器内消化。

### 8.3 错误码

| 码 | 含义 | 前端行为 |
|---|---|---|
| `E_AUTH` | 未登录/Token 失效 | 跳登录 |
| `E_NO_METRIC` | 指标未定义 | 展示候选指标 |
| `E_BAD_FILTER` | 过滤值非法 | 展示可选值 |
| `E_LIMIT` | 数据量超限 | 提示缩小范围 |
| `E_ERP` | ERP 调用失败 | 提示稍后重试 |
| `E_LLM` | 模型调用失败 | 提示重试 |

## 9. 数据设计

| 表 | 用途 | 关键字段 |
|---|---|---|
| `sem_object` | 对象语义 | code、doctype、fields、version |
| `sem_metric` | 指标定义 | code、yaml、owner、version、status |
| `sem_template` | 查询模板 | metric_id、params、steps、aggregate |
| `sem_permission` | 权限映射 | role、object、field_mask、row_scope |
| `app_user` | 用户与 Token | erp_user、token_cipher、degraded |
| `trace` / `span` | 审计 | id、user、question、plan、step、duration |
| `cache_entry` | 聚合缓存 | key、value、expires_at |

## 10. 非功能设计

| 项 | 设计 |
|---|---|
| 性能预算 | 槽位解析 2–3s、取数 1–4s、聚合 <0.3s、渲染 <0.3s，P95 ≤ 10s |
| 并发 | 10 并发，2 worker，单请求超时 30s |
| 限流 | 单用户 10 次/分钟；全局 60 次/分钟 |
| 重试 | ERP 只读调用超时重试 1 次，指数退避 |
| 降级 | 模型不可用 → 规则解析 5 个指标；ERP 不可用 → 明确报错 |

## 11. 技术选型与 ADR

| 编号 | 决策 | 选择 | 理由 |
|---|---|---|---|
| ADR-01 | 服务形态 | 单体 | 1 人 6 周，微服务只增加负担 |
| ADR-02 | 后端 | Python + FastAPI | LLM 生态成熟、迭代快 |
| ADR-03 | 查询 | 模板 + 槽位填充 | 模型不生成查询，准确率可控 |
| ADR-04 | 数据 | 不复制业务数据 | 权限天然、无同步成本 |
| ADR-05 | 前端 | React + Ant Design | 表格与表单开发快 |
| ADR-06 | 缓存 | Postgres 表 | 少一个组件少一处故障 |
| ADR-07 | 草稿 | V1 不做，仅留接口 | 7 人日以上，超出 24 人日预算 |

## 12. 演进路线

| 版本 | 内容 |
|---|---|
| V1.1 | 文本草稿（2 类单据）+ Excel 导出；指标扩到 10 个 |
| V1.2 | 图片抽取、PDF 导出、第二 ERP 适配器 |
| V2 | 受控写接口、多 Agent 编排、评测自动化 |

## 13. 风险与权衡

| 风险 | 影响 | 对策 |
|---|---|---|
| 5 个指标算不出来 | 产品价值不足 | 指标选定前逐条核对 API 可行性 |
| API 聚合受限 | 部分维度查不动 | 优先报表接口；模板内置行数上限 |
| 与客户权限模型差异 | 接真实客户时需适配 | 预留字段与行级映射，V1.1 再接真实实例 |
| 1 人单点 | 延期无缓冲 | 范围已最小化；W5 留作兜底 |
