from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from app.domain import AnalysisOperation, ExecutionResult

TemplateHandler = Callable[[pd.DataFrame, AnalysisOperation], tuple[ExecutionResult, str]]


@dataclass(frozen=True)
class BusinessTemplateSpec:
    template_id: str
    handler: TemplateHandler
    description: str


class BusinessTemplateRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, BusinessTemplateSpec] = {}

    def register(self, template_id: str, handler: TemplateHandler, description: str) -> None:
        if template_id in self._templates:
            raise ValueError(f"Duplicate business template: {template_id}")
        self._templates[template_id] = BusinessTemplateSpec(template_id, handler, description)

    def execute(
        self,
        template_id: str | None,
        df: pd.DataFrame,
        operation: AnalysisOperation,
    ) -> tuple[ExecutionResult, str]:
        spec = self._templates.get(template_id or "")
        if spec is None:
            raise ValueError(f"未支持的业务分析模板：{template_id}")
        return spec.handler(df, operation)

    def list_specs(self) -> list[BusinessTemplateSpec]:
        return sorted(self._templates.values(), key=lambda item: item.template_id)
