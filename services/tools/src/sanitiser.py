"""Prompt-injection sanitiser ensuring fetched text is treated strictly as data."""

import html
import json
import re
from typing import Any

INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions[^\n.]*[.\n]?", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|system)\s+[^\n.]*[.\n]?", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+[^\n.]*[.\n]?", re.I),
    re.compile(r"(override|bypass)\s+(the\s+)?(rubric|verdict|guardrails)[^\n.]*[.\n]?", re.I),
    re.compile(r"(give|assign|score)\s+(this|the)\s+idea\s+(a\s+)?5(\.0)?[^\n.]*[.\n]?", re.I),
    re.compile(r"<\|?(system|assistant|im_start|im_end)\|?>[^\n]*", re.I),
    re.compile(r"\[/?INST\]", re.I),
    re.compile(r"^\s*(system|developer|assistant)\s*:\s*.*$", re.I | re.M),
)

HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"[ \t]+")


def _sanitise_plain(raw: str) -> tuple[str, int]:
    text = HTML_COMMENT_RE.sub(" ", raw)
    text = HTML_TAG_RE.sub(" ", text)
    text = html.unescape(text)

    removed = 0
    for pattern in INJECTION_PATTERNS:
        text, n = pattern.subn("[REDACTED_INSTRUCTION] ", text)
        removed += n

    text = WHITESPACE_RE.sub(" ", text).strip()
    return text, removed


def _sanitise_json_value(value: Any) -> tuple[Any, int]:
    if isinstance(value, str):
        return _sanitise_plain(value)
    if isinstance(value, list):
        total = 0
        out: list[Any] = []
        for item in value:
            cleaned, count = _sanitise_json_value(item)
            total += count
            out.append(cleaned)
        return out, total
    if isinstance(value, dict):
        total = 0
        out_dict: dict[str, Any] = {}
        for k, v in value.items():
            cleaned, count = _sanitise_json_value(v)
            total += count
            out_dict[k] = cleaned
        return out_dict, total
    return value, 0


def sanitise_text(raw: str) -> tuple[str, int]:
    """Strip HTML comments/tags and model-directed prompt injections.

    If raw is valid JSON, sanitise string leaf values without breaking JSON syntax.
    """
    stripped = raw.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return _sanitise_plain(raw)
        cleaned_obj, removed = _sanitise_json_value(parsed)
        return json.dumps(cleaned_obj), removed

    return _sanitise_plain(raw)
