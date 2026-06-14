from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongo_uri: str = Field(default="", alias="MONGO_URI")
    mongo_database: str = Field(default="dataanalyst_ai", alias="MONGO_DATABASE")
    frontend_origin: str = Field(default="http://localhost:3000", alias="FRONTEND_ORIGIN")
    default_gemini_api_key: str = Field(default="", alias="DEFAULT_GEMINI_API_KEY")
    jwt_secret_key: str = Field(default="change-this-development-secret", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60 * 24 * 7, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    api_key_encryption_secret: str = Field(default="", alias="API_KEY_ENCRYPTION_SECRET")
    max_upload_file_bytes: int = Field(default=50 * 1024 * 1024, alias="MAX_UPLOAD_FILE_BYTES")
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_bucket_name: str = Field(default="csv-files", alias="SUPABASE_BUCKET_NAME")

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
