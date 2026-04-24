import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.logic.debt import can_buy, get_debt_level_info
from app.logic.loot import get_total_ingredient_count
from app.logic.meta import get_inventory_limit, get_shop_discount
from app.logic.economy import pay_debt as do_pay_debt, take_ingredient_kit
from app.models.inventory_item import InventoryItem
from app.models.shop_item import ShopItem
from app.models.user import User
from app.schemas.shop import (
    ShopBuyRequest,
    ShopBuyResponse,
    ShopItemOut,
    ShopPayRequest,
    ShopPayResponse,
    SupplierKitItem,
    SupplierKitResponse,
)

router = APIRouter(prefix="/shop", tags=["supplier"])


@router.get("/items", response_model=list[ShopItemOut])
async def list_items(
    session: AsyncSession = Depends(get_session),
) -> list[ShopItemOut]:
    result = await session.execute(select(ShopItem))
    items = result.scalars().all()
    return [
        ShopItemOut(
            id=i.id,
            name=i.name,
            description=i.description,
            price=i.price,
            category=i.category,
        )
        for i in items
    ]


@router.post("/buy", response_model=ShopBuyResponse)
async def buy_item(
    body: ShopBuyRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ShopBuyResponse:
    if not await can_buy(user.debt_level):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Shop blocked: debt level too high (level 2+)",
        )

    result = await session.execute(
        select(ShopItem).where(ShopItem.id == body.item_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    discount = get_shop_discount(user)
    final_price = max(1, int(item.price * (1.0 - discount)))

    if user.credits < final_price:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Not enough credits (need {final_price})",
        )

    user.credits -= final_price

    if item.category == "ingredient" and item.payload:
        payload = json.loads(item.payload)
        inv_limit = get_inventory_limit(user)
        current_count = await get_total_ingredient_count(session, user.id)
        for ing_id in payload.get("ingredient_ids", []):
            if current_count >= inv_limit:
                break
            result_inv = await session.execute(
                select(InventoryItem).where(
                    InventoryItem.user_id == user.id,
                    InventoryItem.ingredient_id == ing_id,
                )
            )
            inv = result_inv.scalar_one_or_none()
            if inv is None:
                inv = InventoryItem(user_id=user.id, ingredient_id=ing_id, quantity=1)
                session.add(inv)
            else:
                inv.quantity += 1
            current_count += 1

    await session.commit()
    await session.refresh(user)

    return ShopBuyResponse(
        message=f"Purchased {item.name}",
        credits=user.credits,
        item=ShopItemOut(
            id=item.id,
            name=item.name,
            description=item.description,
            price=item.price,
            category=item.category,
        ),
    )


@router.post("/debt", response_model=SupplierKitResponse)
async def take_kit(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SupplierKitResponse:
    inv_limit = get_inventory_limit(user)
    granted = await take_ingredient_kit(session, user, inventory_limit=inv_limit)
    info = await get_debt_level_info(user.debt_level)

    return SupplierKitResponse(
        message="Набор продуктов получен под реализацию",
        debt=user.debt,
        debt_level=user.debt_level,
        debt_level_name=info["name"],
        items=[SupplierKitItem(**g) for g in granted],
    )


@router.post("/pay", response_model=ShopPayResponse)
async def pay_debt_endpoint(
    body: ShopPayRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ShopPayResponse:
    if body.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Amount must be positive",
        )

    try:
        await do_pay_debt(session, user, body.amount)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e),
        )

    info = await get_debt_level_info(user.debt_level)

    return ShopPayResponse(
        message=f"Paid {body.amount} credits toward debt",
        credits=user.credits,
        debt=user.debt,
        debt_level=user.debt_level,
        debt_level_name=info["name"],
    )


@router.post("/remove-card")
async def remove_card(
    card_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.logic.persistence import load_run_state, save_run_state

    run = await load_run_state(session, user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="No active run")

    removal_cost = 50 + (25 * run.card_removals_this_run)

    if user.credits < removal_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Not enough credits (need {removal_cost})",
        )

    deck_result = await session.execute(
        select(UserDeckCard).where(
            UserDeckCard.user_id == user.id,
            UserDeckCard.card_id == card_id,
        )
    )
    deck_card = deck_result.scalar_one_or_none()
    if deck_card is None:
        raise HTTPException(status_code=404, detail="Card not in deck")

    if deck_card.quantity > 1:
        deck_card.quantity -= 1
    else:
        await session.delete(deck_card)

    user.credits -= removal_cost
    run.card_removals_this_run += 1

    if run.battle:
        for pile in [run.battle.hand, run.battle.draw_pile, run.battle.discard_pile, run.battle.exhaust_pile, run.battle.retained_cards]:
            for card in pile[:]:
                if card.card_id == card_id:
                    pile.remove(card)
                    break

    await session.commit()
    await save_run_state(session, run)

    return {
        "message": f"Карта удалена за {removal_cost} кредитов",
        "removal_cost": removal_cost,
        "credits": user.credits,
        "run": run,
    }
