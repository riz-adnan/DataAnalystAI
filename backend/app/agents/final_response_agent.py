from typing import Any

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.prompts import build_final_response_prompt
from app.services.gemini_service import call_gemini
from app.services.trace_service import add_trace, create_trace, elapsed_ms, start_timer


def _find_chart(execution_context: dict[str, Any], final_outputs: dict[str, Any]) -> dict[str, Any] | None:
    for value in [final_outputs, *execution_context.values()]:
        if isinstance(value, dict) and isinstance(value.get("chart"), dict):
            return value["chart"]
    return None


def _find_table(execution_context: dict[str, Any], final_outputs: dict[str, Any]) -> list[dict[str, Any]] | None:
    for value in [final_outputs, *reversed(list(execution_context.values()))]:
        if isinstance(value, dict):
            if isinstance(value.get("data"), list):
                return value["data"][:20]
            if isinstance(value.get("preview"), list):
                return value["preview"][:20]
    return None


def _normalize_table(table: Any) -> list[dict[str, Any]] | None:
    if table is None:
        return None
    if isinstance(table, list):
        return table[:20]
    if isinstance(table, dict):
        rows = table.get("data") or table.get("rows") or table.get("preview")
        if isinstance(rows, list):
            return rows[:20]
        return [table]
    return None


def _fallback_response(
    question: str,
    planner_output: dict[str, Any],
    execution_context: dict[str, Any],
    final_outputs: dict[str, Any],
) -> dict[str, Any]:
    chart = _find_chart(execution_context, final_outputs)
    table = _find_table(execution_context, final_outputs)
    response_type = "chart_and_text" if chart else "table" if table else "text"
    return {
        "response_type": response_type,
        "answer": "I ran the planned analysis and prepared the result.",
        "chart": chart,
        "table": table,
        "follow_up_suggestions": [],
    }


def _normalize_response(response: dict[str, Any], execution_context: dict[str, Any], final_outputs: dict[str, Any]) -> dict[str, Any]:
    chart = response.get("chart") or _find_chart(execution_context, final_outputs)
    table = _normalize_table(response.get("table")) or _find_table(execution_context, final_outputs)
    response_type = response.get("response_type") or ("chart_and_text" if chart else "table" if table else "text")
    if response_type not in {"text", "chart", "chart_and_text", "table"}:
        response_type = "chart_and_text" if chart else "table" if table else "text"
    return {
        "response_type": response_type,
        "answer": response.get("answer") or "Here is the result.",
        "chart": chart,
        "table": table,
        "follow_up_suggestions": response.get("follow_up_suggestions") or [],
    }


async def generate_final_response(
    database: AsyncIOMotorDatabase,
    project: dict[str, Any],
    question: str,
    planner_output: dict[str, Any],
    traces: list[dict[str, Any]],
    execution_context: dict[str, Any],
    final_outputs: dict[str, Any],
) -> dict[str, Any]:
    prompt = build_final_response_prompt(
        question,
        planner_output,
        traces,
        execution_context,
        final_outputs,
    )
    started_at = start_timer()
    project_id = str(project["_id"])

    try:
        output = await call_gemini(project, prompt, response_format="json")
        response = _normalize_response(output, execution_context, final_outputs)
        trace = create_trace(
            question,
            "llm_call",
            "final_response_agent",
            "generate_final_response",
            {"planner_output": planner_output, "final_outputs": final_outputs},
            response,
            "success",
            elapsed_ms(started_at),
        )
        await add_trace(database, project_id, trace)
        return response
    except Exception as exc:
        response = _fallback_response(question, planner_output, execution_context, final_outputs)
        error = exc.detail if isinstance(exc, HTTPException) else str(exc)
        trace = create_trace(
            question,
            "llm_call",
            "final_response_agent",
            "generate_final_response",
            {"planner_output": planner_output, "final_outputs": final_outputs},
            response,
            "error",
            elapsed_ms(started_at),
            str(error),
        )
        await add_trace(database, project_id, trace)
        return response
