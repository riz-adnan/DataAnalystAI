import math
from typing import Any

import pandas as pd
from fastapi import HTTPException, status

from app.services.result_store import result_store


MAX_PREVIEW_ROWS = 10
MAX_CHART_ROWS = 100


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def dataframe_preview(dataframe: pd.DataFrame, limit: int = MAX_PREVIEW_ROWS) -> list[dict[str, Any]]:
    preview = dataframe.head(limit).astype(object).where(pd.notnull(dataframe.head(limit)), None)
    return [
        {str(key): json_safe(value) for key, value in row.items()}
        for row in preview.to_dict(orient="records")
    ]


def dataframe_to_records(dataframe: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    selected = dataframe if limit is None else dataframe.head(limit)
    selected = selected.astype(object).where(pd.notnull(selected), None)
    return [
        {str(key): json_safe(value) for key, value in row.items()}
        for row in selected.to_dict(orient="records")
    ]


def get_result_dataframe(result_id: str) -> pd.DataFrame:
    if not result_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_result_id is required",
        )
    try:
        return result_store.get(result_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


def store_result(dataframe: pd.DataFrame) -> str:
    return result_store.put(dataframe)


def require_columns(dataframe: pd.DataFrame, columns: list[str]) -> None:
    columns = [column for column in columns if column]
    missing = [column for column in columns if column not in dataframe.columns]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing columns: {', '.join(missing)}",
        )


def success_result(dataframe: pd.DataFrame, result_id: str | None = None) -> dict[str, Any]:
    actual_result_id = result_id or store_result(dataframe)
    return {
        "success": True,
        "result_id": actual_result_id,
        "columns": [str(column) for column in dataframe.columns.tolist()],
        "row_count": int(len(dataframe)),
        "preview": dataframe_preview(dataframe),
    }
