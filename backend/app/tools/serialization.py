from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd


def to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def dataframe_to_records(df: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    frame = df.head(limit) if limit is not None else df
    return [to_jsonable(row) for row in frame.to_dict(orient="records")]
