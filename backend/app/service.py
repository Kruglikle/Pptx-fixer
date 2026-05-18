from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from pymorphy3 import MorphAnalyzer
from symspellpy import SymSpell, Verbosity
from wordfreq import top_n_list, zipf_frequency

from .schemas import Issue, SlideText

WORD_RE = re.compile(r"[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z-]*")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
REPEATED_CYRILLIC_RE = re.compile(r"([а-яё])\1+")
PREPOSITIONS = (
    "без",
    "для",
    "до",
    "из",
    "за",
    "к",
    "ко",
    "на",
    "над",
    "о",
    "об",
    "от",
    "по",
    "под",
    "при",
    "с",
    "со",
    "у",
    "в",
    "во",
)


class PresentationChecker:
    def __init__(self) -> None:
        self.morph = MorphAnalyzer()
        self.symspell = self._load_symspell()
        self.language_tool = self._load_language_tool()

    def check_slides(self, slides: Iterable[SlideText]) -> list[Issue]:
        issues: list[Issue] = []
        seen: set[tuple[int, int | None, int | None, str, str | None]] = set()

        for slide in slides:
            slide_issues = [
                *self._check_words(slide),
                *self._check_agreement(slide),
                *self._check_language_tool(slide),
            ]
            for issue in slide_issues:
                key = (issue.slide, issue.start, issue.end, issue.issue_type, issue.suggestion)
                if key not in seen:
                    issues.append(issue)
                    seen.add(key)

        return issues

    def _check_words(self, slide: SlideText) -> list[Issue]:
        issues: list[Issue] = []
        for match in WORD_RE.finditer(slide.text):
            word = match.group(0).strip("-")
            start = match.start()
            end = match.end()
            if len(word) < 3 or not CYRILLIC_RE.search(word) or word.isupper():
                continue

            normalized = word.lower().replace("ё", "е")
            if self._is_known_word(normalized):
                continue

            if issue := self._detect_repeated_letters(slide.index, word, normalized, start, end):
                issues.append(issue)
                continue

            if issue := self._detect_merged_preposition(slide.index, word, normalized, start, end):
                issues.append(issue)
                continue

            if issue := self._detect_swapped_letters(slide.index, word, normalized, start, end):
                issues.append(issue)
                continue

            if suggestion := self._symspell_suggestion(normalized):
                issues.append(
                    Issue(
                        slide=slide.index,
                        fragment=word,
                        issue_type="spelling",
                        message="Ошибка! Вероятная орфографическая ошибка.",
                        suggestion=self._preserve_case(word, suggestion),
                        source="symspell",
                        start=start,
                        end=end,
                    )
                )
            else:
                issues.append(
                    Issue(
                        slide=slide.index,
                        fragment=word,
                        issue_type="spelling",
                        message="Проверьте написание слова: оно не найдено в локальном словаре.",
                        source="pymorphy3",
                        start=start,
                        end=end,
                    )
                )

        return issues

    def _check_agreement(self, slide: SlideText) -> list[Issue]:
        issues: list[Issue] = []
        tokens = [match for match in WORD_RE.finditer(slide.text) if CYRILLIC_RE.search(match.group(0))]

        for left_match, right_match in zip(tokens, tokens[1:]):
            left = left_match.group(0)
            right = right_match.group(0)
            left_parse = self.morph.parse(left.lower())[0]
            right_parse = self.morph.parse(right.lower())[0]
            if "ADJF" not in left_parse.tag or "NOUN" not in right_parse.tag:
                continue

            left_gender = left_parse.tag.gender
            right_gender = right_parse.tag.gender
            left_number = left_parse.tag.number
            right_number = right_parse.tag.number
            left_case = left_parse.tag.case
            right_case = right_parse.tag.case

            gender_ok = not left_gender or not right_gender or left_gender == right_gender
            number_ok = not left_number or not right_number or left_number == right_number
            case_ok = not left_case or not right_case or left_case == right_case

            if not (gender_ok and number_ok and case_ok):
                issues.append(
                    Issue(
                        slide=slide.index,
                        fragment=f"{left} {right}",
                        issue_type="agreement",
                        message="Проверьте согласованность окончаний.",
                        suggestion=self._agree_adjective(left, right),
                        source="pymorphy3",
                        start=left_match.start(),
                        end=right_match.end(),
                    )
                )

        return issues

    def _check_language_tool(self, slide: SlideText) -> list[Issue]:
        if not self.language_tool or not slide.text.strip():
            return []

        issues: list[Issue] = []
        try:
            matches = self.language_tool.check(slide.text)
        except Exception:
            return []

        for match in matches:
            end = match.offset + match.errorLength
            fragment = slide.text[match.offset:end].strip()
            if not fragment:
                continue
            issues.append(
                Issue(
                    slide=slide.index,
                    fragment=fragment,
                    issue_type="grammar",
                    message=match.message,
                    suggestion=match.replacements[0] if match.replacements else None,
                    source="language-tool",
                    start=match.offset,
                    end=end,
                )
            )
        return issues

    def _detect_repeated_letters(self, slide: int, word: str, normalized: str, start: int, end: int) -> Issue | None:
        for match in REPEATED_CYRILLIC_RE.finditer(normalized):
            collapsed = normalized[: match.start()] + match.group(1) + normalized[match.end() :]
            if self._is_known_word(collapsed):
                return Issue(
                    slide=slide,
                    fragment=word,
                    issue_type="typo",
                    message="Ошибка! Вероятно задвоена буква.",
                    suggestion=self._preserve_case(word, collapsed),
                    source="rules",
                    start=start,
                    end=end,
                )

        for size in (2, 3):
            for idx in range(0, len(normalized) - size * 2 + 1):
                chunk = normalized[idx : idx + size]
                if chunk == normalized[idx + size : idx + size * 2]:
                    collapsed = normalized[:idx] + chunk + normalized[idx + size * 2 :]
                    if self._is_known_word(collapsed):
                        return Issue(
                            slide=slide,
                            fragment=word,
                            issue_type="typo",
                            message="Ошибка! Вероятно задвоен слог.",
                            suggestion=self._preserve_case(word, collapsed),
                            source="rules",
                            start=start,
                            end=end,
                        )
        return None

    def _detect_merged_preposition(self, slide: int, word: str, normalized: str, start: int, end: int) -> Issue | None:
        for prep in PREPOSITIONS:
            if normalized.startswith(prep) and len(normalized) > len(prep) + 2:
                rest = normalized[len(prep) :]
                if self._is_known_word(rest):
                    return Issue(
                        slide=slide,
                        fragment=word,
                        issue_type="typo",
                        message="Ошибка! Вероятно слитное написание предлога.",
                        suggestion=self._preserve_case(word, f"{prep} {rest}"),
                        source="rules",
                        start=start,
                        end=end,
                    )
        return None

    def _detect_swapped_letters(self, slide: int, word: str, normalized: str, start: int, end: int) -> Issue | None:
        letters = list(normalized)
        for idx in range(len(letters) - 1):
            swapped = letters.copy()
            swapped[idx], swapped[idx + 1] = swapped[idx + 1], swapped[idx]
            candidate = "".join(swapped)
            if candidate != normalized and self._is_known_word(candidate):
                return Issue(
                    slide=slide,
                    fragment=word,
                    issue_type="typo",
                    message="Ошибка! Вероятно неверный порядок букв.",
                    suggestion=self._preserve_case(word, candidate),
                    source="rules",
                    start=start,
                    end=end,
                )
        return None

    def _agree_adjective(self, adjective: str, noun: str) -> str | None:
        noun_parses = self.morph.parse(noun.lower())
        noun_parse = next((parse for parse in noun_parses if parse.tag.case == "nomn"), noun_parses[0])
        adjective_parse = self.morph.parse(adjective.lower())[0]
        required = {tag for tag in (noun_parse.tag.gender, noun_parse.tag.number, noun_parse.tag.case) if tag}
        if not required:
            return None
        inflected = adjective_parse.inflect(required)
        if not inflected:
            return None
        return self._preserve_case(adjective, f"{inflected.word} {noun}")

    def _is_known_word(self, word: str) -> bool:
        if len(word) < 3:
            return True
        return self.morph.word_is_known(word) or bool(self.symspell.words.get(word))

    def _symspell_suggestion(self, word: str) -> str | None:
        max_distance = 1 if len(word) <= 5 else 2
        suggestions = self.symspell.lookup(word, Verbosity.CLOSEST, max_edit_distance=max_distance, include_unknown=False)
        if not suggestions:
            return None

        ranked = sorted(
            suggestions[:8],
            key=lambda item: (
                item.distance,
                -zipf_frequency(item.term, "ru"),
                -item.count,
                len(item.term),
            ),
        )
        suggestion = ranked[0].term
        return suggestion if suggestion != word else None

    @staticmethod
    def _preserve_case(source: str, suggestion: str) -> str:
        if not source:
            return suggestion
        return suggestion[:1].upper() + suggestion[1:] if source[0].isupper() else suggestion

    @staticmethod
    def _load_symspell() -> SymSpell:
        symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
        dictionary_path = Path(os.getenv("SYMSPELL_DICTIONARY", "/app/data/frequency_dictionary_ru.txt"))
        if dictionary_path.exists():
            symspell.load_dictionary(str(dictionary_path), term_index=0, count_index=1, separator=" ")

        top_n = int(os.getenv("WORDFREQ_TOP_N", "60000"))
        for rank, term in enumerate(top_n_list("ru", top_n), start=1):
            normalized = term.lower().replace("ё", "е")
            if not CYRILLIC_RE.search(normalized) or not normalized.isalpha() or len(normalized) < 3:
                continue
            symspell.create_dictionary_entry(normalized, max(top_n - rank + 1, 1))

        return symspell

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_language_tool():
        if os.getenv("ENABLE_LANGUAGE_TOOL", "false").lower() not in {"1", "true", "yes"}:
            return None
        try:
            import language_tool_python

            return language_tool_python.LanguageTool("ru-RU")
        except Exception:
            return None
