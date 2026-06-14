from typing import Any

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.tools.aggregation_tool import aggregate_tool, create_derived_column_tool
from app.tools.chart_tool import generate_chart_tool
from app.tools._utils import success_result
from app.tools.dataframe_loader_tool import load_csv_dataframe
from app.tools.filter_tool import filter_tool
from app.tools.join_csv_tool import join_csv_tool
from app.tools.sort_tool import sort_tool
from app.tools.summary_tool import summarize_result_tool


AVAILABLE_TOOLS: dict[str, dict[str, Any]] = {
    "load_csv": {
        "description": "Load one cleaned CSV dataframe by file_id as a temporary result",
        "input_schema": {
            "project_id": "string",
            "file_id": "string",
        },
    },
    "join_csv": {
        "description": "Join multiple CSV dataframes using specified keys",
        "input_schema": {
            "project_id": "string",
            "join_plan": {
                "tables": [{"file_id": "string", "alias": "string"}],
                "joins": [
                    {
                        "left_alias": "string",
                        "right_alias": "string",
                        "left_key": "string",
                        "right_key": "string",
                        "how": "inner | left | right | outer",
                    }
                ],
            },
        },
    },
    "aggregate": {
        "description": "Group and aggregate a dataframe result",
        "input_schema": {
            "source_result_id": "string",
            "group_by": ["string"],
            "metrics": [{"column": "string", "operation": "sum | mean | median | min | max | count | nunique"}],
        },
    },
    "filter": {
        "description": "Filter a dataframe result with deterministic operators",
        "input_schema": {
            "source_result_id": "string",
            "filters": [
                {
                    "column": "string",
                    "operator": "equals | not_equals | greater_than | less_than | greater_than_or_equal | less_than_or_equal | contains | between | date_between",
                    "value": "any",
                }
            ],
        },
    },
    "sort": {
        "description": "Sort a dataframe result by one column",
        "input_schema": {
            "source_result_id": "string",
            "sort_by": "string",
            "sort_order": "asc | desc",
            "limit": "number | null",
        },
    },
    "create_derived_column": {
        "description": "Create a safe derived numeric or date-part column without eval",
        "input_schema": {
            "source_result_id": "string",
            "derived_column_spec": {
                "new_column": "string",
                "formula": {
                    "type": "multiply | add | subtract | divide | percentage | date_part",
                    "columns": ["string", "string"],
                    "column": "string, for date_part",
                    "part": "year | month | month_name | quarter | day | day_of_week | week | date | year_month",
                },
            },
        },
    },
    "generate_chart": {
        "description": "Generate frontend-ready chart JSON from a dataframe result",
        "input_schema": {
            "source_result_id": "string",
            "chart_type": "bar | line | pie | scatter",
            "x_key": "string",
            "y_keys": ["string"],
        },
    },
    "summarize_result": {
        "description": "Return columns, row count, preview rows, and numeric summary",
        "input_schema": {"source_result_id": "string", "max_rows": "number"},
    },
}


async def execute_tool(
    database: AsyncIOMotorDatabase,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if tool_name == "load_csv":
        project_id = arguments.get("project_id")
        file_id = arguments.get("file_id")
        if not project_id or not file_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="project_id and file_id are required for load_csv",
            )
        dataframe = await load_csv_dataframe(database, project_id, file_id)
        return success_result(dataframe)

    if tool_name == "join_csv":
        project_id = arguments.get("project_id")
        join_plan = arguments.get("join_plan") or arguments
        if not project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="project_id is required for join_csv",
            )
        return await join_csv_tool(database, project_id, join_plan)

    if tool_name == "aggregate":
        return aggregate_tool(arguments)

    if tool_name == "filter":
        return filter_tool(arguments.get("source_result_id"), arguments.get("filters") or [])

    if tool_name == "sort":
        return sort_tool(
            arguments.get("source_result_id"),
            arguments.get("sort_by"),
            arguments.get("sort_order", "desc"),
            arguments.get("limit"),
        )

    if tool_name == "create_derived_column":
        return create_derived_column_tool(
            arguments.get("source_result_id"),
            arguments.get("derived_column_spec") or arguments,
        )

    if tool_name == "generate_chart":
        source_result_id = arguments.get("source_result_id")
        chart_spec = {key: value for key, value in arguments.items() if key != "source_result_id"}
        return generate_chart_tool(source_result_id, chart_spec)

    if tool_name == "summarize_result":
        return summarize_result_tool(
            arguments.get("source_result_id"),
            int(arguments.get("max_rows", 10)),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown tool {tool_name}",
    )
