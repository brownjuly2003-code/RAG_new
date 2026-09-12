"""GR-2 uses the same canonical keys for extraction and query entities."""

import pytest

from ingestion.entity_normalization import normalize_entities


@pytest.mark.parametrize("aliases, expected", [
    (["AWB", "air waybill", "авианакладная"], ["awb"]),
    (["HAWB", "house air waybill", "MAWB", "master air waybill"], ["hawb", "mawb"]),
    (["Booking", "бронирование"], ["booking"]),
    ([" сотрудник ", "Компания", "документ", "document", "company", "employee"], []),
    (["  Dangerous   GOODS ", "dangerous goods", "cold-chain"], ["dangerous goods", "cold chain"]),
    (["awb customs", "booking cancellation"], ["awb customs", "booking cancellation"]),
    (["", "---", "x" * 129, 123, None], []),
])
def test_normalization(aliases, expected):
    assert normalize_entities(aliases) == expected


def test_normalization_is_idempotent_and_bounded():
    values = [f"term {i}" for i in range(20)]
    result = normalize_entities(values)
    assert result == values[:12]
    assert normalize_entities(result) == result
