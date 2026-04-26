from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.models.cart_upgrade import CartUpgrade
from app.models.suture_relic import SutureRelic
from app.models.user import User

router = APIRouter(prefix="/hub", tags=["hub"])

UPGRADE_COST_XP = 50
MAX_LEVEL = 5


async def _get_or_create_cart(session: AsyncSession, user_id: int) -> CartUpgrade:
    result = await session.execute(select(CartUpgrade).where(CartUpgrade.user_id == user_id))
    cart = result.scalar_one_or_none()
    if cart is None:
        cart = CartUpgrade(user_id=user_id)
        session.add(cart)
        await session.flush()
    return cart


class SutureRelicOut(BaseModel):
    id: int
    name: str
    description: str
    effect_tag: str
    currency: str
    price: int
    owned: bool = False


class HubStatusResponse(BaseModel):
    username: str | None
    experience: int
    credits: int
    slime: int
    cores: int
    debt: int
    debt_level: int
    kitchen_level: int
    fridge_level: int
    ads_level: int
    upgrade_cost: int
    suture_relics_owned: list[int]
    suture_catalog: list[SutureRelicOut]


class SutureBuyRequest(BaseModel):
    relic_id: int


class SutureBuyResponse(BaseModel):
    message: str
    slime: int
    cores: int
    suture_relics_owned: list[int]


@router.get("/status", response_model=HubStatusResponse)
async def hub_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> HubStatusResponse:
    cart = await _get_or_create_cart(session, user.id)
    relics_result = await session.execute(select(SutureRelic))
    all_relics = relics_result.scalars().all()

    owned: list[int] = user.suture_relics or []

    catalog = [
        SutureRelicOut(
            id=r.id,
            name=r.name,
            description=r.description,
            effect_tag=r.effect_tag,
            currency=r.currency,
            price=r.price,
            owned=r.id in owned,
        )
        for r in all_relics
    ]

    return HubStatusResponse(
        username=user.username,
        experience=user.experience,
        credits=user.credits,
        slime=user.slime,
        cores=user.cores,
        debt=user.debt,
        debt_level=user.debt_level,
        kitchen_level=cart.kitchen_level,
        fridge_level=cart.fridge_level,
        ads_level=cart.ads_level,
        upgrade_cost=UPGRADE_COST_XP,
        suture_relics_owned=owned,
        suture_catalog=catalog,
    )


@router.post("/suture/buy", response_model=SutureBuyResponse)
async def suture_buy(
    body: SutureBuyRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SutureBuyResponse:
    result = await session.execute(select(SutureRelic).where(SutureRelic.id == body.relic_id))
    relic = result.scalar_one_or_none()
    if relic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Реликвия не найдена")

    owned: list[int] = list(user.suture_relics or [])
    if relic.id in owned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Реликвия уже установлена")

    if relic.currency == "slime":
        if user.slime < relic.price:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Недостаточно слизи (нужно {relic.price}, есть {user.slime})",
            )
        user.slime -= relic.price
    elif relic.currency == "cores":
        if user.cores < relic.price:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Недостаточно ядер (нужно {relic.price}, есть {user.cores})",
            )
        user.cores -= relic.price
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестная валюта")

    owned.append(relic.id)
    user.suture_relics = owned

    await session.commit()

    return SutureBuyResponse(
        message=f"{relic.name} установлена",
        slime=user.slime,
        cores=user.cores,
        suture_relics_owned=owned,
    )
