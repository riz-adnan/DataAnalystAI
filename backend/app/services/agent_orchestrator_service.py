from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.final_response_agent import generate_final_response
from app.agents.planner_agent import plan_query
from app.agents.relationship_agent import infer_and_save_relationships_if_needed
from app.agents.step_executor_agent import execute_llm_step, repair_tool_arguments
from app.services.trace_service import add_trace, build_output_preview, create_trace, elapsed_ms, start_timer
from app.tools.dataframe_loader_tool import safe_table_name
from app.tools.tool_registry import execute_tool


MAX_COMPLEX_ITERATIONS = 5


def _build_schema_previews(project: dict[str, Any]) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for csv_file in project.get("csv_files", []):
        schema_preview = csv_file.get("schema_preview") or {}
        previews.append(
            {
                "file_id": csv_file.get("file_id"),
                "original_name": csv_file.get("original_name"),
                "csv_name": schema_preview.get("csv_name") or csv_file.get("original_name"),
                "columns": schema_preview.get("columns") or csv_file.get("columns", []),
                "sample_rows": schema_preview.get("sample_rows", []),
            }
        )
    return previews


def _context_entry(output: dict[str, Any]) -> dict[str, Any]:
    return build_output_preview(output)


def _csv_aliases(preview: dict[str, Any]) -> set[str]:
    aliases = {
        str(preview.get("file_id") or ""),
        str(preview.get("original_name") or ""),
        str(preview.get("csv_name") or ""),
    }
    aliases.update(safe_table_name(alias) for alias in list(aliases) if alias)
    return {alias for alias in aliases if alias}


def _find_file_id_for_reference(schema_previews: list[dict[str, Any]], reference: str | None) -> str | None:
    if not reference:
        return None
    reference = str(reference)
    for preview in schema_previews:
        if reference in _csv_aliases(preview):
            file_id = preview.get("file_id")
            return str(file_id) if file_id else None
    return None


def _inject_result_id(arguments: dict[str, Any], project_id: str, last_result_id: str | None, tool_name: str) -> dict[str, Any]:
    next_args = dict(arguments or {})
    if tool_name in {"join_csv", "load_csv"}:
        # Always use the authenticated project. Planner-provided IDs are not trusted.
        next_args["project_id"] = project_id
    elif last_result_id and "source_result_id" not in next_args:
        next_args["source_result_id"] = last_result_id
    return next_args


async def _execute_tool_with_trace(
    database: AsyncIOMotorDatabase,
    project_id: str,
    question: str,
    agent: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    started_at = start_timer()
    try:
        output = await execute_tool(database, tool_name, arguments)
        trace = create_trace(
            question,
            "tool_call",
            agent,
            tool_name,
            arguments,
            output,
            "success",
            elapsed_ms(started_at),
        )
        await add_trace(database, project_id, trace)
        return output, trace
    except Exception as exc:
        error = exc.detail if isinstance(exc, HTTPException) else str(exc)
        trace = create_trace(
            question,
            "tool_call",
            agent,
            tool_name,
            arguments,
            None,
            "error",
            elapsed_ms(started_at),
            str(error),
        )
        await add_trace(database, project_id, trace)
        raise


async def _resolve_dataframe_source(
    database: AsyncIOMotorDatabase,
    project_id: str,
    question: str,
    agent: str,
    tool_name: str,
    arguments: dict[str, Any],
    schema_previews: list[dict[str, Any]],
    result_aliases: dict[str, str],
    last_result_id: str | None,
) -> tuple[dict[str, Any], str | None, list[dict[str, Any]]]:
    if tool_name in {"load_csv", "join_csv"}:
        return arguments, last_result_id, []

    next_args = dict(arguments)
    source_reference = next_args.get("source_result_id")
    traces: list[dict[str, Any]] = []

    if source_reference in result_aliases:
        next_args["source_result_id"] = result_aliases[str(source_reference)]
        return next_args, last_result_id, traces

    if last_result_id:
        next_args["source_result_id"] = last_result_id
        return next_args, last_result_id, traces

    file_id = _find_file_id_for_reference(schema_previews, str(source_reference) if source_reference else None)
    if file_id is None and len(schema_previews) == 1:
        only_file_id = schema_previews[0].get("file_id")
        file_id = str(only_file_id) if only_file_id else None

    if file_id is None:
        return next_args, last_result_id, traces

    load_output, load_trace = await _execute_tool_with_trace(
        database,
        project_id,
        question,
        agent,
        "load_csv",
        {"project_id": project_id, "file_id": file_id},
    )
    traces.append(load_trace)
    loaded_result_id = load_output.get("result_id")
    if loaded_result_id:
        for preview in schema_previews:
            if str(preview.get("file_id")) == file_id:
                for alias in _csv_aliases(preview):
                    result_aliases[alias] = loaded_result_id
        result_aliases[str(source_reference)] = loaded_result_id
        next_args["source_result_id"] = loaded_result_id
        return next_args, loaded_result_id, traces

    return next_args, last_result_id, traces


async def _execute_tool_with_repair(
    database: AsyncIOMotorDatabase,
    project: dict[str, Any],
    project_id: str,
    question: str,
    agent: str,
    tool_name: str,
    arguments: dict[str, Any],
    plan: dict[str, Any],
    current_step: dict[str, Any],
    execution_context: dict[str, Any],
    schema_previews: list[dict[str, Any]],
    known_relationships: list[dict[str, Any]],
    result_aliases: dict[str, str],
    last_result_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any], str | None, list[dict[str, Any]]]:
    try:
        output, trace = await _execute_tool_with_trace(
            database,
            project_id,
            question,
            agent,
            tool_name,
            arguments,
        )
        next_result_id = output.get("result_id") or last_result_id
        return output, trace, next_result_id, []
    except HTTPException as exc:
        error = str(exc.detail)

    repaired_arguments = await repair_tool_arguments(
        database=database,
        project=project,
        question=question,
        plan=plan,
        current_step=current_step,
        tool_name=tool_name,
        bad_arguments=arguments,
        error=error,
        execution_context=execution_context,
        schema_previews=schema_previews,
        known_relationships=known_relationships,
    )
    repaired_arguments = _inject_result_id(
        repaired_arguments,
        project_id,
        last_result_id,
        tool_name,
    )
    repaired_arguments, resolved_result_id, pre_traces = await _resolve_dataframe_source(
        database,
        project_id,
        question,
        agent,
        tool_name,
        repaired_arguments,
        schema_previews,
        result_aliases,
        last_result_id,
    )
    output, trace = await _execute_tool_with_trace(
        database,
        project_id,
        question,
        agent,
        tool_name,
        repaired_arguments,
    )
    next_result_id = output.get("result_id") or resolved_result_id or last_result_id
    return output, trace, next_result_id, pre_traces


