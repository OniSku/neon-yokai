import pytest

from app.logic.craft import craft_dish, resolve_dominant_flavor, sum_ingredient_weights
from app.models.ingredient import Ingredient
from app.schemas.craft import FlavorProfile


def _ingredient(
    name: str = "Chili",
    spicy: int = 0,
    sour: int = 0,
    sweet: int = 0,
    bitter: int = 0,
) -> Ingredient:
    ing = Ingredient.__new__(Ingredient)
    ing.id = 1
    ing.name = name
    ing.spicy = spicy
    ing.sour = sour
    ing.sweet = sweet
    ing.bitter = bitter
    ing.rarity = "common"
    return ing


@pytest.mark.asyncio
async def test_sum_ingredient_weights_single() -> None:
    profile = await sum_ingredient_weights([
        _ingredient(spicy=3, sour=1, sweet=0, bitter=2),
    ])
    assert profile.spicy == 3
    assert profile.sour == 1
    assert profile.sweet == 0
    assert profile.bitter == 2


@pytest.mark.asyncio
async def test_sum_ingredient_weights_multiple() -> None:
    profile = await sum_ingredient_weights([
        _ingredient(spicy=3, sour=1),
        _ingredient(spicy=2, sweet=4),
        _ingredient(bitter=5),
    ])
    assert profile.spicy == 5
    assert profile.sour == 1
    assert profile.sweet == 4
    assert profile.bitter == 5


@pytest.mark.asyncio
async def test_resolve_dominant_flavor_clear_winner() -> None:
    profile = FlavorProfile(spicy=10, sour=2, sweet=1, bitter=0)
    result = await resolve_dominant_flavor(profile)
    assert result == "spicy"


@pytest.mark.asyncio
async def test_resolve_dominant_flavor_below_threshold() -> None:
    profile = FlavorProfile(spicy=2, sour=1, sweet=1, bitter=1)
    result = await resolve_dominant_flavor(profile)
    assert result is None


@pytest.mark.asyncio
async def test_craft_dish_returns_buff_for_dominant() -> None:
    ingredients = [
        _ingredient(spicy=6, sour=1),
        _ingredient(spicy=4),
    ]
    result = await craft_dish(ingredients)
    assert result.dominant_flavor == "spicy"
    assert "SPICY_BUFF" in result.buffs


@pytest.mark.asyncio
async def test_craft_dish_no_buff_when_no_dominant() -> None:
    ingredients = [
        _ingredient(spicy=1, sour=1, sweet=1, bitter=1),
    ]
    result = await craft_dish(ingredients)
    assert result.dominant_flavor is None
    assert len(result.buffs) == 0
