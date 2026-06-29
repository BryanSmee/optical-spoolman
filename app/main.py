import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .analyzer import analyze_image
from .config import settings
from .models import CreateRequest
from .spoolman import SpoolmanClient, apply_defaults

logger = logging.getLogger("optical_spoolman")

app = FastAPI(title="Optical Spoolman")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
ALLOWED_MEDIA = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict:
    spoolman_ok = await SpoolmanClient(settings.spoolman_url).ping()
    return {
        "anthropic_configured": bool(settings.anthropic_api_key),
        "spoolman_url": settings.spoolman_url,
        "spoolman_reachable": spoolman_ok,
    }


@app.post("/api/analyze")
def analyze(file: UploadFile = File(...)) -> dict:
    if not settings.anthropic_api_key:
        raise HTTPException(500, "ANTHROPIC_API_KEY is not configured on the server.")

    media_type = (file.content_type or "").lower()
    if media_type not in ALLOWED_MEDIA:
        raise HTTPException(
            400, f"Unsupported image type '{media_type}'. Use JPEG, PNG, WebP, or GIF."
        )

    data = file.file.read()
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image is too large (max 15 MB).")

    try:
        extracted = analyze_image(data, media_type)
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the client
        logger.exception("Vision analysis failed")
        raise HTTPException(502, f"Vision analysis failed: {exc}")

    return apply_defaults(extracted)


@app.post("/api/create")
async def create(req: CreateRequest) -> dict:
    client = SpoolmanClient(settings.spoolman_url)
    try:
        return await client.create_all(req)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            502, f"Spoolman returned {exc.response.status_code}: {exc.response.text}"
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            502, f"Could not reach Spoolman at {settings.spoolman_url}: {exc}"
        )
