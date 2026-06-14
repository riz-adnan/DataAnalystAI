from functools import lru_cache

from fastapi import HTTPException, status
from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()

    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase storage is not configured",
        )

    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def upload_file_to_supabase(path: str, content: bytes, content_type: str) -> str:
    settings = get_settings()
    client = get_supabase_client()

    try:
        client.storage.from_(settings.supabase_bucket_name).upload(
            path,
            content,
            file_options={
                "content-type": content_type,
                "upsert": "false",
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload {path} to Supabase",
        ) from exc

    return path


def download_file_from_supabase(path: str) -> bytes:
    settings = get_settings()
    client = get_supabase_client()

    try:
        content = client.storage.from_(settings.supabase_bucket_name).download(path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to download {path} from Supabase",
        ) from exc

    if isinstance(content, bytes):
        return content

    return bytes(content)


def delete_file_from_supabase(path: str) -> bool:
    settings = get_settings()
    client = get_supabase_client()

    try:
        client.storage.from_(settings.supabase_bucket_name).remove([path])
    except Exception:
        return False

    return True
