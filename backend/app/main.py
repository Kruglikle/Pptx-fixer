from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from .llm_checker import OllamaChecker
from .pptx_reader import extract_pptx_slides
from .schemas import CheckResponse
from .service import PresentationChecker

app = FastAPI(
    title="Local PPTX Proofreader",
    description="Local MVP service for checking PPTX text by slide.",
    version="0.1.0",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

checker = PresentationChecker()
ollama_checker = OllamaChecker()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/test.txt", response_class=PlainTextResponse)
def test_report() -> str:
    return "Тестовый отчет"


@app.post("/api/check-pptx", response_model=CheckResponse)
async def check_pptx(file: UploadFile = File(...), use_llm: bool = Form(False)) -> CheckResponse:
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        raise HTTPException(status_code=400, detail="Поддерживается только формат .pptx")

    suffix = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        while chunk := await file.read(1024 * 1024):
            tmp.write(chunk)

    try:
        slides = extract_pptx_slides(tmp_path)
        issues = checker.check_slides(slides)
        if use_llm:
            issues = _merge_issues(issues, ollama_checker.check_slides(slides))
        return CheckResponse(filename=file.filename, slides_count=len(slides), slides=slides, issues=issues)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


def _merge_issues(base: list, extra: list) -> list:
    merged = list(base)
    seen = {
        (issue.slide, issue.start, issue.end, issue.fragment.lower(), issue.suggestion)
        for issue in merged
    }

    for issue in extra:
        key = (issue.slide, issue.start, issue.end, issue.fragment.lower(), issue.suggestion)
        if key not in seen:
            merged.append(issue)
            seen.add(key)

    return merged
