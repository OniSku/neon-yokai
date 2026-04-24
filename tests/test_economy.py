import math

import pytest

from app.logic.debt import DEBT_LEVELS, get_debt_level_info
from app.logic.economy import INTEREST_RATE


@pytest.mark.asyncio
async def test_debt_level_names() -> None:
    info_0 = await get_debt_level_info(0)
    assert info_0["name"] == "Чисто"
    assert info_0["debuff"] is None

    info_1 = await get_debt_level_info(1)
    assert info_1["name"] == "Стыд"

    info_2 = await get_debt_level_info(2)
    assert info_2["name"] == "Давление"

    info_3 = await get_debt_level_info(3)
    assert info_3["name"] == "Угрозы"

    info_4 = await get_debt_level_info(4)
    assert info_4["name"] == "Коллекторы"


@pytest.mark.asyncio
async def test_debt_level_info_unknown_falls_back() -> None:
    info = await get_debt_level_info(99)
    assert info["name"] == "Чисто"


def test_interest_calculation() -> None:
    debt = 100
    expected = math.ceil(debt * INTEREST_RATE)
    assert expected == 15


def test_interest_zero_debt() -> None:
    debt = 0
    expected = math.ceil(debt * INTEREST_RATE)
    assert expected == 0


def test_all_debt_levels_defined() -> None:
    for level in range(5):
        assert level in DEBT_LEVELS
        assert "name" in DEBT_LEVELS[level]
        assert "debuff" in DEBT_LEVELS[level]
