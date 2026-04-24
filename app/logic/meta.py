from __future__ import annotations

import json

from app.models.user import User


MAX_UPGRADE_LEVEL: int = 5

UPGRADE_BRANCHES: dict[str, dict] = {
    "kitchen": {
        "name": "Кухня",
        "description": "+5 к макс. HP за уровень",
        "bonus_per_level": 5,
        "bonus_type": "max_hp",
    },
    "fridge": {
        "name": "Холодильник",
        "description": "+1 слот ингредиента за уровень",
        "bonus_per_level": 1,
        "bonus_type": "ingredient_slot",
    },
    "ads": {
        "name": "Реклама",
        "description": "-5% цены в магазине за уровень",
        "bonus_per_level": 0.05,
        "bonus_type": "shop_discount",
    },
}

XP_COST_PER_LEVEL: list[int] = [50, 100, 200, 350, 500]


def parse_meta(user: User) -> dict[str, int]:
    if not user.meta_progress:
        return {"kitchen": 0, "fridge": 0, "ads": 0}
    try:
        data = json.loads(user.meta_progress)
        return {
            "kitchen": data.get("kitchen", 0),
            "fridge": data.get("fridge", 0),
            "ads": data.get("ads", 0),
        }
    except (json.JSONDecodeError, TypeError):
        return {"kitchen": 0, "fridge": 0, "ads": 0}


def save_meta(user: User, meta: dict[str, int]) -> None:
    user.meta_progress = json.dumps(meta)


def get_upgrade_cost(current_level: int) -> int | None:
    if current_level >= MAX_UPGRADE_LEVEL:
        return None
    return XP_COST_PER_LEVEL[current_level]


async def try_upgrade(user: User, branch: str) -> tuple[bool, str]:
    if branch not in UPGRADE_BRANCHES:
        return False, f"Неизвестная ветка: {branch}"

    meta = parse_meta(user)
    current_level = meta[branch]

    cost = get_upgrade_cost(current_level)
    if cost is None:
        return False, f"{UPGRADE_BRANCHES[branch]['name']} уже на макс. уровне ({MAX_UPGRADE_LEVEL})"

    if user.experience < cost:
        return False, f"Недостаточно опыта (нужно {cost}, есть {user.experience})"

    user.experience -= cost
    meta[branch] = current_level + 1
    save_meta(user, meta)

    info = UPGRADE_BRANCHES[branch]
    return True, f"{info['name']} улучшена до уровня {meta[branch]}!"


def get_max_hp_bonus(user: User) -> int:
    meta = parse_meta(user)
    kitchen_bonus = meta["kitchen"] * UPGRADE_BRANCHES["kitchen"]["bonus_per_level"]
    implant_bonus = meta.get("implant_hp", 0)
    return kitchen_bonus + implant_bonus


BASE_INVENTORY_LIMIT: int = 5


def get_ingredient_slot_bonus(user: User) -> int:
    meta = parse_meta(user)
    return meta["fridge"] * UPGRADE_BRANCHES["fridge"]["bonus_per_level"]


def get_inventory_limit(user: User) -> int:
    return BASE_INVENTORY_LIMIT + get_ingredient_slot_bonus(user)


def get_shop_discount(user: User) -> float:
    meta = parse_meta(user)
    return meta["ads"] * UPGRADE_BRANCHES["ads"]["bonus_per_level"]
