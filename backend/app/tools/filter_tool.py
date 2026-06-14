from typing import Any

import pandas as pd
from fastapi import HTTPException, status

from app.tools._utils import get_result_dataframe, require_columns, success_result


SUPPORTED_FILTERS = {
    "equals",
    "not_equals",
    "greater_than",
    "less_than",
    "greater_than_or_equal",
    "less_than_or_equal",
    "contains",
    "between",
    "date_between",
}

FILTER_OPERATOR_ALIASES = {
    "=": "equals",
    "==": "equals",
    "eq": "equals",
    "!=": "not_equals",
    "<>": "not_equals",
    "ne": "not_equals",
    ">": "greater_than",
    "gt": "greater_than",
    "<": "less_than",
    "lt": "less_than",
    ">=": "greater_than_or_equal",
    "gte": "greater_than_or_equal",
    "<=": "less_than_or_equal",
    "lte": "less_than_or_equal",
}


def normalize_filter_operator(operator: Any) -> str:
    normalized = str(operator or "").strip().lower()
    return FILTER_OPERATOR_ALIASES.get(normalized, normalized)


def filter_tool(source_result_id: str, filters: list[dict[str, Any]]) -> dict[str, Any]:
    dataframe = get_result_dataframe(source_result_id)
    result = dataframe.copy()

    for filter_spec in filters:
        column = filter_spec.get("column")
        operator = normalize_filter_operator(filter_spec.get("operator"))
        value = filter_spec.get("value")
        if operator not in SUPPORTED_FILTERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported filter operator {operator}",
            )
        require_columns(result, [column])

        series = result[column]
        if operator == "equals":
            mask = series == value
        elif operator == "not_equals":
            mask = series != value
        elif operator == "greater_than":
            mask = pd.to_numeric(series, errors="coerce") > value
        elif operator == "less_than":
            mask = pd.to_numeric(series, errors="coerce") < value
        elif operator == "greater_than_or_equal":
            mask = pd.to_numeric(series, errors="coerce") >= value
        elif operator == "less_than_or_equal":
            mask = pd.to_numeric(series, errors="coerce") <= value
        elif operator == "contains":
            mask = series.astype(str).str.contains(str(value), case=False, na=False)
        elif operator == "between":
            if not isinstance(value, list) or len(value) != 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="between filter requires [min, max]",
                )
            numeric = pd.to_numeric(series, errors="coerce")
            mask = numeric.between(value[0], value[1])
        elif operator == "date_between":
            if not isinstance(value, list) or len(value) != 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="date_between filter requires [start, end]",
                )
            dates = pd.to_datetime(series, errors="coerce")
            start = pd.to_datetime(value[0])
            end = pd.to_datetime(value[1])
            mask = dates.between(start, end)

        result = result.loc[mask].reset_index(drop=True)

    return success_result(result)
