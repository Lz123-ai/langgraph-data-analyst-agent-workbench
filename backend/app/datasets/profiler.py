from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.domain import ColumnProfile, DataGrainProfile, DatasetProfile, LogicalType
from app.tools.serialization import to_jsonable


def profile_dataframe(df: pd.DataFrame, dataset_id: str | None = None) -> DatasetProfile:
    columns = [_profile_column(df[column], column, len(df)) for column in df.columns]
    numeric_columns = [column.name for column in columns if column.logical_type == "numeric"]
    categorical_columns = [column.name for column in columns if column.logical_type in {"categorical", "text"}]
    datetime_columns = [column.name for column in columns if column.logical_type == "datetime"]
    boolean_columns = [column.name for column in columns if column.logical_type == "boolean"]
    return DatasetProfile(
        dataset_id=dataset_id,
        row_count=int(len(df)),
        column_count=int(len(df.columns)),
        columns=columns,
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        datetime_columns=datetime_columns,
        boolean_columns=boolean_columns,
        grain=_infer_grain(df, columns),
        generated_at=datetime.now(timezone.utc),
    )


def _profile_column(series: pd.Series, name: str, row_count: int) -> ColumnProfile:
    logical_type = _infer_logical_type(series)
    missing_count = int(series.isna().sum())
    missing_rate = float(missing_count / row_count) if row_count else 0.0
    non_null = series.dropna()
    unique_count = int(non_null.nunique(dropna=True))
    sample_values = [to_jsonable(value) for value in non_null.head(5).tolist()]
    base: dict[str, Any] = {
        "name": name,
        "dtype": str(series.dtype),
        "logical_type": logical_type,
        "missing_count": missing_count,
        "missing_rate": round(missing_rate, 4),
        "unique_count": unique_count,
        "sample_values": sample_values,
    }

    if logical_type == "numeric":
        numeric = pd.to_numeric(series, errors="coerce").dropna()
        if not numeric.empty:
            q1 = numeric.quantile(0.25)
            q3 = numeric.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outlier_count = int(((numeric < lower) | (numeric > upper)).sum())
            base.update(
                {
                    "min": to_jsonable(numeric.min()),
                    "max": to_jsonable(numeric.max()),
                    "mean": to_jsonable(numeric.mean()),
                    "std": to_jsonable(numeric.std()),
                    "q1": to_jsonable(q1),
                    "q3": to_jsonable(q3),
                    "outlier_count": outlier_count,
                }
            )
    elif logical_type == "datetime":
        parsed = pd.to_datetime(series, errors="coerce", format="mixed").dropna()
        if not parsed.empty:
            base.update({"min": to_jsonable(parsed.min()), "max": to_jsonable(parsed.max())})
    else:
        top_values = non_null.astype(str).value_counts().head(5).reset_index()
        top_values.columns = ["value", "count"]
        base["top_values"] = [
            {"value": to_jsonable(row["value"]), "count": int(row["count"])}
            for _, row in top_values.iterrows()
        ]

    return ColumnProfile(**base)


def _infer_logical_type(series: pd.Series) -> LogicalType:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    non_null = series.dropna()
    if non_null.empty:
        return "unknown"

    sample = non_null.astype(str).head(100)
    parsed_dates = pd.to_datetime(sample, errors="coerce", format="mixed")
    if parsed_dates.notna().mean() >= 0.8:
        return "datetime"

    unique_ratio = non_null.nunique(dropna=True) / max(1, len(non_null))
    if unique_ratio <= 0.5 or non_null.nunique(dropna=True) <= 30:
        return "categorical"
    return "text"


