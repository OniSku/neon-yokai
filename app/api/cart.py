"""API для мета-прогрессии тележки (Хаб).

Отделено от /run/rest - это постоянные улучшения за XP.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.models.cart_upgrade import CartUpgrade
from app.models.user import User

router = APIRouter(prefix="/hub/cart", tags=["cart"])

UPGRADE_COST_XP = 50
MAX_LEVEL = 5


class CartStatusResponse(BaseModel):
    kitchen_level: int
    fridge_level: int
    ads_level: int
    user_experience: int
    can_upgrade_kitchen: bool
    can_upgrade_fridge: bool
    can_upgrade_ads: bool
    upgrade_cost: int


class CartUpgradeRequest(BaseModel):
    branch: str  # "kitchen" | "fridge" | "ads"


class CartUpgradeResponse(BaseModel):
    success: bool
    branch: str
    new_level: int
    remaining_xp: int
    message: str


async def _get_or_create_cart_upgrade(
    session: AsyncSession, user_id: int
) -> CartUpgrade:
    result = await session.execute(
        select(CartUpgrade).where(CartUpgrade.user_id == user_id)
    )
    cart = result.scalar_one_or_none()
    if cart is None:
        cart = CartUpgrade(user_id=user_id)
        session.add(cart)
        await session.flush()
    return cart


@router.get("/status", response_model=CartStatusResponse)
async def get_cart_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CartStatusResponse:
    """Получить текущий статус улучшений тележки."""
    cart = await _get_or_create_cart_upgrade(session, user.id)

    return CartStatusResponse(
        kitchen_level=cart.kitchen_level,
        fridge_level=cart.fridge_level,
        ads_level=cart.ads_level,
        user_experience=user.experience,
        can_upgrade_kitchen=cart.kitchen_level < MAX_LEVEL
        and user.experience >= UPGRADE_COST_XP,
        can_upgrade_fridge=cart.fridge_level < MAX_LEVEL
        and user.experience >= UPGRADE_COST_XP,
        can_upgrade_ads=cart.ads_level < MAX_LEVEL
        and user.experience >= UPGRADE_COST_XP,
        upgrade_cost=UPGRADE_COST_XP,
    )


@router.post("/upgrade", response_model=CartUpgradeResponse)
async def upgrade_cart(
    body: CartUpgradeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CartUpgradeResponse:
    """Улучшить ветку тележки (kitchen, fridge, ads)."""
    if body.branch not in ("kitchen", "fridge", "ads"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid branch: {body.branch}. Must be kitchen, fridge, or ads",
        )

    cart = await _get_or_create_cart_upgrade(session, user.id)

    # Проверяем максимальный уровень
    current_level = getattr(cart, f"{body.branch}_level")
    if current_level >= MAX_LEVEL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{body.branch} already at max level ({MAX_LEVEL})",
        )

    # Проверяем достаточно ли XP
    if user.experience < UPGRADE_COST_XP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not enough XP. Required: {UPGRADE_COST_XP}, have: {user.experience}",
        )

    # Списываем XP и повышаем уровень
    user.experience -= UPGRADE_COST_XP
    setattr(cart, f"{body.branch}_level", current_level + 1)

    await session.commit()

    # Формируем сообщение
    messages = {
        "kitchen": f"Кухня улучшена! +5 макс HP (уровень {current_level + 1}/5)",
        "fridge": f"Холодильник улучшен! +1 слот ингредиента (уровень {current_level + 1}/5)",
        "ads": f"Реклама улучшена! -5% цены в магазине (уровень {current_level + 1}/5)",
    }

    return CartUpgradeResponse(
        success=True,
        branch=body.branch,
        new_level=current_level + 1,
        remaining_xp=user.experience,
        message=messages[body.branch],
    )
