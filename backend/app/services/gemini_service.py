import asyncio
import json
import re
import urllib.error
import urllib.request
from typing import Any

from fastapi import HTTPException, status

from app.config import get_settings
from app.services.api_key_service import decrypt_api_key


GEMINI_MODEL = "gemini-2.5-flash-lite"


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text


def _get_project_api_key(project: dict[str, Any]) -> str:
    settings = get_settings()
    if project.get("use_default_gemini_key", False):
        api_key = settings.default_gemini_api_key
    else:
        api_key = decrypt_api_key(project.get("gemini_key"))

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini API key is not configured for this project",
        )
    return api_key


def _call_gemini_sync(api_key: str, prompt: str, response_format: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1},
    }
    if response_format == "json":
        payload["generationConfig"]["responseMimeType"] = "application/json"

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") or str(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini request failed: {detail[:300]}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini request failed: {exc}",
        ) from exc

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini response did not include text output",
        ) from exc


async def call_gemini(
    project: dict[str, Any],
    prompt: str,
    response_format: str = "json",
) -> dict[str, Any] | str:
    api_key = _get_project_api_key(project)
    text = await asyncio.to_thread(_call_gemini_sync, api_key, prompt, response_format)
    print("\n========== GEMINI RESPONSE START ==========")
    print(text)
    print("========== GEMINI RESPONSE END ==========\n")

    if response_format != "json":
        return text

    cleaned = _strip_json_fences(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini returned invalid JSON",
        ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini JSON response must be an object",
        )
    return parsed
