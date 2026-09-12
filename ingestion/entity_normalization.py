"""Shared, bounded normalization for GR-2 extracted and query entities."""

from collections.abc import Iterable

from vectordb._base_manager import _tokenize_for_bm25

_ALIASES = {
    "air waybill": "awb",
    "авианакладная": "awb",
    "house air waybill": "hawb",
    "master air waybill": "mawb",
    "бронирование": "booking",
}
_STOP_WORDS = {"сотрудник", "компания", "документ", "employee", "company", "document"}


def normalize_entities(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or len(value.strip()) > 128:
            continue
        key = " ".join(_tokenize_for_bm25(value))
        key = _ALIASES.get(key, key)
        if not key or key in _STOP_WORDS or key in result:
            continue
        result.append(key)
        if len(result) == 12:
            break
    return result
