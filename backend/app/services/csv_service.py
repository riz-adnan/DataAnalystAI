from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, UploadFile, status

from app.config import get_settings
from app.models.project import CsvFileMetadata
from app.services.csv_preprocessing_service import (
    build_schema_preview,
    dataframe_to_json_safe_records,
    preprocess_csv_bytes,
)
from app.services.supabase_storage_service import (
    delete_file_from_supabase,
    download_file_from_supabase,
    upload_file_to_supabase,
)


CSV_CONTENT_TYPE = "text/csv"


def _safe_filename(filename: str) -> str:
    return Path(filename).name.replace("\\", "_").replace("/", "_")


def _cleaned_dataframe_to_csv_bytes(cleaned_dataframe: pd.DataFrame) -> bytes:
    buffer = StringIO()
    cleaned_dataframe.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")


async def save_and_analyze_csv(project_id: str, upload: UploadFile) -> CsvFileMetadata:
    original_name = _safe_filename(upload.filename or "")

    if not original_name.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{original_name or 'Uploaded file'} must be a CSV file",
        )

    content = await upload.read()
    settings = get_settings()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{original_name} is empty",
        )

    if len(content) > settings.max_upload_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{original_name} exceeds the upload size limit",
        )

    file_id = str(uuid4())
    storage_name = f"{file_id}_{original_name}"
    original_supabase_path = f"projects/{project_id}/original/{storage_name}"
    cleaned_supabase_path = f"projects/{project_id}/cleaned/{storage_name}"

    upload_file_to_supabase(original_supabase_path, content, CSV_CONTENT_TYPE)

    try:
        cleaned_dataframe, preprocessing_report = preprocess_csv_bytes(content)
    except Exception as exc:
        delete_file_from_supabase(original_supabase_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{original_name} could not be parsed or preprocessed as CSV",
        ) from exc

    cleaned_content = _cleaned_dataframe_to_csv_bytes(cleaned_dataframe)

    try:
        upload_file_to_supabase(cleaned_supabase_path, cleaned_content, CSV_CONTENT_TYPE)
    except Exception:
        delete_file_from_supabase(original_supabase_path)
        raise

    schema_preview = build_schema_preview(original_name, cleaned_dataframe)
    row_count_before = int(preprocessing_report["rows_before"])
    row_count_after = int(preprocessing_report["rows_after"])

    return CsvFileMetadata(
        file_id=file_id,
        original_name=original_name,
        original_supabase_path=original_supabase_path,
        cleaned_supabase_path=cleaned_supabase_path,
        uploaded_at=datetime.now(timezone.utc),
        row_count=row_count_after,
        row_count_before=row_count_before,
        row_count_after=row_count_after,
        columns=[str(column) for column in cleaned_dataframe.columns.tolist()],
        schema={str(column): str(dtype) for column, dtype in cleaned_dataframe.dtypes.items()},
        schema_preview=schema_preview,
        sample_rows=dataframe_to_json_safe_records(cleaned_dataframe, limit=5),
        preprocessing_report=preprocessing_report,
    )


async def load_project_csv_as_dataframe(
    database: Any,
    project_id: str,
    file_id: str,
) -> pd.DataFrame:
    try:
        object_id = ObjectId(project_id)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invaliid project id",
        ) from exc

    project = await database.projects.find_one(
        {"_id": object_id, "csv_files.file_id": file_id},
        {"csv_files.$": 1},
    )

    if not project or not project.get("csv_files"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CSV file not found",
        )

    cleaned_path = project["csv_files"][0].get("cleaned_supabase_path")
    if not cleaned_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cleaned CSV path not found",
        )

    content = download_file_from_supabase(cleaned_path)
    return pd.read_csv(BytesIO(content))
