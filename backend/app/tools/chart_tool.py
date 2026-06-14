from typing import Any

from fastapi import HTTPException, status

from app.tools._utils import MAX_CHART_ROWS, dataframe_to_records, get_result_dataframe, require_columns


SUPPORTED_CHARTS = {"bar", "line", "pie", "scatter"}


def generate_chart_tool(source_result_id: str, chart_spec: dict[str, Any]) -> dict[str, Any]:
    dataframe = get_result_dataframe(source_result_id)
    chart_type = chart_spec.get("chart_type")
    x_key = chart_spec.get("x_key")
    y_keys = chart_spec.get("y_keys") or []
    limit = int(chart_spec.get("limit") or MAX_CHART_ROWS)
    limit = min(limit, MAX_CHART_ROWS)

    if chart_type not in SUPPORTED_CHARTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported chart type {chart_type}",
        )
    if chart_type == "pie" and len(y_keys) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pie charts require exactly one y_key",
        )

    require_columns(dataframe, [x_key, *y_keys])
    result = dataframe[[x_key, *y_keys]].copy()
    if chart_type == "line":
        result = result.sort_values(by=x_key)
    result = result.head(limit)

    return {
        "success": True,
        "chart": {
            "chart_type": chart_type,
            "title": chart_spec.get("title", ""),
            "description": chart_spec.get("description", ""),
            "x_key": x_key,
            "y_keys": y_keys,
            "data": dataframe_to_records(result, limit=limit),
        },
    }

