from typing import Any

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.tools._utils import require_columns, success_result
from app.tools.dataframe_loader_tool import load_csv_dataframe


ALLOWED_JOIN_TYPES = {"inner", "left", "right", "outer"}


async def join_csv_tool(
    database: AsyncIOMotorDatabase,
    project_id: str,
    join_plan: dict[str, Any],
) -> dict[str, Any]:
    table_specs = join_plan.get("tables", [])
    join_specs = join_plan.get("joins", [])
    if not table_specs or not join_specs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Join plan requires tables and joins",
        )

    tables = {}
    for table_spec in table_specs:
        alias = table_spec.get("alias")
        file_id = table_spec.get("file_id")
        if not alias or not file_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each table requires file_id and alias",
            )
        tables[alias] = await load_csv_dataframe(database, project_id, file_id)

    first_alias = join_specs[0].get("left_alias")
    if first_alias not in tables:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown left alias {first_alias}",
        )
    result = tables[first_alias].copy()
    active_aliases = {first_alias}

    for join_spec in join_specs:
        left_alias = join_spec.get("left_alias")
        right_alias = join_spec.get("right_alias")
        left_key = join_spec.get("left_key")
        right_key = join_spec.get("right_key")
        how = join_spec.get("how", "inner")

        if how not in ALLOWED_JOIN_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported join type {how}",
            )
        if right_alias not in tables:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown right alias {right_alias}",
            )
        if left_alias not in active_aliases and left_alias not in tables:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown left alias {left_alias}",
            )

        require_columns(result, [left_key])
        right_df = tables[right_alias]
        require_columns(right_df, [right_key])
        result = result.merge(
            right_df,
            left_on=left_key,
            right_on=right_key,
            how=how,
            suffixes=("", f"_{right_alias}"),
        )
        active_aliases.add(right_alias)

    return success_result(result)

