from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.logic.debt import get_debt_level_info
from app.logic.meta import (
    MAX_UPGRADE_LEVEL,
    UPGRADE_BRANCHES,
    get_inventory_limit,
    get_upgrade_cost,
    parse_meta,
    try_upgrade,
)
from app.models.card import Card
from app.models.ingredient import Ingredient
from app.models.inventory_item import InventoryItem
from app.models.user import User
from app.models.user_deck_card import UserDeckCard
from app.schemas.requests import UpgradeRequest
from app.schemas.responses import (
    BranchInfo,
    DeckCardOut,
    InventoryItemOut,
    MetaProgress,
    UpgradeResponse,
    UserProfileResponse,
)

router = APIRouter(prefix="/user", tags=["user"])


def _build_meta(user: User) -> MetaProgress:
    meta = parse_meta(user)
    branches: dict[str, BranchInfo] = {}
    for key, info in UPGRADE_BRANCHES.items():
        lvl = meta[key]
        branches[key] = BranchInfo(
            name=info["name"],
            description=info["description"],
            level=lvl,
            max_level=MAX_UPGRADE_LEVEL,
            next_cost=get_upgrade_cost(lvl),
        )
    return MetaProgress(**branches)


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    user: User = Depends(get_current_user),
) -> UserProfileResponse:
    info = await get_debt_level_info(user.debt_level)
    return UserProfileResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        experience=user.experience,
        credits=user.credits,
        debt=user.debt,
        debt_level=user.debt_level,
        debt_level_name=info["name"],
        inventory_limit=get_inventory_limit(user),
        meta=_build_meta(user),
    )


@router.post("/upgrade", response_model=UpgradeResponse)
async def upgrade_branch(
    body: UpgradeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UpgradeResponse:
    success, msg = await try_upgrade(user, body.branch)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    await session.commit()
    await session.refresh(user)
    return UpgradeResponse(
        success=True,
        message=msg,
        experience=user.experience,
        meta=_build_meta(user),
    )


@router.get("/inventory", response_model=list[InventoryItemOut])
async def get_inventory(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[InventoryItemOut]:
    result = await session.execute(
        select(InventoryItem, Ingredient).join(
            Ingredient, InventoryItem.ingredient_id == Ingredient.id
        ).where(InventoryItem.user_id == user.id, InventoryItem.quantity > 0)
    )
    rows = result.all()
    return [
        InventoryItemOut(
            ingredient_id=inv.ingredient_id,
            ingredient_name=ing.name,
            quantity=inv.quantity,
        )
        for inv, ing in rows
    ]


@router.get("/deck", response_model=list[DeckCardOut])
async def get_deck(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DeckCardOut]:
    result = await session.execute(
        select(UserDeckCard, Card).join(
            Card, UserDeckCard.card_id == Card.id
        ).where(UserDeckCard.user_id == user.id)
    )
    rows = result.all()
    deck: list[DeckCardOut] = []
    for udc, card in rows:
        tags = [t.strip() for t in card.tags.split(",") if t.strip()] if card.tags else []
        deck.append(
            DeckCardOut(
                card_id=card.id,
                name=card.name,
                cost=card.cost,
                type=card.type,
                power=card.power,
                damage_type=card.damage_type,
                tags=tags,
                is_exhaust=card.is_exhaust,
                is_upgraded=udc.is_upgraded,
                quantity=udc.quantity,
            )
        )
    return deck
