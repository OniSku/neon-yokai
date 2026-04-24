from app.schemas.battle import Buff, CardInstance

DEBT_BUFF_NERF: float = 0.5
DEBT_CARD_COUNT: int = 2

DEBT_CARD = CardInstance(
    card_id=-1,
    name="Долговая расписка",
    cost=0,
    type="curse",
    power=0,
    damage_type="none",
    tags=["DEBT"],
    is_exhaust=False,
)

DEBT_LEVELS: dict[int, dict] = {
    0: {"name": "Чисто", "debuff": None},
    1: {"name": "Стыд", "debuff": "Баффы крафта ослаблены на 50%"},
    2: {"name": "Давление", "debuff": "Магазин заблокирован"},
    3: {"name": "Угрозы", "debuff": "2 проклятые карты в колоде"},
    4: {"name": "Коллекторы", "debuff": "Засада на первом узле карты"},
}

INGREDIENT_KIT_COST: int = 50
INGREDIENT_KIT_IDS: list[int] = [1, 2, 3, 4]


async def calculate_debt_level(debt: int) -> int:
    if debt >= 500:
        return 4
    if debt >= 300:
        return 3
    if debt >= 150:
        return 2
    if debt >= 50:
        return 1
    return 0


async def get_debt_level_info(level: int) -> dict:
    return DEBT_LEVELS.get(level, DEBT_LEVELS[0])


async def can_buy(debt_level: int) -> bool:
    return debt_level < 2


async def nerf_buffs(buffs: list[Buff], debt_level: int) -> list[Buff]:
    if debt_level < 1:
        return buffs

    nerfed: list[Buff] = []
    for b in buffs:
        copy = b.model_copy()
        copy.multiplier = 1.0 + (copy.multiplier - 1.0) * DEBT_BUFF_NERF
        copy.flat_bonus = int(copy.flat_bonus * DEBT_BUFF_NERF)
        nerfed.append(copy)
    return nerfed


async def generate_debt_cards(debt_level: int) -> list[CardInstance]:
    if debt_level < 3:
        return []
    return [DEBT_CARD.model_copy() for _ in range(DEBT_CARD_COUNT)]
