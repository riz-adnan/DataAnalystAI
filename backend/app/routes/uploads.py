from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.models.project import (
    CsvFileMetadata,
    FilesResponse,
    UploadCsvError,
    UploadCsvMetrics,
    UploadCsvResponse,
)
from app.services.auth_service import get_current_project, get_required_database
from app.services.csv_service import save_and_analyze_csv


router = APIRouter(prefix="/projects", tags=["uploads"])


@router.post("/upload-csv", response_model=UploadCsvResponse)
async def upload_csv_files(
    request: Request,
    files: list[UploadFile] = File(...),
    project: dict[str, Any] = Depends(get_current_project),
) -> UploadCsvResponse:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one CSV file is required",
        )
    database = get_required_database(request)
    project_id = str(project["_id"])
    uploaded_files: list[CsvFileMetadata] = []
    errors: list[UploadCsvError] = []

    for upload in files:
        original_name = upload.filename or "Uploaded file"
        try:
            uploaded_files.append(await save_and_analyze_csv(project_id, upload))
        except HTTPException as exc:
            detail = str(exc.detail) if exc.detail else f"{original_name} failed preprocessing"
            errors.append(UploadCsvError(original_name=original_name, error=detail))
        except Exception as exc:
            errors.append(
                UploadCsvError(
                    original_name=original_name,
                    error=f"{original_name} failed preprocessing",
                )
            )

    if uploaded_files:
        await database.projects.update_one(
            {"_id": project["_id"]},
            {
                "$push": {
                    "csv_files": {
                        "$each": [
                            file.model_dump(mode="json", by_alias=True)
                            for file in uploaded_files
                        ]
                    }
                },
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

    metrics = UploadCsvMetrics(
        requested_count=len(files),
        uploaded_count=len(uploaded_files),
        failed_count=len(errors),
        total_rows_before=sum(file.row_count_before for file in uploaded_files),
        total_rows_after=sum(file.row_count_after for file in uploaded_files),
        total_rows=sum(file.row_count_before for file in uploaded_files),
        total_cleaned_rows=sum(file.row_count_after for file in uploaded_files),
        duplicates_removed=sum(
            int(file.preprocessing_report.get("duplicates_removed", 0))
            for file in uploaded_files
        ),
    )

    return UploadCsvResponse(
        files=uploaded_files,
        uploaded_count=len(uploaded_files),
        metrics=metrics,
        errors=errors,
    )


@router.get("/files", response_model=FilesResponse)
async def list_uploaded_files(
    project: dict[str, Any] = Depends(get_current_project),
) -> FilesResponse:
    return FilesResponse(files=project.get("csv_files", []))
