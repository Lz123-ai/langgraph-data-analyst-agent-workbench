from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerabilityIssue:
    reason: str
    suggestion: str
    category: str


def detect_answerability_issue(question: str) -> AnswerabilityIssue | None:
    """Reject requests that the local tabular execution layer cannot ground."""
    q = question.strip().lower()
    if not q:
        return AnswerabilityIssue(
            reason="问题为空，无法确定需要执行的数据分析。",
            suggestion="请说明希望分析的指标、维度或数据质量问题。",
            category="empty",
        )

    destructive_terms = [
        "delete all data",
        "drop table",
        "remove all files",
        "删除所有数据",
        "删库",
        "读取 c:/",
        "读取 c:\\",
        "read c:/",
        "win.ini",
        "/etc/passwd",
        "ignore all rules",
        "ignore previous",
        "忽略之前",
        "忽略规则",
    ]
    if any(term in q for term in destructive_terms):
        return AnswerabilityIssue(
            reason="该请求包含文件、系统或越权操作，不属于只读表格分析能力范围。",
            suggestion="请改为询问上传数据集中的字段、指标、分组、趋势或数据质量。",
            category="unsafe_or_prompt_injection",
        )

    prediction_terms = ["预测", "预估", "forecast", "predict", "next month", "下个月", "未来销售"]
    if any(term in q for term in prediction_terms):
        return AnswerabilityIssue(
            reason="当前工作台只执行描述性和诊断性分析，尚未配置可验证的预测模型与回测流程。",
            suggestion="可以先分析历史趋势；如需预测，请补充预测目标、时间粒度、训练窗口和评估指标。",
            category="prediction_not_supported",
        )

    causal_terms = ["因果", "导致", "cause", "causal", "impact of", "是否造成"]
    if any(term in q for term in causal_terms):
        return AnswerabilityIssue(
            reason="观察性表格分析最多能计算相关关系，不能仅凭相关性证明因果关系。",
            suggestion="可以改问相关性；如需因果结论，请提供实验设计、处理组/对照组或可识别的准实验条件。",
            category="causal_not_supported",
        )

    out_of_domain_terms = [
        "天气",
        "weather",
        "股票价格",
        "stock price",
        "新闻",
        "news today",
        "写一首诗",
        "write a poem",
    ]
    if any(term in q for term in out_of_domain_terms):
        return AnswerabilityIssue(
            reason="该问题需要上传数据集之外的实时信息或通用知识，当前 Agent 不访问外部数据源。",
            suggestion="请改为询问当前数据集能够支持的分析问题。",
            category="out_of_domain",
        )

    greetings = {"hello", "hi", "你好", "您好", "在吗"}
    if q in greetings:
        return AnswerabilityIssue(
            reason="当前输入没有包含数据分析目标。",
            suggestion="请指定指标、维度、时间范围或希望检查的数据质量问题。",
            category="no_analysis_objective",
        )
    return None
