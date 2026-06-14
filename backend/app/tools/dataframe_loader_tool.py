import re
from io import BytesIO
from pathlib import Path

import pandas as pd
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.supabase_storage_service import download_file_from_supabase


def safe_table_name(filename: str) -> str:
    stem = Path(filename).stem.strip().lower()
    stem = re.sub(r"\s+", "_", stem)
    stem = re.sub(r"[^a-z0-9_]", "", stem)
    return stem or "table"


async def _get_csv_metadata(
    database: AsyncIOMotorDatabase,
    project_id: str | ObjectId,
    file_id: str,
) -> dict:
    if isinstance(project_id, ObjectId):
        object_id = project_id
    else:
        try:
            object_id = ObjectId(str(project_id))
        except (InvalidId, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid project id",
            ) from exc

    project = await database.projects.find_one(
        {"_id": object_id, "csv_files.file_id": file_id},
        {"csv_files.$": 1},
    )
    if not project or not project.get("csv_files"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CSV file {file_id} was not found for this project",
        )

    return project["csv_files"][0]


async def load_csv_dataframe(
    database: AsyncIOMotorDatabase,
    project_id: str | ObjectId,
    file_id: str,
) -> pd.DataFrame:
    metadata = await _get_csv_metadata(database, project_id, file_id)
    cleaned_path = metadata.get("cleaned_supabase_path")
    if not cleaned_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CSV file {file_id} does not have a cleaned Supabase path",
        )

    content = download_file_from_supabase(cleaned_path)
    return pd.read_csv(BytesIO(content))


async def load_multiple_dataframes(
    database: AsyncIOMotorDatabase,
    project_id: str | ObjectId,
    file_ids: list[str],
) -> dict[str, pd.DataFrame]:
    dataframes: dict[str, pd.DataFrame] = {}
    used_names: dict[str, int] = {}

    for file_id in file_ids:
        metadata = await _get_csv_metadata(database, project_id, file_id)
        table_name = safe_table_name(metadata.get("original_name", file_id))
        count = used_names.get(table_name, 0)
        used_names[table_name] = count + 1
        if count:
            table_name = f"{table_name}_{count + 1}"
        dataframes[table_name] = await load_csv_dataframe(database, project_id, file_id)

    return dataframes
