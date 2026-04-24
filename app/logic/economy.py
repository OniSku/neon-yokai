import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logic.debt import INGREDIENT_KIT_COST, INGREDIENT_KIT_IDS, calculate_debt_level
from app.models.inventory_item import InventoryItem
from app.models.user import User


async def _get_inv_count(session: AsyncSession, user_id: int) -> int:
    from sqlalchemy import func as sa_func
    result = await session.execute(
        select(sa_func.coalesce(sa_func.sum(InventoryItem.quantity), 0)).where(
            InventoryItem.user_id == user_id,
            InventoryItem.quantity > 0,
        )
    )
    return int(result.scalar())

INTEREST_RATE: float = 0.15


async def apply_interest(session: AsyncSession, user: User) -> int:
    if user.debt <= 0:
        return 0

    interest = math.ceil(user.debt * INTEREST_RATE)
    user.debt += interest
    user.debt_level = await calculate_debt_level(user.debt)

    await session.commit()
    await session.refresh(user)
    return interest


async def take_ingredient_kit(
    session: AsyncSession,
    user: User,
    inventory_limit: int = 5,
) -> list[dict]:
    user.debt += INGREDIENT_KIT_COST
    user.debt_level = await calculate_debt_level(user.debt)

    granted: list[dict] = []
    current_count = await _get_inv_count(session, user.id)

    for ing_id in INGREDIENT_KIT_IDS:
        if current_count >= inventory_limit:
            break

        result = await session.execute(
            select(InventoryItem).where(
                InventoryItem.user_id == user.id,
                InventoryItem.ingredient_id == ing_id,
            )
        )
        inv = result.scalar_one_or_none()

        if inv is None:
            inv = InventoryItem(
                user_id=user.id,
                ingredient_id=ing_id,
                quantity=1,
            )
            session.add(inv)
        else:
            inv.quantity += 1

        current_count += 1
        granted.append({"ingredient_id": ing_id, "quantity": 1})

    await session.commit()
    await session.refresh(user)
    return granted


async def pay_debt(session: AsyncSession, user: User, amount: int) -> None:
    if amount > user.credits:
        raise ValueError("Not enough credits")

    pay = min(amount, user.debt)
    user.credits -= pay
    user.debt -= pay
    user.debt_level = await calculate_debt_level(user.debt)

    await session.commit()
    await session.refresh(user)
