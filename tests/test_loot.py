import pytest

from app.logic.loot import CREDITS_PER_WIN, LOOT_MAX, LOOT_MIN


def test_loot_constants() -> None:
    assert LOOT_MIN >= 1
    assert LOOT_MAX >= LOOT_MIN
    assert CREDITS_PER_WIN > 0


@pytest.mark.asyncio
async def test_generate_loot_returns_correct_structure() -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.credits = 0
    mock_user.experience = 0

    mock_ingredient = MagicMock()
    mock_ingredient.id = 5
    mock_ingredient.name = "Test Ingredient"

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_ingredient]

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_inv_result = MagicMock()
    mock_inv_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[mock_result, mock_inv_result])
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    from app.logic.loot import generate_loot

    with patch("app.logic.loot.random.randint", return_value=1):
        with patch("app.logic.loot.random.choices", return_value=[mock_ingredient]):
            loot = await generate_loot(mock_session, mock_user)

    assert len(loot) == 1
    assert loot[0]["ingredient_id"] == 5
    assert loot[0]["name"] == "Test Ingredient"
    assert loot[0]["quantity"] == 1
    assert mock_user.credits == CREDITS_PER_WIN
    assert mock_user.experience == 10


@pytest.mark.asyncio
async def test_generate_loot_increments_existing_inventory() -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.credits = 10
    mock_user.experience = 5

    mock_ingredient = MagicMock()
    mock_ingredient.id = 3
    mock_ingredient.name = "Existing Ingredient"

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_ingredient]

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_inv_item = MagicMock()
    mock_inv_item.quantity = 2

    mock_inv_result = MagicMock()
    mock_inv_result.scalar_one_or_none.return_value = mock_inv_item

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[mock_result, mock_inv_result])
    mock_session.commit = AsyncMock()

    from app.logic.loot import generate_loot

    with patch("app.logic.loot.random.randint", return_value=1):
        with patch("app.logic.loot.random.choices", return_value=[mock_ingredient]):
            loot = await generate_loot(mock_session, mock_user)

    assert len(loot) == 1
    assert mock_inv_item.quantity == 3
    assert mock_user.credits == 10 + CREDITS_PER_WIN


@pytest.mark.asyncio
async def test_generate_loot_empty_ingredients() -> None:
    from unittest.mock import AsyncMock, MagicMock

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.credits = 0
    mock_user.experience = 0

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    from app.logic.loot import generate_loot

    loot = await generate_loot(mock_session, mock_user)

    assert loot == []
