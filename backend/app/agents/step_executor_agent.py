from typing import Any
from datetime import date

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.prompts import build_step_executor_prompt, build_tool_argument_repair_prompt
from app.services.gemini_service import call_gemini
from app.services.trace_service import add_trace, create_trace, elapsed_ms, start_timer
from app.tools.tool_registry import AVAILABLE_TOOLS


def _validate_step_output(output: dict[str, Any]) -> dict[str, Any]:
    output.setdefault("status", "success")
    output.setdefault("next_action", "continue")
    output.setdefault("tool_call", None)
    output.setdefault("error", None)
    if output["next_action"] not in {"continue", "finalize", "need_tool"}:
        output["next_action"] = "continue"
    tool_call = output.get("tool_call")
    if output["next_action"] == "need_tool":
        if not isinstance(tool_call, dict) or tool_call.get("tool") not in AVAILABLE_TOOLS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Step executor requested an invalid tool",
            )
    return output


async def execute_llm_step(
    database: AsyncIOMotorDatabase,
    project: dict[str, Any],
    question: str,
    plan: dict[str, Any],
    current_step: dict[str, Any],
    execution_context: dict[str, Any],
    schema_previews: list[dict[str, Any]],
    known_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    prompt = build_step_executor_prompt(
        question,
        plan,
        current_step,
        execution_context,
        schema_previews,
        known_relationships,
    )
    started_at = start_timer()
    project_id = str(project["_id"])

    try:
        output = _validate_step_output(await call_gemini(project, prompt, response_format="json"))
        trace = create_trace(
            question,
            "llm_call",
            "step_executor_agent",
            current_step.get("llm_task", "execute_llm_step"),
            {"current_step": current_step, "execution_context": execution_context},
            output,
            "success",
            elapsed_ms(started_at),
        )
        await add_trace(database, project_id, trace)
        return output
    except Exception as exc:
        error = exc.detail if isinstance(exc, HTTPException) else str(exc)
        trace = create_trace(
            question,
            "llm_call",
            "step_executor_agent",
            current_step.get("llm_task", "execute_llm_step"),
            {"current_step": current_step, "execution_context": execution_context},
            None,
            "error",
            elapsed_ms(started_at),
            str(error),
        )
        await add_trace(database, project_id, trace)
        raise


async def repair_tool_arguments(
    database: AsyncIOMotorDatabase,
    project: dict[str, Any],
    question: str,
    plan: dict[str, Any],
    current_step: dict[str, Any],
    tool_name: str,
    bad_arguments: dict[str, Any],
    error: str,
    execution_context: dict[str, Any],
    schema_previews: list[dict[str, Any]],
    known_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    prompt = build_tool_argument_repair_prompt(
        question=question,
        plan=plan,
        current_step=current_step,
        tool_name=tool_name,
        bad_arguments=bad_arguments,
        error=error,
        execution_context=execution_context,
        schema_previews=schema_previews,
        known_relationships=known_relationships,
        available_tools=AVAILABLE_TOOLS,
        current_date=date.today().isoformat(),
    )
    started_at = start_timer()
    project_id = str(project["_id"])

    try:
        output = await call_gemini(project, prompt, response_format="json")
        repaired_tool = output.get("tool", tool_name)
        if repaired_tool != tool_name or repaired_tool not in AVAILABLE_TOOLS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repair agent returned an invalid tool",
            )
        arguments = output.get("arguments")
        if not isinstance(arguments, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repair agent did not return arguments",
            )
        trace = create_trace(
            question,
            "llm_call",
            "tool_argument_repair_agent",
            f"repair_{tool_name}",
            {"tool": tool_name, "bad_arguments": bad_arguments, "error": error},
            output,
            "success",
            elapsed_ms(started_at),
        )
        await add_trace(database, project_id, trace)
        return arguments
    except Exception as exc:
        trace_error = exc.detail if isinstance(exc, HTTPException) else str(exc)
        trace = create_trace(
            question,
            "llm_call",
            "tool_argument_repair_agent",
            f"repair_{tool_name}",
            {"tool": tool_name, "bad_arguments": bad_arguments, "error": error},
            None,
            "error",
            elapsed_ms(started_at),
            str(trace_error),
        )
        await add_trace(database, project_id, trace)
        raise
