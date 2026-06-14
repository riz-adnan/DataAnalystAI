from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import get_database, lifespan
from app.routes import chat, projects, uploads


settings = get_settings()

app = FastAPI(
    title="DataAnalyst AI API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(uploads.router)
app.include_router(chat.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "DataAnalyst AI backend is running"}


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    database = get_database(request.app)
    mongo_status = "not_configured"

    if database is not None:
        try:
            await database.command("ping")
            mongo_status = "connected"
        except Exception:
            mongo_status = "unreachable"

    return {"status": "ok", "mongo": mongo_status}
