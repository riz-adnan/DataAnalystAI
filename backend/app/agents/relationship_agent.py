from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.prompts import build_relationship_prompt
from app.services.gemini_service import call_gemini
from app.services.trace_service import add_trace, create_trace, elapsed_ms, start_timer


def _available_columns(schema_previews: list[dict[str, Any]]) -> dict[str, set[str]]:
    return {
        preview["csv_name"]: set(preview.get("columns", []))
        for preview in schema_previews
        if preview.get("csv_name")
    }


def _sanitize_relationships(output: dict[str, Any], schema_previews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    available = _available_columns(schema_previews)
    relationships: list[dict[str, Any]] = []

    for item in output.get("relationships", []):
        left_csv = item.get("left_csv")
        right_csv = item.get("right_csv")
        left_column = item.get("left_column")
        right_column = item.get("right_column")
        if left_csv not in available or right_csv not in available:
            continue
        if left_column not in available[left_csv] or right_column not in available[right_csv]:
            continue
        relationships.append(
            {
                "left_csv": left_csv,
                "left_column": left_column,
                "right_csv": right_csv,
                "right_column": right_column,
                "join_type": item.get("join_type", "unknown"),
                "recommended_how": item.get("recommended_how", "left"),
                "confidence": float(item.get("confidence", 0)),
                "reason": item.get("reason", ""),
            }
        )

    return relationships


async def infer_and_save_relationships_if_needed(
    database: AsyncIOMotorDatabase,
    project: dict[str, Any],
    question: str,
    schema_previews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing = project.get("known_relationships") or []
    if existing:
        return existing

    project_id = str(project["_id"])
    prompt = build_relationship_prompt(question, schema_previews)
    started_at = start_timer()

    try:
        output = await call_gemini(project, prompt, response_format="json")
        relationships = _sanitize_relationships(output, schema_previews)
        saved = {
            "relationships": relationships,
            "join_notes": output.get("join_notes", []),
        }
        await database.projects.update_one(
            {"_id": ObjectId(project_id)},
            {
                "$set": {
                    "known_relationships": relationships,
                    "traces_context.relationship_notes": saved.get("join_notes", []),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        trace = create_trace(
            question,
            "llm_call",
            "relationship_agent",
            "infer_relationships",
            {"schema_previews": schema_previews},
            saved,
            "success",
            elapsed_ms(started_at),
        )
        await add_trace(database, project_id, trace)
        return relationships
    except Exception as exc:
        error = exc.detail if isinstance(exc, HTTPException) else str(exc)
        trace = create_trace(
            question,
            "llm_call",
            "relationship_agent",
            "infer_relationships",
            {"schema_previews": schema_previews},
            None,
            "error",
            elapsed_ms(started_at),
            str(error),
        )
        await add_trace(database, project_id, trace)
        raise
