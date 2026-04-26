import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import Artifact
from app.models.card import Card
from app.models.ingredient import Ingredient
from app.models.inventory_item import InventoryItem
from app.models.user import User
from app.models.user_deck_card import UserDeckCard
from app.schemas.battle import ArtifactInstance, PendingRewards, RewardCard

LOOT_MIN: int = 1
LOOT_MAX: int = 2
INGREDIENT_DROP_CHANCE: float = 0.22  # - 22% шанс дропа ингредиента с врага


async def get_total_ingredient_count(
    session: AsyncSession,
    user_id: int,
) -> int:
    result = await session.execute(
        select(func.coalesce(func.sum(InventoryItem.quantity), 0)).where(
            InventoryItem.user_id == user_id,
            InventoryItem.quantity > 0,
        )
    )
    return int(result.scalar())


CREDITS_PER_WIN: int = 15
XP_PER_WIN: int = 10
REWARD_CARD_CHOICES: int = 3

RARITY_WEIGHTS_NORMAL: dict[str, float] = {"common": 0.75, "rare": 0.25}
LEGENDARY_UPGRADE_CHANCE: float = 0.05
ARTIFACT_DROP_CHANCE: float = 0.30


def _card_to_reward(c: Card) -> RewardCard:
    tags = [t.strip() for t in c.tags.split(",") if t.strip()] if c.tags else []
    return RewardCard(
        card_id=c.id,
        name=c.name,
        cost=c.cost,
        type=c.type,
        power=c.power,
        damage_type=c.damage_type,
        tags=tags,
        is_exhaust=c.is_exhaust,
        rarity=c.rarity,
    )


async def _roll_ingredient_loot(
    session: AsyncSession,
    enemy_count: int = 1,
    force: bool = False,
) -> list[dict]:
    # - Шанс дропа: 22% за врага. Элита/босс - всегда дропают.
    drop_count = 0
    for _ in range(enemy_count):
        if force or random.random() < INGREDIENT_DROP_CHANCE:
            drop_count += 1
    if drop_count == 0:
        return []
    result = await session.execute(select(Ingredient))
    all_ingredients = list(result.scalars().all())
    if not all_ingredients:
        return []
    qty = random.randint(LOOT_MIN, LOOT_MAX) if drop_count == 1 else random.randint(LOOT_MIN, LOOT_MAX + 1)
    chosen = random.choices(all_ingredients, k=qty)
    return [
        {
            "ingredient_id": ing.id,
            "ingredient_name": ing.name,
            "name": ing.name,
            "quantity": 1,
            "flavor_profile": {
                "spicy": ing.spicy, "sour": ing.sour,
                "sweet": ing.sweet, "bitter": ing.bitter, "salty": ing.salty,
            },
        }
        for ing in chosen
    ]


async def _roll_reward_cards(
    session: AsyncSession,
    node_type: str = "combat",
) -> list[RewardCard]:
    result = await session.execute(select(Card))
    all_cards = list(result.scalars().all())
    if not all_cards:
        return []

    # Фильтрация: убираем проклятия и стартовые карты
    reward_cards = [
        c for c in all_cards
        if c.type != "curse" and not c.is_starting
    ]
    if not reward_cards:
        return []

    by_rarity: dict[str, list[Card]] = {}
    for c in reward_cards:
        by_rarity.setdefault(c.rarity, []).append(c)

    # Шанс легендарки: 1-2% (обычный бой), гарантированно с босса
    legendary_chance = 0.02 if node_type == "combat" else 0.01

    if node_type == "boss":
        pool = by_rarity.get("legendary", [])
        if not pool:
            pool = by_rarity.get("rare", reward_cards)
        chosen = random.sample(pool, k=min(REWARD_CARD_CHOICES, len(pool)))
        return [_card_to_reward(c) for c in chosen]

    cards: list[RewardCard] = []
    common_pool = by_rarity.get("common", [])
    rare_pool = by_rarity.get("rare", [])
    legendary_pool = by_rarity.get("legendary", [])

    for _ in range(REWARD_CARD_CHOICES):
        if legendary_pool and random.random() < legendary_chance:
            c = random.choice(legendary_pool)
        elif rare_pool and random.random() < RARITY_WEIGHTS_NORMAL["rare"]:
            c = random.choice(rare_pool)
        elif common_pool:
            c = random.choice(common_pool)
        else:
            c = random.choice(reward_cards)
        cards.append(_card_to_reward(c))

    seen_ids: set[int] = set()
    unique: list[RewardCard] = []
    for rc in cards:
        if rc.card_id not in seen_ids:
            seen_ids.add(rc.card_id)
            unique.append(rc)
    return unique if unique else cards[:1]


