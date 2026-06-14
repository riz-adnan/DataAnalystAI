from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CsvFileMetadata(BaseModel):
    file_id: str
    original_name: str
    original_supabase_path: str | None = None
    cleaned_supabase_path: str | None = None
    uploaded_at: datetime
    row_count: int | None = None
    row_count_before: int = 0
    row_count_after: int = 0
    columns: list[str]
    schema_: dict[str, str] = Field(alias="schema")
    schema_preview: dict[str, Any] = {}
    sample_rows: list[dict[str, Any]]
    preprocessing_report: dict[str, Any] = {}

    model_config = ConfigDict(populate_by_name=True)


class ProjectCreate(BaseModel):
    project_name: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)
    gemini_key: str | None = Field(default=None, max_length=500)
    use_default_gemini_key: bool = False

    @field_validator("project_name")
    @classmethod
    def clean_project_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name is required")
        return value

    @field_validator("gemini_key")
    @classmethod
    def clean_gemini_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProjectLogin(BaseModel):
    project_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class ApiKeyUpdate(BaseModel):
    gemini_key: str | None = Field(default=None, max_length=500)
    use_default_gemini_key: bool = False

    @field_validator("gemini_key")
    @classmethod
    def clean_gemini_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProjectPublic(BaseModel):
    id: str
    project_name: str
    has_gemini_key: bool
    use_default_gemini_key: bool
    csv_files: list[CsvFileMetadata] = []
    chat_history: list[Any] = []
    traces: list[Any] = []
    traces_context: dict[str, Any] | list[Any] = {}
    known_relationships: list[Any] = []
    created_at: datetime
    updated_at: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    project: ProjectPublic


class FilesResponse(BaseModel):
    files: list[CsvFileMetadata]


class UploadCsvError(BaseModel):
    original_name: str
    error: str


class UploadCsvMetrics(BaseModel):
    requested_count: int
    uploaded_count: int
    failed_count: int
    total_rows_before: int
    total_rows_after: int
    total_rows: int
    total_cleaned_rows: int
    duplicates_removed: int


class UploadCsvResponse(FilesResponse):
    uploaded_count: int
    metrics: UploadCsvMetrics
    errors: list[UploadCsvError] = []
