from __future__ import annotations

from difflib import SequenceMatcher
import re


_PUNCT_RE = re.compile(r"[\s\-—_·.。,:：/\\()（）\[\]【】'\"“”‘’!?！？]+")


def normalize_match_key(value: str) -> str:
    return _PUNCT_RE.sub("", str(value or "")).casefold()


def normalize_text(value: str) -> str:
    return str(value or "").strip().casefold()


def fuzzy_name_score(query: str, target: str) -> int:
    query_key = normalize_match_key(query)
    target_key = normalize_match_key(target)
    if not query_key or not target_key:
        return 0

    if query_key == target_key:
        return 120
    if target_key.startswith(query_key):
        return 104
    if query_key in target_key:
        return 96
    if target_key in query_key:
        return 90
    if len(query_key) >= 2 and _is_subsequence(query_key, target_key):
        return 82

    overlap = len(set(query_key) & set(target_key))
    if overlap >= max(2, len(query_key) - 1):
        return 72

    ratio = SequenceMatcher(None, query_key, target_key).ratio()
    if ratio >= 0.82:
        return 68
    if ratio >= 0.7:
        return 58
    if ratio >= 0.62:
        return 48
    return 0


def is_fuzzy_match(query: str, target: str, threshold: int = 58) -> bool:
    return fuzzy_name_score(query, target) >= threshold


def _is_subsequence(query: str, target: str) -> bool:
    index = 0
    for char in target:
        if index < len(query) and query[index] == char:
            index += 1
            if index == len(query):
                return True
    return False
