from __future__ import annotations

from dataclasses import dataclass

from app.improvements.models import ImprovementStatus


@dataclass(frozen=True)
class DefaultImprovementLog:
    log_id: str
    issue: str
    resolution: str
    status: ImprovementStatus = "resolved"
    related_question: str | None = None


DEFAULT_IMPROVEMENT_LOGS: tuple[DefaultImprovementLog, ...] = (
    DefaultImprovementLog(
        log_id="builtin-layout-overlap",
        issue="前端工作台各板块在分析结果较多时互相遮挡。",
        resolution="重构工作台三栏布局，给数据预览、执行时间线、图表结果和报告区设置独立滚动边界与稳定宽度，避免运行后内容覆盖。",
        related_question="前端各个板块做好分割，运行之后各个板块的结果会互相遮挡。",
    ),
    DefaultImprovementLog(
        log_id="builtin-top-profit-product",
        issue="询问利润最高的商品名称时，系统返回数值描述统计，无法回答具体商品。",
        resolution="新增 top_records 意图识别和 DuckDB 排序查询路径，按利润字段真实排序并返回商品名称、利润和证据表。",
        related_question="利润最高的商品名称是什么",
    ),
    DefaultImprovementLog(
        log_id="builtin-market-recommendation",
        issue="市场建议类问题被错误降级为描述统计，不能形成有证据的扩张建议。",
        resolution="新增 market_recommendation 分析路径，用城市、品类、销售额、利润和利润率生成候选市场表，并在报告中标记数据范围和外推风险。",
        related_question="上海那类商品的市场建议扩大",
    ),
    DefaultImprovementLog(
        log_id="builtin-dataset-overview",
        issue="数据集概览问题被误判为分组统计，不能直接回答订单数、字段数和日期范围。",
        resolution="新增 dataset_overview 固定操作，读取真实行数、列数、字段列表和时间范围，避免无关图表替代答案。",
        related_question="这个数据集有多少条订单、多少个原始字段？日期范围是什么？",
    ),
    DefaultImprovementLog(
        log_id="builtin-data-quality",
        issue="数据质量问题被误判为普通数值描述统计。",
        resolution="新增 data_quality 意图和 pandas 质量扫描，覆盖缺失、重复、负值、零金额、公式一致性和业务键重复，并输出质量明细表。",
        related_question="数据质量有哪些明显问题？",
    ),
    DefaultImprovementLog(
        log_id="builtin-saas-mrr-risk",
        issue="SaaS 经营类问题无法区分当前 MRR、累计 MRR 和高风险客户排名。",
        resolution="新增 MRR 口径识别、高风险客户排名、月份过滤和回归评测用例，确保 SaaS 指标按真实字段计算。",
        related_question="当前 MRR 与累计 MRR 的口径区分。12 月高风险客户和高风险 MRR 排名。",
    ),
    DefaultImprovementLog(
        log_id="builtin-business-template-routing",
        issue="账款风险、续约风险、客户成功、渠道、行业、商品 Pareto 等业务意图经常退回 numeric_describe。",
        resolution="新增统一 business_template_analysis 路由和 pandas 业务模板工具，批量覆盖 SaaS 与销售经营高频问题，并加入 agent_eval 批量回归。",
        related_question="账款风险与续约风险联动分析。",
    ),
    DefaultImprovementLog(
        log_id="builtin-log-page-hidden",
        issue="改进日志内容直接占用工作台页面，影响核心分析界面。",
        resolution="将改进日志独立成日志页面，只保留顶部“日志”按钮入口，点击后跳转查看和记录改进项。",
        related_question="把这个日志的内容隐藏，只有点击日志这个按钮才会跳转到日志界面。",
    ),
    DefaultImprovementLog(
        log_id="builtin-compound-question",
        issue="用户一次性提出多个分析问题时，系统只执行第一个分析操作，导致答案不完整。",
        resolution="新增复合问题拆分、AnalysisPlan 多操作规划和 multi_analysis 聚合执行结果；每个子问题分别调用 DuckDB SQL 或 pandas/scipy 真实执行，并在报告中列出子问题执行清单、结果表、图表和证据链。",
        related_question="一次性询问多个问题，并不能完整地回答。",
    ),
)