async def _execute_simple_plan(
    database: AsyncIOMotorDatabase,
    project: dict[str, Any],
    project_id: str,
    question: str,
    plan: dict[str, Any],
    schema_previews: list[dict[str, Any]],
    known_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    execution_context: dict[str, Any] = {}
    traces: list[dict[str, Any]] = []
    final_output: dict[str, Any] = {}
    last_result_id: str | None = None
    result_aliases: dict[str, str] = {}

    for index, step in enumerate(plan.get("steps", []), start=1):
        if step.get("step_type") != "tool_call":
            continue
        tool_name = step.get("tool")
        arguments = _inject_result_id(
            step.get("arguments") or {},
            project_id,
            last_result_id,
            tool_name,
        )
        arguments, last_result_id, pre_traces = await _resolve_dataframe_source(
            database,
            project_id,
            question,
            "planner_agent",
            tool_name,
            arguments,
            schema_previews,
            result_aliases,
            last_result_id,
        )
        traces.extend(pre_traces)
        output, trace, last_result_id, repair_traces = await _execute_tool_with_repair(
            database,
            project,
            project_id,
            question,
            "planner_agent",
            tool_name,
            arguments,
            plan,
            step,
            execution_context,
            schema_previews,
            known_relationships,
            result_aliases,
            last_result_id,
        )
        traces.extend(repair_traces)
        traces.append(trace)
        final_output = output
        if output.get("result_id"):
            last_result_id = output["result_id"]
        save_as = step.get("save_as") or f"step_{index}"
        if last_result_id:
            result_aliases[str(save_as)] = last_result_id
            if tool_name == "load_csv" and arguments.get("file_id"):
                for preview in schema_previews:
                    if str(preview.get("file_id")) == str(arguments.get("file_id")):
                        for alias in _csv_aliases(preview):
                            result_aliases[alias] = last_result_id
        execution_context[save_as] = _context_entry(output)

    return {
        "success": True,
        "execution_context": execution_context,
        "final_output": final_output,
        "traces": traces,
    }


async def _execute_complex_plan(
    database: AsyncIOMotorDatabase,
    project: dict[str, Any],
    question: str,
    plan: dict[str, Any],
    schema_previews: list[dict[str, Any]],
    known_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    project_id = str(project["_id"])
    execution_context: dict[str, Any] = {}
    traces: list[dict[str, Any]] = []
    final_output: dict[str, Any] = {}
    last_result_id: str | None = None
    result_aliases: dict[str, str] = {}
    iterations = 0

    for index, step in enumerate(plan.get("steps", []), start=1):
        if iterations >= MAX_COMPLEX_ITERATIONS:
            break
        iterations += 1

        if step.get("step_type") == "tool_call":
            tool_name = step.get("tool")
            arguments = _inject_result_id(step.get("arguments") or {}, project_id, last_result_id, tool_name)
            arguments, last_result_id, pre_traces = await _resolve_dataframe_source(
                database,
                project_id,
                question,
                "step_executor_agent",
                tool_name,
                arguments,
                schema_previews,
                result_aliases,
                last_result_id,
            )
            traces.extend(pre_traces)
            output, trace, last_result_id, repair_traces = await _execute_tool_with_repair(
                database,
                project,
                project_id,
                question,
                "step_executor_agent",
                tool_name,
                arguments,
                plan,
                step,
                execution_context,
                schema_previews,
                known_relationships,
                result_aliases,
                last_result_id,
            )
            traces.extend(repair_traces)
            traces.append(trace)
            final_output = output
            if output.get("result_id"):
                last_result_id = output["result_id"]
            save_as = step.get("save_as") or f"step_{index}"
            if last_result_id:
                result_aliases[str(save_as)] = last_result_id
                if tool_name == "load_csv" and arguments.get("file_id"):
                    for preview in schema_previews:
                        if str(preview.get("file_id")) == str(arguments.get("file_id")):
                            for alias in _csv_aliases(preview):
                                result_aliases[alias] = last_result_id
            execution_context[save_as] = _context_entry(output)
            continue

        llm_output = await execute_llm_step(
            database,
            project,
            question,
            plan,
            step,
            execution_context,
            schema_previews,
            known_relationships,
        )
        execution_context[step.get("save_as") or f"step_{index}"] = _context_entry(llm_output)
        final_output = llm_output

        if llm_output.get("next_action") == "need_tool":
            tool_call = llm_output.get("tool_call") or {}
            tool_name = tool_call.get("tool")
            arguments = _inject_result_id(tool_call.get("arguments") or {}, project_id, last_result_id, tool_name)
            arguments, last_result_id, pre_traces = await _resolve_dataframe_source(
                database,
                project_id,
                question,
                "step_executor_agent",
                tool_name,
                arguments,
                schema_previews,
                result_aliases,
                last_result_id,
            )
            traces.extend(pre_traces)
            output, trace, last_result_id, repair_traces = await _execute_tool_with_repair(
                database,
                project,
                project_id,
                question,
                "step_executor_agent",
                tool_name,
                arguments,
                plan,
                step,
                execution_context,
                schema_previews,
                known_relationships,
                result_aliases,
                last_result_id,
            )
            traces.extend(repair_traces)
            traces.append(trace)
            final_output = output
            if output.get("result_id"):
                last_result_id = output["result_id"]
            save_as = f"{step.get('save_as') or f'step_{index}'}_tool"
            if last_result_id:
                result_aliases[save_as] = last_result_id
            execution_context[save_as] = _context_entry(output)

        if llm_output.get("next_action") == "finalize":
            break

    return {
        "success": True,
        "execution_context": execution_context,
        "final_output": final_output,
        "traces": traces,
    }


async def _save_chat_history(
    database: AsyncIOMotorDatabase,
    project_id: str,
    question: str,
    final_response: dict[str, Any],
) -> None:
    table = final_response.get("table")
    if isinstance(table, list):
        table_preview = table[:5]
    elif isinstance(table, dict):
        rows = table.get("data") or table.get("rows") or table.get("preview")
        table_preview = rows[:5] if isinstance(rows, list) else [table]
    else:
        table_preview = []

    await database.projects.update_one(
        {"_id": ObjectId(project_id)},
        {
            "$push": {
                "chat_history": {
                    "timestamp": datetime.now(timezone.utc),
                    "question": question,
                    "answer": final_response.get("answer", ""),
                    "response_type": final_response.get("response_type", "text"),
                    "chart": final_response.get("chart"),
                    "table_preview": table_preview,
                }
            },
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )


async def handle_chat_query(
    database: AsyncIOMotorDatabase,
    project_id: str,
    question: str,
) -> dict[str, Any]:
    question = question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question is required",
        )

    project = await database.projects.find_one({"_id": ObjectId(project_id)})
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not project.get("csv_files"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload at least one CSV before asking questions",
        )
    trace_start_index = len(project.get("traces", []))

    schema_previews = _build_schema_previews(project)
    known_relationships = await infer_and_save_relationships_if_needed(
        database,
        project,
        question,
        schema_previews,
    )
    project["known_relationships"] = known_relationships

    plan = await plan_query(database, project, question, schema_previews, known_relationships)
    if plan.get("complexity") == "complex":
        execution = await _execute_complex_plan(
            database,
            project,
            question,
            plan,
            schema_previews,
            known_relationships,
        )
    else:
        execution = await _execute_simple_plan(
            database,
            project,
            project_id,
            question,
            plan,
            schema_previews,
            known_relationships,
        )

    final_response = await generate_final_response(
        database,
        project,
        question,
        plan,
        execution.get("traces", []),
        execution.get("execution_context", {}),
        execution.get("final_output") or {},
    )
    await _save_chat_history(database, project_id, question, final_response)
    updated_project = await database.projects.find_one({"_id": ObjectId(project_id)})
    traces = (updated_project or {}).get("traces", [])[trace_start_index:]

    return {
        "success": True,
        "answer": final_response.get("answer", ""),
        "response_type": final_response.get("response_type", "text"),
        "chart": final_response.get("chart"),
        "table": final_response.get("table"),
        "follow_up_suggestions": final_response.get("follow_up_suggestions", []),
        "traces": traces,
    }
