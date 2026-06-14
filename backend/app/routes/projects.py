from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pymongo.errors import DuplicateKeyError

from app.models.project import ApiKeyUpdate, LoginResponse, ProjectCreate, ProjectLogin, ProjectPublic
from app.services.api_key_service import encrypt_api_key
from app.services.auth_service import get_current_project, get_required_database
from app.utils.security import create_access_token, hash_password, verify_password


router = APIRouter(prefix="/projects", tags=["projects"])


def project_to_public(project: dict[str, Any]) -> ProjectPublic:
    return ProjectPublic(
        id=str(project["_id"]),
        project_name=project["project_name"],
        has_gemini_key=bool(project.get("gemini_key")),
        use_default_gemini_key=project.get("use_default_gemini_key", False),
        csv_files=project.get("csv_files", []),
        chat_history=project.get("chat_history", []),
        traces=project.get("traces", []),
        traces_context=project.get("traces_context", {}),
        known_relationships=project.get("known_relationships", []),
        created_at=project["created_at"],
        updated_at=project["updated_at"],
    )


@router.post("/create", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, request: Request) -> LoginResponse:
    database = get_required_database(request)
    now = datetime.now(timezone.utc)

    use_default = payload.use_default_gemini_key or not payload.gemini_key
    project_document = {
        "project_name": payload.project_name,
        "password_hash": hash_password(payload.password),
        "gemini_key": None if use_default else encrypt_api_key(payload.gemini_key),
        "use_default_gemini_key": use_default,
        "csv_files": [],
        "chat_history": [],
        "traces": [],
        "traces_context": {},
        "known_relationships": [],
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = await database.projects.insert_one(project_document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project name already exists",
        ) from exc

    project_document["_id"] = result.inserted_id
    token = create_access_token(str(result.inserted_id), {"project_name": payload.project_name})
    return LoginResponse(access_token=token, project=project_to_public(project_document))


@router.post("/login", response_model=LoginResponse)
async def login_project(payload: ProjectLogin, request: Request) -> LoginResponse:
    database = get_required_database(request)
    project = await database.projects.find_one({"project_name": payload.project_name.strip()})

    if project is None or not verify_password(payload.password, project["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid project name or password",
        )

    token = create_access_token(str(project["_id"]), {"project_name": project["project_name"]})
    return LoginResponse(access_token=token, project=project_to_public(project))


@router.get("/me", response_model=ProjectPublic)
async def get_me(project: dict[str, Any] = Depends(get_current_project)) -> ProjectPublic:
    return project_to_public(project)


@router.put("/api-key", response_model=ProjectPublic)
async def update_api_key(
    payload: ApiKeyUpdate,
    request: Request,
    project: dict[str, Any] = Depends(get_current_project),
) -> ProjectPublic:
    database = get_required_database(request)
    use_default = payload.use_default_gemini_key or not payload.gemini_key
    update = {
        "$set": {
            "gemini_key": None if use_default else encrypt_api_key(payload.gemini_key),
            "use_default_gemini_key": use_default,
            "updated_at": datetime.now(timezone.utc),
        }
    }

    await database.projects.update_one({"_id": project["_id"]}, update)
    updated_project = await database.projects.find_one({"_id": project["_id"]})
    return project_to_public(updated_project)

