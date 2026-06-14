from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.utils.security import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_required_database(request: Request) -> AsyncIOMotorDatabase:
    database = get_database(request.app)
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MONGO_URI is not configured",
        )
    return database


async def get_current_project(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        payload = decode_access_token(credentials.credentials)
        project_id = payload.get("sub")
        if not project_id:
            raise ValueError("Missing token subject")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    database = get_required_database(request)
    try:
        object_id = ObjectId(project_id)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    project = await database.projects.find_one({"_id": object_id})

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Project no longer exists",
        )

    return project
