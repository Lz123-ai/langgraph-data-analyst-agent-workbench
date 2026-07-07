from __future__ import annotations

import re

import pandas as pd


def latest_complete_period(periods: pd.Series) -> pd.Period | None:
    valid = periods.dropna()
    if valid.empty:
        return None
    counts = valid.value_counts().sort_index()
    median_count = float(counts.median())
    threshold = max(1.0, median_count * 0.5)
    complete = counts[counts >= threshold]
    if complete.empty:
        return valid.max()
    return complete.index.max()


def late_outlier_periods(periods: pd.Series) -> list[str]:
    valid = periods.dropna()
    if valid.empty:
        return []
    latest = latest_complete_period(valid)
    if latest is None:
        return []
    counts = valid.value_counts().sort_index()
    return [str(period) for period, count in counts.items() if period > latest]


def period_filters(filters: list[str]) -> list[pd.Period]:
    periods: list[pd.Period] = []
    for item in filters:
        if item.startswith("__period__=") or item.startswith("__start_period__=") or item.startswith("__end_period__="):
            value = item.split("=", 1)[1].strip()
            period = parse_period(value)
            if period is not None:
                periods.append(period)
    return periods


def start_end_period_filters(filters: list[str]) -> tuple[pd.Period | None, pd.Period | None]:
    start = None
    end = None
    for item in filters:
        if item.startswith("__start_period__="):
            start = parse_period(item.split("=", 1)[1].strip())
        elif item.startswith("__end_period__="):
            end = parse_period(item.split("=", 1)[1].strip())
    explicit = period_filters(filters)
    if start is None and len(explicit) >= 1:
        start = min(explicit)
    if end is None and len(explicit) >= 2:
        end = max(explicit)
    return start, end


def parse_period(value: str) -> pd.Period | None:
    value = value.strip()
    match = re.search(r"(\d{4})[-/年\s]*(1[0-2]|0?[1-9])", value)
    if not match:
        return None
    return pd.Period(f"{int(match.group(1)):04d}-{int(match.group(2)):02d}", freq="M")
