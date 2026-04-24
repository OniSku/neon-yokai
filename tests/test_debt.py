import pytest

from app.logic.debt import (
    calculate_debt_level,
    can_buy,
    generate_debt_cards,
    nerf_buffs,
    DEBT_BUFF_NERF,
)
from app.schemas.battle import Buff


@pytest.mark.asyncio
async def test_calculate_debt_level_zero() -> None:
    assert await calculate_debt_level(0) == 0
    assert await calculate_debt_level(49) == 0


@pytest.mark.asyncio
async def test_calculate_debt_level_one() -> None:
    assert await calculate_debt_level(50) == 1
    assert await calculate_debt_level(149) == 1


@pytest.mark.asyncio
async def test_calculate_debt_level_two() -> None:
    assert await calculate_debt_level(150) == 2
    assert await calculate_debt_level(299) == 2


@pytest.mark.asyncio
async def test_calculate_debt_level_three() -> None:
    assert await calculate_debt_level(300) == 3
    assert await calculate_debt_level(499) == 3


@pytest.mark.asyncio
async def test_calculate_debt_level_four() -> None:
    assert await calculate_debt_level(500) == 4
    assert await calculate_debt_level(1000) == 4


@pytest.mark.asyncio
async def test_can_buy_allowed() -> None:
    assert await can_buy(0) is True
    assert await can_buy(1) is True


@pytest.mark.asyncio
async def test_can_buy_blocked() -> None:
    assert await can_buy(2) is False
    assert await can_buy(3) is False


@pytest.mark.asyncio
async def test_nerf_buffs_no_debt() -> None:
    buffs = [Buff(tag="SPICY_BUFF", duration=3, multiplier=1.3, flat_bonus=3)]
    result = await nerf_buffs(buffs, 0)
    assert result[0].multiplier == 1.3
    assert result[0].flat_bonus == 3


@pytest.mark.asyncio
async def test_nerf_buffs_debt_level_1() -> None:
    buffs = [Buff(tag="SPICY_BUFF", duration=3, multiplier=1.3, flat_bonus=4)]
    result = await nerf_buffs(buffs, 1)
    expected_mult = 1.0 + (1.3 - 1.0) * DEBT_BUFF_NERF
    assert result[0].multiplier == pytest.approx(expected_mult)
    assert result[0].flat_bonus == int(4 * DEBT_BUFF_NERF)


@pytest.mark.asyncio
async def test_nerf_buffs_does_not_mutate_original() -> None:
    buffs = [Buff(tag="A", duration=2, multiplier=1.5, flat_bonus=6)]
    result = await nerf_buffs(buffs, 2)
    assert buffs[0].multiplier == 1.5
    assert result[0].multiplier != 1.5


@pytest.mark.asyncio
async def test_generate_debt_cards_below_level_3() -> None:
    assert await generate_debt_cards(0) == []
    assert await generate_debt_cards(1) == []
    assert await generate_debt_cards(2) == []


@pytest.mark.asyncio
async def test_generate_debt_cards_level_3() -> None:
    cards = await generate_debt_cards(3)
    assert len(cards) == 2
    assert all(c.name == "Долговая расписка" for c in cards)
    assert all(c.type == "curse" for c in cards)
    assert all(c.card_id == -1 for c in cards)


@pytest.mark.asyncio
async def test_curse_card_unplayable() -> None:
    from app.logic.combat import execute_card
    from app.logic.deck import init_deck
    from app.schemas.battle import BattleState, CardInstance, Fighter

    debt_card = CardInstance(
        card_id=-1, name="Долговая расписка", cost=0, type="curse",
        power=0, damage_type="none", tags=["DEBT"],
    )
    state = BattleState(
        user_id=1,
        player=Fighter(hp=80, max_hp=80, energy=3),
        enemy=Fighter(name="Enemy", hp=50, max_hp=50),
    )
    state.hand = [debt_card]

    with pytest.raises(ValueError, match="Curse cards cannot be played"):
        await execute_card(state, 0)
