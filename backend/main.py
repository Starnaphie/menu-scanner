import json
import logging
from pathlib import Path

import openai
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.extractor import _stage1_extract, _stage2_refine, _stage3_explain_flags, extract_menu

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/scan/stage1")
async def scan_stage1(
    file: UploadFile = File(...),
    dietary_restrictions: str = Form("[]"),
):
    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{mime}'. Upload a JPEG, PNG, WEBP, or GIF image.",
        )

    image_bytes = await file.read()

    try:
        items, _usage = _stage1_extract(image_bytes, mime_type=mime)
    except openai.OpenAIError as exc:
        logger.exception("OpenAI API error")
        raise HTTPException(status_code=502, detail=f"OpenAI error: {exc}") from exc
    except json.JSONDecodeError as exc:
        logger.exception("Model returned malformed JSON")
        raise HTTPException(
            status_code=502,
            detail=f"Model returned malformed JSON: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during extraction")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"items": items}


class Stage2Request(BaseModel):
    items: list[dict]
    dietary_restrictions: list[str] = []


@app.post("/scan/stage2")
async def scan_stage2(body: Stage2Request):
    restrictions = body.dietary_restrictions or None
    try:
        items, _usage = _stage2_refine(body.items, restrictions)
    except openai.OpenAIError as exc:
        logger.exception("OpenAI API error")
        raise HTTPException(status_code=502, detail=f"OpenAI error: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error during refinement")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"items": items}


class RefineRequest(BaseModel):
    name: str
    description: str = ""
    dietary_restrictions: list[str] = []


@app.post("/refine-item")
async def refine_item(body: RefineRequest):
    item_dict = {"name": body.name, "description": body.description}
    restrictions = body.dietary_restrictions or None
    logger.debug("refine-item called with item=%s restrictions=%s", item_dict, restrictions)
    try:
        refined, _usage = _stage2_refine([item_dict], restrictions)
    except openai.OpenAIError as exc:
        logger.exception("OpenAI API error")
        raise HTTPException(status_code=502, detail=f"OpenAI error: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error during refinement")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not refined:
        raise HTTPException(status_code=422, detail="Refinement produced no output")

    result = refined[0]
    result["name"] = body.name
    result["description"] = body.description if body.description.strip() else None

    try:
        flag_explanations, _ = _stage3_explain_flags(result, restrictions)
    except openai.OpenAIError as exc:
        logger.exception("OpenAI API error during flag explanation")
        raise HTTPException(status_code=502, detail=f"OpenAI error: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error during flag explanation")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Remove flags that stage 3 determined are safe
    safe_restrictions = {
        e["restriction"].lower()
        for e in flag_explanations
        if e.get("verdict") == "safe"
    }
    result["user_dietary_flags"] = [
        f for f in result.get("user_dietary_flags", [])
        if f.lower() not in safe_restrictions
    ]

    return {"item": result}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