def _artifact_to_instance(a: Artifact) -> ArtifactInstance:
    return ArtifactInstance(
        artifact_id=a.id,
        name=a.name,
        rarity=a.rarity,
        description=a.description,
        trigger=a.trigger,
        charges=a.charges,
        is_active=a.is_active,
    )


async def _roll_artifact_reward(
    session: AsyncSession,
    node_type: str = "combat",
) -> ArtifactInstance | None:
    if node_type in ("boss", "elite"):
        guaranteed = True
    elif random.random() > ARTIFACT_DROP_CHANCE:
        return None
    else:
        guaranteed = False

    result = await session.execute(select(Artifact).where(Artifact.is_active == True))
    pool = list(result.scalars().all())
    if not pool:
        return None
    if node_type == "boss":
        leg_pool = [a for a in pool if a.rarity == "legendary"]
        if leg_pool:
            pool = leg_pool
    elif node_type == "elite":
        rare_pool = [a for a in pool if a.rarity in ("rare", "legendary")]
        if rare_pool:
            pool = rare_pool
    return _artifact_to_instance(random.choice(pool))


CREDITS_BY_TYPE: dict[str, int] = {
    "combat": 15,
    "elite": 30,
    "boss": 50,
}
XP_BY_TYPE: dict[str, int] = {
    "combat": 10,
    "elite": 25,
    "boss": 40,
}


async def generate_pending_rewards(
    session: AsyncSession,
    node_type: str = "combat",
    enemy_count: int = 1,
) -> PendingRewards:
    # - Элита и босс гарантированно дропают ингредиенты
    force_drop = node_type in ("elite", "boss")
    loot = await _roll_ingredient_loot(session, enemy_count=enemy_count, force=force_drop)
    card_choices = await _roll_reward_cards(session, node_type=node_type)
    if node_type in ("elite", "boss"):
        artifact = await _roll_artifact_reward(session, node_type=node_type)
    else:
        artifact = None
    cr = CREDITS_BY_TYPE.get(node_type, CREDITS_PER_WIN)
    xp = XP_BY_TYPE.get(node_type, XP_PER_WIN)
    return PendingRewards(
        credits=cr,
        experience=xp,
        loot=loot,
        card_choices=card_choices,
        artifact_reward=artifact,
    )


async def claim_rewards(
    session: AsyncSession,
    user: User,
    rewards: PendingRewards,
    chosen_card_id: int | None = None,
    inventory_limit: int = 5,
    run: "any | None" = None,  # - если передан - лут идёт в run_ingredients, а не в хаб-инвентарь
) -> None:
    user.credits += rewards.credits
    user.experience += rewards.experience

    if run is not None:
        # - Лут идёт в run_ingredients (доступен для готовки на привале)
        if not hasattr(run, "run_ingredients") or run.run_ingredients is None:
            run.run_ingredients = []
        for item in rewards.loot:
            ing_id = item["ingredient_id"]
            existing = next((r for r in run.run_ingredients if r.get("ingredient_id") == ing_id), None)
            if existing:
                existing["quantity"] = existing.get("quantity", 0) + 1
            else:
                run.run_ingredients.append({
                    "ingredient_id": ing_id,
                    "ingredient_name": item.get("ingredient_name") or item.get("name", str(ing_id)),
                    "quantity": 1,
                    "flavor_profile": item.get("flavor_profile"),
                })
    else:
        # - Лут идёт в хаб-инвентарь (старое поведение)
        current_count = await get_total_ingredient_count(session, user.id)
        for item in rewards.loot:
            if current_count >= inventory_limit:
                break
            ing_id = item["ingredient_id"]
            inv_result = await session.execute(
                select(InventoryItem).where(
                    InventoryItem.user_id == user.id,
                    InventoryItem.ingredient_id == ing_id,
                )
            )
            inv_item = inv_result.scalar_one_or_none()
            if inv_item is None:
                inv_item = InventoryItem(user_id=user.id, ingredient_id=ing_id, quantity=1)
                session.add(inv_item)
            else:
                inv_item.quantity += 1
            current_count += 1

    if chosen_card_id is not None:
        valid = any(c.card_id == chosen_card_id for c in rewards.card_choices)
        if valid:
            deck_result = await session.execute(
                select(UserDeckCard).where(
                    UserDeckCard.user_id == user.id,
                    UserDeckCard.card_id == chosen_card_id,
                )
            )
            existing = deck_result.scalar_one_or_none()
            if existing is None:
                session.add(UserDeckCard(user_id=user.id, card_id=chosen_card_id, quantity=1))
            else:
                existing.quantity += 1

    await session.commit()
    await session.refresh(user)
