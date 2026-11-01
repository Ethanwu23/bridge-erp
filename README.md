# 数桥 Bridge

> 让 ERP 的数据，被 AI 安全、准确地查出来。

数桥是一个**只读**的 ERP 数据问答层：把业务指标的口径固化成确定性模板，LLM 只负责把自然语言翻译成「指标 + 时间 + 过滤」，取数与聚合全部走模板。V1 只做 5 个销售指标，不写库、不抓页面、全程可回放。

- 目标系统：ERPNext v16（可跟随客户 v15）
- 接入方式：仅 REST API，每用户 Token
- 当前范围：销售额、回款额、回款率、订单数、逾期应收
- 人力 / 周期：1 人 / 6 周

## 为什么不是"另一个套壳 Copilot"

大模型直接生成查询，在 ERP 场景里准确率不可控。数桥反过来：**查询由模板决定，模型只填参数**。指标口径可评审、可版本化，答案能追到具体的 API 调用与数据范围。

## 目录

```
config/metrics/          5 个指标的确定性定义（JSON）
services/api/bridge/
  adapter/http_client.py ERPNext REST 适配器（Token、过滤、分页）
  adapter/mock.py        内存版 ERP，离线开发与测试
  metrics/engine.py      指标执行引擎（来源 → 聚合 → 公式）
scripts/d1_check.py      D1 六项开工检查
tests/                   指标正确性 / HTTP 契约 / 分页
docs/                    PRD、架构、开发计划、开工检查
ops/erpnext/             本地 ERPNext 环境与灌数步骤
```

## 快速开始

```bash
# 不依赖 ERP：跑指标引擎与 D1 检查
python scripts/d1_check.py --mode mock
python tests/test_metrics.py
python tests/test_http_and_paging.py

# 有 ERPNext 时（见 ops/erpnext/README.md）
python scripts/d1_check.py --mode http \
  --base-url http://localhost:8080 \
  --key <api_key> --secret <api_secret>
```

## D1 状态（2026-11-01）

| # | 检查项 | 结果 | 说明 |
|---|---|---|---|
| 1 | ERPNext 可达 | SKIP | 开发机无 Docker，未起实例 |
| 2 | API Token 可用 | SKIP | 同上 |
| 3 | 种子数据齐全 | PASS | mock 数据 7 发票 / 4 回款 / 5 订单 |
| 4 | 5 个指标取数 | PASS | 与期望值完全一致（含退货、跨期、部分收款） |
| 5 | DeepSeek JSON 调用 | SKIP | 未设置 `DEEPSEEK_API_KEY` |
| 6 | 配置与口径基线 | PASS | 5 指标 + 口径文档就位 |

补齐 Docker 与 API Key 后，重跑同一条命令即可。

## 文档

| 文档 | 说明 |
|---|---|
| [PRD](docs/PRD-v0.6.md) | 范围、场景、8 条 P0、验收标准 |
| [架构](docs/ARCH-v0.3.md) | 分层、流程、接口、ADR |
| [开发计划](docs/PLAN-v0.3.md) | 16 个任务、23 人日、需求追溯 |
| [开工检查](docs/READY-v0.1.md) | 三个阻塞项的闭环方案与种子数据 |
| [Windows 环境](docs/SETUP-WINDOWS.md) | 新机器克隆、装 Docker、起 ERPNext、跑通 D1 |

## 已知偏差

- 指标配置目前用 JSON（环境无 PyYAML），W2 迁 YAML + Schema 校验。
- 真实 ERPNext 的灌数脚本尚未实现：依赖 Setup Wizard 的科目配置，需实例可用后补；当前用 `adapter/mock.py` 提供等价数据。

## License

MIT
