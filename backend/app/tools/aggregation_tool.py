from typing import Any

import pandas as pd
from fastapi import HTTPException, status

from app.tools._utils import dataframe_to_records, get_result_dataframe, require_columns, store_result


SUPPORTED_AGGREGATIONS = {"sum", "mean", "median", "min", "max", "count", "nunique"}
SUPPORTED_FORMULAS = {
    "multiply",
    "add",
    "subtract",
    "divide",
    "percentage",
    "date_part",
}
SUPPORTED_DATE_PARTS = {
    "year",
    "month",
    "month_name",
    "quarter",
    "day",
    "day_of_week",
    "week",
    "date",
    "year_month",
}


def aggregate_tool(operation: dict[str, Any]) -> dict[str, Any]:
    source_result_id = operation.get("source_result_id")
    if not source_result_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_result_id is required",
        )

    dataframe = get_result_dataframe(source_result_id)
    group_by = operation.get("group_by") or []
    metrics = operation.get("metrics") or []
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one metric is required",
        )

    require_columns(dataframe, group_by)
    require_columns(dataframe, [metric.get("column") for metric in metrics])

    aggregation_map = {}
    aliases = {}
    for metric in metrics:
        column = metric.get("column")
        operation_name = metric.get("operation")
        alias = metric.get("alias") or f"{operation_name}_{column}"
        if operation_name not in SUPPORTED_AGGREGATIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported aggregation {operation_name}",
            )
        aggregation_map[alias] = pd.NamedAgg(column=column, aggfunc=operation_name)
        aliases[alias] = alias

    if group_by:
        result = dataframe.groupby(group_by, dropna=False).agg(**aggregation_map).reset_index()
    else:
        row = {}
        for metric in metrics:
            column = metric["column"]
            operation_name = metric["operation"]
            alias = metric.get("alias") or f"{operation_name}_{column}"
            row[alias] = getattr(dataframe[column], operation_name)()
        result = pd.DataFrame([row])

    sort_by = operation.get("sort_by")
    if sort_by:
        require_columns(result, [sort_by])
        ascending = operation.get("sort_order", "desc") == "asc"
        result = result.sort_values(by=sort_by, ascending=ascending)

    limit = operation.get("limit")
    if limit is not None:
        result = result.head(int(limit))

    result_id = store_result(result)
    return {
        "success": True,
        "result_id": result_id,
        "data": dataframe_to_records(result),
        "columns": [str(column) for column in result.columns.tolist()],
        "row_count": int(len(result)),
    }


def create_derived_column_tool(
    source_result_id: str,
    derived_column_spec: dict[str, Any],
) -> dict[str, Any]:
    dataframe = get_result_dataframe(source_result_id)
    new_column = derived_column_spec.get("new_column")
    formula = derived_column_spec.get("formula") or {}
    formula_type = formula.get("type")
    columns = formula.get("columns") or []

    if not new_column:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="new_column is required",
        )
    if formula_type not in SUPPORTED_FORMULAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported formula type {formula_type}",
        )
    result = dataframe.copy()

    if formula_type == "date_part":
        column = formula.get("column") or (columns[0] if columns else None)
        part = str(formula.get("part") or formula.get("date_part") or "year_month").strip().lower()
        if part not in SUPPORTED_DATE_PARTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported date_part {part}",
            )
        require_columns(dataframe, [column])
        dates = pd.to_datetime(dataframe[column], errors="coerce")
        if part == "year":
            result[new_column] = dates.dt.year.astype("Int64")
        elif part == "month":
            result[new_column] = dates.dt.month.astype("Int64")
        elif part == "month_name":
            result[new_column] = dates.dt.month_name()
        elif part == "quarter":
            result[new_column] = ("Q" + dates.dt.quarter.astype("Int64").astype(str)).where(dates.notna())
        elif part == "day":
            result[new_column] = dates.dt.day.astype("Int64")
        elif part == "day_of_week":
            result[new_column] = dates.dt.day_name()
        elif part == "week":
            result[new_column] = dates.dt.isocalendar().week.astype("Int64")
        elif part == "date":
            result[new_column] = dates.dt.date.astype(str).where(dates.notna())
        elif part == "year_month":
            result[new_column] = dates.dt.to_period("M").astype(str).where(dates.notna())

        result_id = store_result(result)
        return {
            "success": True,
            "result_id": result_id,
            "columns": [str(column) for column in result.columns.tolist()],
            "row_count": int(len(result)),
            "preview": dataframe_to_records(result, limit=10),
        }

    if len(columns) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Derived column formulas require exactly two columns",
        )
    require_columns(dataframe, columns)

    left = pd.to_numeric(dataframe[columns[0]], errors="coerce")
    right = pd.to_numeric(dataframe[columns[1]], errors="coerce")

    if formula_type == "multiply":
        result[new_column] = left * right
    elif formula_type == "add":
        result[new_column] = left + right
    elif formula_type == "subtract":
        result[new_column] = left - right
    elif formula_type == "divide":
        result[new_column] = left.divide(right.where(right != 0))
    elif formula_type == "percentage":
        result[new_column] = left.divide(right.where(right != 0)) * 100

    result_id = store_result(result)
    return {
        "success": True,
        "result_id": result_id,
        "columns": [str(column) for column in result.columns.tolist()],
        "row_count": int(len(result)),
        "preview": dataframe_to_records(result, limit=10),
    }