def _infer_grain(df: pd.DataFrame, columns: list[ColumnProfile]) -> DataGrainProfile:
    row_count = int(len(df))
    id_columns = _candidate_id_columns(df.columns)
    time_columns = _candidate_time_columns(columns)
    primary_key_candidates: list[list[str]] = []
    notes: list[str] = []

    for column in id_columns:
        if df[column].notna().all() and int(df[column].nunique(dropna=True)) == row_count:
            primary_key_candidates.append([column])

    for id_column in id_columns:
        for time_column in time_columns:
            key_columns = [id_column, time_column]
            if _non_null_unique_key(df, key_columns):
                primary_key_candidates.append(key_columns)

    order_key = _first_named_key(id_columns, ["订单", "order"])
    customer_key = _first_named_key(id_columns, ["客户", "customer"])
    if order_key:
        grain_columns = [order_key]
    elif customer_key and time_columns:
        grain_columns = [customer_key, time_columns[0]]
    else:
        grain_columns = primary_key_candidates[0] if primary_key_candidates else []

    if not grain_columns and id_columns:
        best = min(id_columns, key=lambda column: row_count - int(df[column].nunique(dropna=True)))
        grain_columns = [best]

    duplicate_key_count = _duplicate_key_count(df, grain_columns)
    time_field = time_columns[0] if time_columns else None
    time_range = _time_range(df, time_field)

    lower_names = " ".join(str(column).lower() for column in df.columns)
    if any(keyword in lower_names for keyword in ["订单id", "订单编号", "order id", "order_id"]):
        grain_type = "订单流水"
        notes.append("检测到订单标识字段，默认按订单明细理解。")
    elif any(keyword in lower_names for keyword in ["客户id", "customer id", "customer_id"]) and time_field:
        grain_type = "客户-时间快照"
        notes.append("检测到客户标识和时间字段，默认按客户-时间记录理解，不等同于客户唯一粒度。")
    elif grain_columns:
        grain_type = "明细记录"
        notes.append(f"候选主键：{'+'.join(grain_columns)}。")
    else:
        grain_type = "未知粒度"
        notes.append("未识别稳定主键，涉及去重或客户数时需要显式确认口径。")

    if duplicate_key_count:
        notes.append(f"候选粒度字段存在 {duplicate_key_count} 条重复记录。")
    if time_field and time_range:
        notes.append(f"时间字段 {time_field} 范围为 {time_range.get('min')} 至 {time_range.get('max')}。")

    return DataGrainProfile(
        grain_type=grain_type,
        grain_columns=grain_columns,
        primary_key_candidates=primary_key_candidates[:5],
        time_field=time_field,
        time_range=time_range,
        duplicate_key_count=duplicate_key_count,
        notes=notes,
    )


def _candidate_id_columns(columns: pd.Index) -> list[str]:
    keywords = [
        "id",
        "_id",
        "编号",
        "编码",
        "订单号",
        "客户号",
        "用户号",
        "order_id",
        "customer_id",
        "user_id",
    ]
    return [str(column) for column in columns if any(keyword in str(column).lower() for keyword in keywords)]


def _candidate_time_columns(columns: list[ColumnProfile]) -> list[str]:
    name_keywords = ["日期", "时间", "月份", "统计月", "month", "date", "time"]
    logical_matches = [column.name for column in columns if column.logical_type == "datetime"]
    name_matches = [column.name for column in columns if any(keyword in column.name.lower() for keyword in name_keywords)]
    return list(dict.fromkeys([*logical_matches, *name_matches]))


def _first_named_key(columns: list[str], keywords: list[str]) -> str | None:
    for column in columns:
        column_lower = column.lower()
        if any(keyword.lower() in column_lower for keyword in keywords):
            return column
    return None


def _non_null_unique_key(df: pd.DataFrame, columns: list[str]) -> bool:
    if not columns or any(column not in df.columns for column in columns):
        return False
    key_frame = df[columns]
    if key_frame.isna().any(axis=None):
        return False
    return int(key_frame.drop_duplicates().shape[0]) == int(len(df))


def _duplicate_key_count(df: pd.DataFrame, columns: list[str]) -> int:
    if not columns or any(column not in df.columns for column in columns):
        return 0
    return int(df.duplicated(subset=columns, keep=False).sum())


def _time_range(df: pd.DataFrame, column: str | None) -> dict[str, Any]:
    if not column or column not in df.columns:
        return {}
    parsed = pd.to_datetime(df[column], errors="coerce", format="mixed").dropna()
    if parsed.empty:
        return {}
    return {"min": to_jsonable(parsed.min()), "max": to_jsonable(parsed.max())}
