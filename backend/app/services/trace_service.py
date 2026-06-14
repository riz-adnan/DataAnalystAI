from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_timer() -> float:
    return perf_counter()


def elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def build_output_preview(output: Any, max_items: int = 5) -> Any:
    if output is None:
        return None
    if isinstance(output, list):
        return [build_output_preview(item, max_items) for item in output[:max_items]]
    if not isinstance(output, dict):
        text = str(output)
        return text[:500]

    if "chart" in output and isinstance(output["chart"], dict):
        chart = output["chart"]
        return {
            "chart_type": chart.get("chart_type"),
            "title": chart.get("title"),
            "x_key": chart.get("x_key"),
            "y_keys": chart.get("y_keys"),
            "rows": len(chart.get("data", [])),
        }
    if "data" in output and isinstance(output["data"], list):
        return {
            "success": output.get("success"),
            "result_id": output.get("result_id"),
            "columns": output.get("columns"),
            "row_count": output.get("row_count"),
            "data": output["data"][:max_items],
        }
    if "preview" in output and isinstance(output["preview"], list):
        return {
            "success": output.get("success"),
            "result_id": output.get("result_id"),
            "columns": output.get("columns"),
            "row_count": output.get("row_count"),
            "preview": output["preview"][:max_items],
        }

    preview: dict[str, Any] = {}
    for key, value in output.items():
        if key in {"result_id", "columns", "row_count", "success", "response_type", "answer", "status", "next_action"}:
            preview[key] = value
        elif key in {"table", "follow_up_suggestions"} and isinstance(value, list):
            preview[key] = value[:max_items]
        elif key == "relationships" and isinstance(value, list):
            preview[key] = value[:max_items]
        elif isinstance(value, (str, int, float, bool)) or value is None:
            preview[key] = value
    return preview


def create_trace(
    question: str,
    step_type: str,
    agent: str,
    name: str,
    input_data: Any,
    output: Any,
    status: str,
    duration_ms: int,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "trace_id": str(uuid4()),
        "timestamp": now_iso(),
        "question": question,
        "step_type": step_type,
        "agent": agent,
        "name": name,
        "input": build_output_preview(input_data),
        "output_preview": build_output_preview(output),
        "status": status,
        "error": error,
        "duration_ms": duration_ms,
    }


async def add_trace(
    database: AsyncIOMotorDatabase,
    project_id: str,
    trace_obj: dict[str, Any],
) -> None:
    await database.projects.update_one(
        {"_id": ObjectId(project_id)},
        {
            "$push": {"traces": trace_obj},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
