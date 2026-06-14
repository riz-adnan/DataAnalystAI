from typing import Any

from app.tools._utils import dataframe_preview, get_result_dataframe, json_safe


def summarize_result_tool(source_result_id: str, max_rows: int = 10) -> dict[str, Any]:
    dataframe = get_result_dataframe(source_result_id)
    numeric_summary = dataframe.describe(include="number").to_dict()
    safe_summary = {
        str(column): {str(key): json_safe(value) for key, value in values.items()}
        for column, values in numeric_summary.items()
    }

    return {
        "success": True,
        "columns": [str(column) for column in dataframe.columns.tolist()],
        "row_count": int(len(dataframe)),
        "preview": dataframe_preview(dataframe, limit=max_rows),
        "numeric_summary": safe_summary,
    }
