from typing import Any

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.prompts import build_planner_prompt
from app.services.gemini_service import call_gemini
from app.services.trace_service import add_trace, create_trace, elapsed_ms, start_timer
from app.tools.tool_registry import AVAILABLE_TOOLS


def _validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("complexity") not in {"simple", "complex"}:
        plan["complexity"] = "simple"
    if plan.get("response_goal") not in {"text", "chart", "chart_and_text", "table"}:
        plan["response_goal"] = "text"
    steps = plan.get("steps")
    if not isinstance(steps, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Planner response did not include steps",
        )
    for step in steps:
        if step.get("step_type") == "tool_call":
            tool = step.get("tool")
            if tool not in AVAILABLE_TOOLS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Planner selected unknown tool {tool}",
                )
        elif step.get("step_type") != "llm_call":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Planner step_type must be tool_call or llm_call",
            )
    return plan


async def plan_query(
    database: AsyncIOMotorDatabase,
    project: dict[str, Any],
    question: str,
    schema_previews: list[dict[str, Any]],
    known_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    recent_chat_history = (project.get("chat_history") or [])[-5:]
    prompt = build_planner_prompt(
        question,
        schema_previews,
        known_relationships,
        AVAILABLE_TOOLS,
        recent_chat_history,
    )
    started_at = start_timer()
    project_id = str(project["_id"])

    try:
        print("planquery)")
        output = await call_gemini(project, prompt, response_format="json")
        plan = _validate_plan(output)
        trace = create_trace(
            question,
            "llm_call",
            "planner_agent",
            "plan_query",
            {"schema_previews": schema_previews, "known_relationships": known_relationships},
            plan,
            "success",
            elapsed_ms(started_at),
        )
        await add_trace(database, project_id, trace)
        return plan
    except Exception as exc:
        error = exc.detail if isinstance(exc, HTTPException) else str(exc)
        trace = create_trace(
            question,
            "llm_call",
            "planner_agent",
            "plan_query",
            {"schema_previews": schema_previews, "known_relationships": known_relationships},
            None,
            "error",
            elapsed_ms(started_at),
            str(error),
        )
        await add_trace(database, project_id, trace)
        raise
