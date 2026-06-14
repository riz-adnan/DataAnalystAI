import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import get_settings


def _get_fernet() -> Fernet:
    settings = get_settings()
    secret = settings.api_key_encryption_secret or settings.jwt_secret_key
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_api_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    return _get_fernet().encrypt(api_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(encrypted_api_key: str | None) -> str | None:
    if not encrypted_api_key:
        return None
    return _get_fernet().decrypt(encrypted_api_key.encode("utf-8")).decode("utf-8")

