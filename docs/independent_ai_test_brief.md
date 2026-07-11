# 独立 AI 测试任务书

## 1. 任务信息

| 项目 | 内容 |
| --- | --- |
| 项目名称 | LangGraph Data Analyst Agent Workbench |
| 测试类型 | 独立功能测试、Agent 质量评测、可靠性验证与轻量安全审查 |
| 测试目标 | 判断项目是否达到可公开发布、可供小团队试用的 Agent 工程质量 |
| 被测版本 | GitHub `main` 分支最新提交；报告中必须记录 commit SHA |
| 预计投入 | 核心验证 60–90 分钟；探索性测试可额外投入 30–60 分钟 |

## 2. 测试原则

1. **独立性**：从干净克隆或隔离工作目录开始；不要依赖作者本机数据库、上传文件、Node/Python 缓存或运行中服务。
2. **证据优先**：不得只阅读代码下结论。每个结论必须附命令输出、HTTP 响应、截图、Trace 或可复现步骤。
3. **不修改实现**：本任务默认只测试和报告。除非任务发起人明确授权，不提交业务代码修改。
4. **最小数据原则**：仅使用仓库中的合成样例数据或测试者自行构造的非敏感数据。
5. **密钥隔离**：不要索取、粘贴、记录或输出项目所有者的 API Key、`.env`、访问 Token、真实用户数据或私有企业评测数据。

## 3. 被测范围

### 必测范围

- CSV/Excel 上传、预览、数据画像和删除。
- LangGraph 工作流：问题理解、计划、DuckDB/pandas/scipy 执行、图表、洞察、复核和报告。
- 不支持问题的拒绝行为：预测、因果、外部知识、字段缺失等。
- SSE 事件、任务取消、失败/取消后重试、重启后中断任务恢复。
- AgentOps：任务状态、Trace、Token/成本、规则节点载荷、评测记录。
- 本地、Token、OIDC/JWT 鉴权边界及 tenant/user 资源隔离。
- Docker Compose 构建、容器健康检查、前端冒烟。
- 公开回归评测、后端测试、前端测试、浏览器 E2E。

### 明确不在本轮范围

- 使用项目所有者的真实模型 Key 进行在线调用。
- 私有企业评测原始数据；它不在公开仓库中。
- 多副本 PostgreSQL、对象存储、Redis 队列和 LangGraph checkpoint 的生产迁移。
- 渗透测试、DDoS 压测或任何可能影响外部服务的攻击性测试。

## 4. 环境准备

```powershell
git clone https://github.com/Lz123-ai/langgraph-data-analyst-agent-workbench.git
cd langgraph-data-analyst-agent-workbench

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

cd frontend
npm ci
cd ..
```

默认保持 `USE_LLM=false`。规则模式是公开 CI 和本任务的标准验证路径。

如需验证 LLM Provider，只能使用测试者自有的临时 Key，并在报告中仅记录 Provider、模型名、时间、耗时和结果，绝不记录 Key。

## 5. 必执行验证清单

### A. 构建与静态质量

```powershell
.\.venv\Scripts\python.exe -m ruff check backend\app agent_eval
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m coverage run -m pytest -q
.\.venv\Scripts\python.exe -m coverage report --fail-under=75

cd frontend
npm test
npm run build
npm audit --audit-level=high
cd ..
```

### B. Agent 回归与业务正确性

```powershell
.\.venv\Scripts\python.exe agent_eval\run_batch_eval.py
```

预期：公开评测 18/18 通过。重点检查：

- 结果是否回答实际问题，而非泛化描述。
- 数值、排序、范围和维度是否来自真实计算。
- 预测、因果和无关问题是否明确拒绝。
- 结论是否与结果表、SQL 或 pandas/scipy 方法一致。

企业评测仅在测试者已合法获得该数据集时执行：

```powershell
.\.venv\Scripts\python.exe agent_eval\enterprise_business_eval.py --data-dir <dataset-directory>
```

数据不存在时，记录为 **Not Run（私有数据不可用）**，不是失败，也不是通过。

### C. 浏览器端到端验证

