import json
import logging
import uuid
from pathlib import Path

import openai
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.embeddings import build_index, search_index
from backend.extractor import _stage1_extract, _stage2_refine, extract_menu

from dotenv import load_dotenv
load_dotenv()

_index_store: dict = {}

handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
handler.setFormatter(formatter)

for name in ("backend.main", "backend.extractor"):
    lg = logging.getLogger(name)
    lg.setLevel(logging.INFO)
    lg.addHandler(handler)
    lg.propagate = False

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
EXTENSION_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _resolve_mime(content_type, filename):
    mime = content_type or ""
    if mime and mime != "application/octet-stream":
        return mime

    suffix = Path(filename or "").suffix.lower()
    return EXTENSION_MIME_TYPES.get(suffix, mime)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(
        "Request: method=%s path=%s query_params=%s",
        request.method,
        request.url.path,
        dict(request.query_params),
    )
    response = await call_next(request)
    logger.info(
        "Response: method=%s path=%s status_code=%s",
        request.method,
        request.url.path,
        response.status_code,
    )
    return response


@app.post("/scan/stage1")
async def scan_stage1(
    file: UploadFile = File(...),
    dietary_restrictions: str = Form("[]"),
):
    mime = _resolve_mime(file.content_type, file.filename)
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


class ExtractResponse(BaseModel):
    scan_id: str
    items: list[dict]
    ocr_text: str
    latency_breakdown: dict
    cost_usd: float


class SearchRequest(BaseModel):
    scan_id: str
    query: str
    threshold: float = 1.3


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


@app.post("/extract", response_model=ExtractResponse)
async def extract(
    file: UploadFile = File(...),
    dietary_restrictions: str = Form("[]"),
):
    mime = _resolve_mime(file.content_type, file.filename)
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{mime}'. Upload a JPEG, PNG, WEBP, or GIF image.",
        )

    image_bytes = await file.read()
    restrictions = json.loads(dietary_restrictions)

    try:
        items, usage, cost_usd = extract_menu(
            image_bytes,
            mime_type=mime,
            restrictions=restrictions,
        )
        faiss_index, indexed_items = build_index(items)
        scan_id = str(uuid.uuid4())
        _index_store[scan_id] = (faiss_index, indexed_items)
        logger.info(
            "extract: scan_id=%s indexed_items=%d",
            scan_id,
            len(indexed_items),
        )
    except openai.OpenAIError as exc:
        logger.exception("OpenAI API error")
        raise HTTPException(status_code=502, detail=f"OpenAI error: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error during extraction")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ExtractResponse(
        scan_id=scan_id,
        items=items,
        ocr_text=usage.get("ocr_text", ""),
        latency_breakdown=usage.get("latency_breakdown", {}),
        cost_usd=cost_usd,
    )


@app.post("/search")
async def search(body: SearchRequest):
    if body.scan_id not in _index_store:
        raise HTTPException(status_code=404, detail="Scan not found. Run /extract first.")

    faiss_index, items = _index_store[body.scan_id]
    try:
        results = search_index(body.query, faiss_index, items, k=len(items))
        results = [result for result in results if result.get("score", 0) <= body.threshold]
    except Exception as exc:
        logger.exception("Unexpected error during search")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"results": results, "query": body.query, "scan_id": body.scan_id}


class RefineRequest(BaseModel):
    name: str
    description: str = ""
    dietary_restrictions: list[str] = []


@app.post("/refine-item")
async def refine_item(body: RefineRequest):
    item_dict = {"name": body.name, "description": body.description}
    restrictions = body.dietary_restrictions or None
    logger.info(
        "refine-item request: name=%s description=%s dietary_restrictions=%s",
        body.name,
        body.description,
        body.dietary_restrictions,
    )
    try:
        refined, _usage = _stage2_refine([item_dict], restrictions)
    except openai.OpenAIError as exc:
        logger.exception("OpenAI API error")
        raise HTTPException(status_code=502, detail=f"OpenAI error: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error during refinement")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info("refine-item: raw _stage2_refine output=%s", refined)

    if not refined:
        logger.warning(
            "refine-item: _stage2_refine returned empty for input item=%s restrictions=%s",
            item_dict,
            restrictions,
        )
        raise HTTPException(status_code=422, detail="Refinement produced no output")

    result = refined[0]
    result["name"] = body.name
    result["description"] = body.description if body.description.strip() else None

    return {"item": result}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
