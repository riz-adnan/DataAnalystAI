from typing import Any

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.tools._utils import dataframe_preview
from app.tools.tool_registry import execute_tool


SAMPLE_PLANNER_OUTPUT = {
    "mode": "simple_execution",
    "steps": [
        {"tool": "join_csv", "arguments": {}},
        {"tool": "create_derived_column", "arguments": {}},
        {"tool": "aggregate", "arguments": {}},
        {"tool": "generate_chart", "arguments": {}},
    ],
    "final_response_type": "chart_and_text",
}


def _output_preview(output: dict[str, Any]) -> Any:
    if "chart" in output:
        chart = output["chart"]
        return {
            "chart_type": chart.get("chart_type"),
            "title": chart.get("title"),
            "rows": len(chart.get("data", [])),
        }
    if "preview" in output:
        return output["preview"]
    if "data" in output:
        return output["data"][:10]
    return {key: output[key] for key in output.keys() & {"success", "row_count", "result_id"}}


async def execute_plan(
    database: AsyncIOMotorDatabase,
    project_id: str,
    plan: dict[str, Any],
) -> dict[str, Any]:
    steps = plan.get("steps") or []
    traces: list[dict[str, Any]] = []
    last_result_id: str | None = None
    final_result: dict[str, Any] | None = None
    chart: dict[str, Any] | None = None

    for step in steps:
        tool_name = step.get("tool")
        arguments = dict(step.get("arguments") or {})
        if tool_name == "join_csv":
            arguments.setdefault("project_id", project_id)
        elif last_result_id and "source_result_id" not in arguments:
            arguments["source_result_id"] = last_result_id

        trace = {
            "tool": tool_name,
            "arguments": arguments,
            "status": "pending",
        }

        try:
            output = await execute_tool(database, tool_name, arguments)
            trace["status"] = "success"
            trace["output_preview"] = _output_preview(output)
            final_result = output
            if output.get("result_id"):
                last_result_id = output["result_id"]
            if output.get("chart"):
                chart = output["chart"]
        except HTTPException as exc:
            trace["status"] = "error"
            trace["error"] = exc.detail
            traces.append(trace)
            return {
                "success": False,
                "final_result": final_result,
                "chart": chart,
                "traces": traces,
            }
        except Exception as exc:
            trace["status"] = "error"
            trace["error"] = str(exc)
            traces.append(trace)
            return {
                "success": False,
                "final_result": final_result,
                "chart": chart,
                "traces": traces,
            }

        traces.append(trace)

    return {
        "success": True,
        "final_result": final_result,
        "chart": chart,
        "traces": traces,
    }
