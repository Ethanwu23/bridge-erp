# ERPNext 本地环境（D1 检查第 1、2 项）

## 1. 前置条件

- Docker Desktop 或 OrbStack（本机当前未安装，这是第 1 项 SKIP 的原因）
- 约 4 GB 空闲磁盘、4 GB 可用内存

## 2. 启动

官方 `frappe_docker` 的 `pwd.yml` 已把镜像固定在 `frappe/erpnext:v16.53.0`：

```bash
git clone https://github.com/frappe/frappe_docker
cd frappe_docker
docker compose -f pwd.yml up -d
docker compose -f pwd.yml logs -f create-site   # 等待建站完成
```

- 访问：<http://localhost:8080>
- 站点：`frontend`，管理员：`Administrator` / `admin`

## 3. 初始化（首次必做）

`pwd.yml` 只装应用，不建公司账套。首次登录后需完成 Setup Wizard：

1. 语言、国家、时区
2. Company：名称随意（如 `Bridge Demo`）、本位币 `CNY`
3. Chart of Accounts 选标准模板
4. 完成向导

没有这一步，发票与收付款没有科目可挂，创建会失败。

## 4. 生成 API Token

**用户 → Administrator → API Access → Generate Keys**，得到 `api_key` / `api_secret`。

```bash
curl -s -H "Authorization: token <key>:<secret>" \
  "http://localhost:8080/api/resource/Sales%20Invoice?limit_page_length=1"
```

返回 `{"data": []}` 即连通。

## 5. 灌入种子数据

种子数据的定义见《开工前置检查》第 4 节（7 张发票、4 笔回款、5 笔订单，含退货、跨期、部分收款）。

推荐顺序：

1. 先在 UI 建 3 个客户（C1 华东-制造、C2 华东-贸易、C3 华南-服务）与 5 个物料（A–E，非库存）
2. 用 REST 批量建单据，或直接在 UI 录入 7 张发票并登记 4 笔收款
3. 核对每家客户的 `outstanding_amount`，确保与第 4.3 节期望值一致

> 导入脚本尚未实现：真实实例的科目、税模板、价格表依赖 Setup Wizard 的结果，脚本需在实例可用后按实际配置生成。当前用 `adapter/mock.py` 提供等价数据，指标引擎已在 mock 上验证通过。

## 6. 验证

```bash
cd bridge
python scripts/d1_check.py --mode http \
  --base-url http://localhost:8080 \
  --key <key> --secret <secret>
```

第 1、2、3、4 项应从 SKIP 变为 PASS。
