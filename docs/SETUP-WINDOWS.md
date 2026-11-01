# Windows 开发环境搭建

目标：在新 Windows 电脑上克隆本仓库，跑通 D1 六项检查。

## 0. 前提

- Windows 10/11 64 位，建议 16 GB 内存、**20 GB 以上空闲磁盘**（Docker 镜像 + ERPNext 数据库约 6–8 GB）
- 使用同一个 GitHub 账号（`Ethanwu23`），仓库是私有
- 不需要 Node.js（V1 后端只用标准库 Python）

## 1. 安装三个工具

| 工具 | 版本 | 注意 |
|---|---|---|
| Git for Windows | 最新 | 自带 Git Bash，可选 |
| Python | 3.12.x | 安装时勾选 **Add python.exe to PATH** |
| Docker Desktop | 最新 | 勾选 **Use WSL 2 based engine**；首次启动会提示安装 WSL 更新 |

验证：

```powershell
git --version
python --version
docker version
```

## 2. 克隆仓库

私有仓库需要先登录，二选一：

```powershell
# 方式 A：GitHub CLI
gh auth login

# 方式 B：浏览器生成 PAT（repo 权限），克隆时当密码用
git clone https://github.com/Ethanwu23/bridge-erp.git
```

```powershell
cd bridge-erp
```

## 3. 先做不依赖 ERP 的自检

```powershell
python scripts\d1_check.py --mode mock
python tests\test_metrics.py
python tests\test_http_and_paging.py
```

预期：D1 为 **3 项 PASS、3 项 SKIP**，两个测试脚本输出 `all tests passed`。这一步不通过就先别装 Docker。

## 3.5 安装依赖并启动 API

```powershell
python -m pip install -r requirements.txt
uvicorn --app-dir services/api bridge.app:app --port 8000 --reload
```

另开一个终端验证：

```powershell
curl.exe -s -X POST http://127.0.0.1:8000/api/v1/query -H "Content-Type: application/json" -d '{"question":"10月回款率是多少"}'
```

应返回 `collection_rate` 与 `0.5818...`。

> 若公司网络装不了依赖，可用零依赖 demo：`python scripts\serve_demo.py --port 8000`，接口一致。

## 4. 启动 ERPNext

```powershell
cd ..
git clone https://github.com/frappe/frappe_docker.git
cd frappe_docker
docker compose -f pwd.yml up -d
docker compose -f pwd.yml logs -f create-site
```

等到日志出现站点创建完成，浏览器打开 <http://localhost:8080>，账号 `Administrator` / `admin`。

首次登录必须完成 **Setup Wizard**：

1. 语言、国家、时区
2. 公司名（如 `Bridge Demo`）、本位币 `CNY`
3. 科目表选标准模板
4. 完成

没有这一步，发票和收付款没有科目可挂，后续建单会失败。

## 5. 生成 API Token

**用户 → Administrator → API Access → Generate Keys**，`secret` 只显示一次，记下来。

```powershell
$env:ERP_KEY="<api_key>"
$env:ERP_SECRET="<api_secret>"

curl.exe -H "Authorization: token $env:ERP_KEY`:$env:ERP_SECRET" `
  "http://localhost:8080/api/resource/Sales%20Invoice?limit_page_length=1"
```

返回 `{"data": []}` 即连通。

## 6. 灌种子数据

数据规格见 [开工检查](READY-v0.1.md) 第 4 节：7 张发票（含 1 张退货负数、1 张跨期）、4 笔回款（含部分收款）、5 笔订单。

当前需在 UI 手工录入，顺序：

1. 建 3 个客户：C1 华东-制造、C2 华东-贸易、C3 华南-服务
2. 建 5 个物料：A–E，非库存、可销售
3. 录入 7 张销售发票并提交，登记 4 笔收款
4. 录入 5 笔销售订单并提交（10 月）

录完抽查两张发票的 `outstanding_amount`，确认与规格一致。

## 7. 配置 DeepSeek

```powershell
$env:DEEPSEEK_API_KEY="sk-..."
```

如需持久化：`setx DEEPSEEK_API_KEY "sk-..."`（新开终端生效）。

## 8. 跑完整 D1

```powershell
cd bridge-erp
python scripts\d1_check.py --mode http `
  --base-url http://localhost:8080 `
  --key $env:ERP_KEY --secret $env:ERP_SECRET
```

六项应全部 PASS（第 5 项要求已设置 Key）。

## 9. 常见问题

| 现象 | 处理 |
|---|---|
| 8080 端口被占用 | 改 `pwd.yml` 里 frontend 的端口映射，如 `8081:8080` |
| `docker compose` 拉镜像很慢 | 配置 Docker Desktop 的 registry mirror |
| PowerShell 中文乱码 | 先执行 `chcp 65001` |
| 换行符导致脚本异常 | 仓库已配置 `.gitattributes`，克隆后保持 LF 即可 |
| WSL 占内存过多 | 在 `%UserProfile%\.wslconfig` 设 `memory=6GB` 后 `wsl --shutdown` |
| `python` 指向 Microsoft Store | 安装时勾选 PATH，或在「应用执行别名」里关闭 python 别名 |