```powershell
cd frontend
npm run test:e2e
cd ..
```

额外手工验证：

1. 启动 `scripts\start-dev.ps1`，打开前端。
2. 上传 `samples/sales_sample.csv`。
3. 分别提问：
   - `按 region 统计 sales 最高的地区，并生成图表和报告`
   - `分析 sales 和 profit 的相关性`
   - `检测 profit 的异常值`
   - `预测下个月销售额`
4. 检查 SSE 时间线、图表、结果表、报告、错误提示与页面布局。
5. 打开 AgentOps，检查任务、Trace、Token、成本、评测记录。

### D. 安全与权限验证

至少确认：

- 未提供 Token 时，受保护接口拒绝访问（Token/OIDC 模式）。
- 一个 tenant/user 无法读取另一个 tenant/user 的数据集、任务、SSE、AgentOps 或用户改进日志。
- `/api/ops/model-status` 不返回 API Key。
- 上传路径、超大文件、非 CSV/Excel 文件被安全处理。
- 不执行任意 SQL、任意 Python 或系统命令。

### E. 可靠性与部署验证

```powershell
.\scripts\verify-docker.ps1
```

检查：

- Compose 配置可解析，前后端镜像可构建。
- 后端容器达到 Healthy，前端 HTTP 返回 200。
- 失败或取消任务可通过 `POST /api/analysis/tasks/{task_id}/retry` 使用同一 Task ID 重试。
- 服务重启后的未完成任务产生 `task_resumed` 事件并安全重新执行。

## 6. 缺陷分级标准

| 级别 | 定义 | 示例 |
| --- | --- | --- |
| P0 阻断 | 数据泄露、密钥泄露、越权、任意代码执行、主流程完全不可用 | 跨租户读取上传文件；公开提交真实 Key |
| P1 高 | 核心分析结果错误、任务丢失、Docker/CI 持续失败、主要页面不可用 | 排序/金额错误；任务无法恢复；公开评测失败 |
| P2 中 | 功能降级、错误提示不清晰、边缘场景失败、明显 UX 缺陷 | SSE 断线后无法提示重连；字段缺失信息不明确 |
| P3 低 | 文案、样式、非关键性能或可维护性建议 | 文案不一致；空状态布局可优化 |

## 7. 测试报告交付模板

```markdown
# 独立测试报告

## 1. 基本信息
- 测试日期：
- 测试者 / 模型：
- 操作系统与版本：
- Python / Node / Docker 版本：
- 被测 commit SHA：
- 是否使用真实 LLM：否 / 是（仅 Provider 和模型名）

## 2. 执行摘要
- 结论：PASS / CONDITIONAL PASS / FAIL
- P0：
- P1：
- P2：
- P3：

## 3. 验证结果
| 项目 | 命令或操作 | 结果 | 证据 |
| --- | --- | --- | --- |
| 后端测试 |  |  |  |
| 覆盖率 |  |  |  |
| 公开 Agent 评测 |  |  |  |
| 前端测试/构建 |  |  |  |
| E2E |  |  |  |
| Docker |  |  |  |
| 企业评测 | Passed / Failed / Not Run |  |  |

## 4. 缺陷明细
### [P?] 标题
- 影响：
- 前置条件：
- 复现步骤：
- 预期结果：
- 实际结果：
- 证据：日志、截图、请求/响应（必须脱敏）
- 建议修复方向：

## 5. Agent 质量评价
- Grounding：
- 安全拒绝：
- 工具路由：
- 报告可读性：
- 可靠性与可观测性：

## 6. 发布建议
- [ ] 建议公开发布
- [ ] 修复 P1 后发布
- [ ] 存在 P0/P1 阻断，不建议发布
```

## 8. 通过标准

满足以下条件可给出 **PASS**：

1. 后端、前端、公开 Agent 评测、E2E、Docker 全部通过。
2. 无 P0/P1 安全或正确性问题。
3. 关键报告中的结论可追溯到真实数据和执行结果。
4. 文档能让陌生开发者在干净环境完成启动与验证。

允许企业评测在无私有数据时标记为 **Not Run**，但不得将其计为通过。
