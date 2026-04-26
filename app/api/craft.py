from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.logic.craft import craft_dish, resolve_combo_effects, sum_ingredient_weights
from app.logic.persistence import load_run_state, save_run_state
from app.models.ingredient import Ingredient
from app.models.inventory_item import InventoryItem
from app.models.user import User
from app.schemas.requests import CookRequest
from app.schemas.responses import CookResponse

router = APIRouter(prefix="/craft", tags=["craft"])


@router.post("/cook", response_model=CookResponse)
async def cook(
    body: CookRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CookResponse:
    needed: dict[int, int] = Counter(body.ingredient_ids)
    result = await session.execute(
        select(Ingredient).where(Ingredient.id.in_(needed.keys()))
    )
    ing_map = {i.id: i for i in result.scalars().all()}

    if len(ing_map) != len(needed):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more ingredients not found",
        )

    # - Строим список с повторами (2x перец чили = [перец, перец])
    ingredients = []
    for ing_id, qty in needed.items():
        ingredients.extend([ing_map[ing_id]] * qty)

    for ing_id, qty in needed.items():
        inv_result = await session.execute(
            select(InventoryItem).where(
                InventoryItem.user_id == user.id,
                InventoryItem.ingredient_id == ing_id,
            )
        )
        inv_item = inv_result.scalar_one_or_none()
        if inv_item is None or inv_item.quantity < qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not enough ingredient id={ing_id} in inventory",
            )

    for ing_id, qty in needed.items():
        inv_result = await session.execute(
            select(InventoryItem).where(
                InventoryItem.user_id == user.id,
                InventoryItem.ingredient_id == ing_id,
            )
        )
        inv_item = inv_result.scalar_one_or_none()
        inv_item.quantity -= qty

    craft_result = await craft_dish(ingredients, debt_level=user.debt_level)

    run = await load_run_state(session, user.id)
    if run and not run.run_finished:
        if craft_result.void_result:
            # - Безвкусная биомасса: сбрасываем баффы, не даём новых
            run.combo_effects = []
        else:
            profile = await sum_ingredient_weights(ingredients)
            combos = await resolve_combo_effects(profile)
            run.combo_effects = combos
        await save_run_state(session, run)

    await session.commit()

    return CookResponse(result=craft_result)
