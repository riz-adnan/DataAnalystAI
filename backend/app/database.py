from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.mongo_client = None
    app.state.database = None

    if settings.mongo_uri:
        client = AsyncIOMotorClient(settings.mongo_uri)
        app.state.mongo_client = client
        app.state.database = client[settings.mongo_database]
        await app.state.database.projects.create_index("project_name", unique=True)

    yield

    if app.state.mongo_client is not None:
        app.state.mongo_client.close()


def get_database(app: FastAPI) -> AsyncIOMotorDatabase | None:
    return getattr(app.state, "database", None)
