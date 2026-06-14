from typing import Any

from app.tools._utils import get_result_dataframe, require_columns, success_result


def sort_tool(
    source_result_id: str,
    sort_by: str,
    sort_order: str = "desc",
    limit: int | None = None,
) -> dict[str, Any]:
    dataframe = get_result_dataframe(source_result_id)
    require_columns(dataframe, [sort_by])
    result = dataframe.sort_values(by=sort_by, ascending=sort_order == "asc")
    if limit is not None:
        result = result.head(int(limit))
    return success_result(result.reset_index(drop=True))

