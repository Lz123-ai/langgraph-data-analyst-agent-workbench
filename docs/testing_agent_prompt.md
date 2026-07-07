# 测试 LangGraph Data Analyst Agent Workbench 的提示词

你是负责验收 Agent 项目的高级测试 Agent。请对这个项目做端到端测试，不要只阅读代码。

目标：验证它是否是一个真正的 LangGraph 数据分析 Agent 工作台，而不是普通聊天包装器。重点检查 LangGraph 状态机、结构化 Agent State、工具调用、pandas/DuckDB 真实执行、SSE 流式事件、图表、Markdown 报告、AgentOps、批量评测和错误处理。

请按顺序执行：

1. 阅读 `README.md`、`AGENT_HANDOFF.md`、`docs/optimization_backlog.md` 和 `agent_eval/README.md`，理解项目结构与已知评测要求。
2. 安装依赖并启动项目：
   ```powershell
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   cd frontend
   npm install
   cd ..
   powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
   ```
3. 运行自动验证：
   ```powershell
   .venv\Scripts\python.exe -m pytest -q
   .venv\Scripts\python.exe agent_eval\run_batch_eval.py
   .venv\Scripts\python.exe agent_eval\enterprise_business_eval.py
   cd frontend
   npm run build
   cd ..
   ```
   期望：后端测试通过，基础批量评测通过，企业评测通过，前端构建通过。
4. 打开 `http://127.0.0.1:5173/` 做 UI 冒烟测试：
   - 上传 `samples/sales_sample.csv`。
   - 提问：`这个数据集有多少条订单、多少个原始字段？日期范围是什么？利润最高的商品名称是什么？数据质量有哪些明显问题？`
   - 检查是否拆分多个子问题，是否显示 LangGraph 执行节点、SSE 时间线、图表、结果表、Markdown 报告和追踪代码。
5. 做业务准确性测试：
   - `利润最高的商品名称是什么`
   - `上海哪类商品建议扩大市场`
   - `数据质量有哪些明显问题？`
   - `当前 MRR 与客户-月份累计 MRR 分别是多少？为什么不能混用？`
   - `2025年12月高续约风险客户有多少？对应 MRR 是多少？列出 MRR 最高的 20 个高风险客户。`
   - `当前总 Pipeline、加权 Pipeline、赢单金额是多少？按销售负责人排序。`
6. 重点判断：
   - 是否回答了用户真实问题，而不是退化为 `numeric_describe`。
   - 每条结论是否来自 DuckDB SQL 或 pandas/scipy 真实计算。
   - 多问题是否完整回答，不只执行第一个问题。
   - 图表、结果表、报告、SQL/pandas 追踪是否互相对应。
   - AgentOps 是否记录任务、Trace、Token 估算、成本估算和评测记录。
   - 日志页面是否能记录失败问题与解决措施。
   - 前端是否有遮挡、横向溢出、表格/图表错位。
7. 如果发现失败，请先写入改进日志，再新增或修改 `agent_eval/cases.json` 或 pytest 用例，最后修复代码并重新跑全部验证。

输出一份测试报告，包含：

- 环境与启动方式
- 自动测试结果
- UI 冒烟测试截图或文字结论
- 失败问题清单
- 每个失败的复现问题、预期、实际、原因判断
- 建议优先级
- 是否适合作为 Agent 开发岗位作品集项目
