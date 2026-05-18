from __future__ import annotations

import json
import os
import re
from typing import Iterable

import requests

from .schemas import Issue, SlideText


class OllamaChecker:
    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_OLLAMA", "false").lower() in {"1", "true", "yes"}
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))

    def check_slides(self, slides: Iterable[SlideText]) -> list[Issue]:
        if not self.enabled:
            return []

        issues: list[Issue] = []
        for slide in slides:
            if not slide.text.strip():
                continue
            issues.extend(self._check_slide(slide))
        return issues

    def _check_slide(self, slide: SlideText) -> list[Issue]:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": self._prompt(slide.text),
            "options": {
                "temperature": 0,
                "num_ctx": 4096,
            },
        }

        try:
            response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
            response.raise_for_status()
            raw = response.json().get("response", "{}")
            parsed = json.loads(raw)
        except Exception:
            return []

        raw_issues = parsed.get("issues", [])
        if not isinstance(raw_issues, list):
            return []

        issues: list[Issue] = []
        for item in raw_issues:
            if not isinstance(item, dict):
                continue

            fragment = str(item.get("fragment", "")).strip()
            if not fragment:
                continue

            start = slide.text.find(fragment)
            suggestion = item.get("suggestion")
            issue_type = item.get("issue_type", "grammar")
            if issue_type not in {"typo", "spelling", "agreement", "grammar"}:
                issue_type = "grammar"

            issues.append(
                Issue(
                    slide=slide.index,
                    fragment=fragment,
                    issue_type=issue_type,
                    message=str(item.get("message", "Проверьте фрагмент.")),
                    suggestion=str(suggestion).strip() if suggestion else None,
                    source=f"ollama:{self.model}",
                    start=start if start >= 0 else None,
                    end=start + len(fragment) if start >= 0 else None,
                )
            )
        return issues

    @staticmethod
    def _prompt(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        return f"""
Ты локальный корректор русского текста в презентации.
Найди только реальные ошибки: опечатки, орфографию, слитные предлоги, несогласованные окончания.
Не исправляй стиль, тональность и смысл. Не переписывай нормальный текст.

Верни строго JSON:
{{
  "issues": [
    {{
      "fragment": "точный фрагмент из текста",
      "issue_type": "typo|spelling|agreement|grammar",
      "message": "короткое объяснение",
      "suggestion": "исправление или null"
    }}
  ]
}}

Текст:
{cleaned}
""".strip()
