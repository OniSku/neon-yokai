from app.logic.debt import nerf_buffs
from app.models.ingredient import Ingredient
from app.schemas.battle import Buff, ComboEffect
from app.schemas.craft import CraftResult, FlavorProfile


FLAVOR_BUFF_MAP: dict[str, list[Buff]] = {
    "spicy": [
        Buff(tag="SPICY_BUFF", duration=3, multiplier=1.3, flat_bonus=3),
    ],
    "sour": [
        Buff(tag="SOUR_BUFF", duration=3, multiplier=1.0, flat_bonus=0),
    ],
    "sweet": [
        Buff(tag="SWEET_BUFF", duration=3, multiplier=1.0, flat_bonus=0),
    ],
    "bitter": [
        Buff(tag="BITTER_BUFF", duration=3, multiplier=1.15, flat_bonus=1),
    ],
    "salty": [
        Buff(tag="SALTY_BUFF", duration=3, multiplier=1.0, flat_bonus=0),
    ],
}

FLAVOR_DESCRIPTION: dict[str, str] = {
    "spicy": "Огненный вкус - усиливает атаку",
    "sour": "Кислый вкус - ослабляет врага",
    "sweet": "Сладкий вкус - восстанавливает HP",
    "bitter": "Горький вкус - усиливает защиту",
    "salty": "Соленый вкус - сохраняет блок",
}

SWEET_HEAL_AMOUNT: int = 8
SOUR_DEBUFF: Buff = Buff(tag="SOUR_DEBUFF", duration=2, multiplier=0.75, flat_bonus=0)

DOMINANCE_THRESHOLD: int = 5
COMBO_THRESHOLD: int = 4

COMBO_MAP: dict[str, ComboEffect] = {
    "spicy": ComboEffect(
        name="Поджог",
        flavor="spicy",
        description="Огненное комбо: +4 урона к атакам на 3 хода",
        buff=Buff(tag="COMBO_BURN", duration=3, multiplier=1.0, flat_bonus=4),
    ),
    "sour": ComboEffect(
        name="Уязвимость",
        flavor="sour",
        description="Кислотное комбо: враг получает +25% урона на 3 хода",
        buff=Buff(tag="COMBO_VULN", duration=3, multiplier=0.75, flat_bonus=0),
    ),
    "sweet": ComboEffect(
        name="Реген",
        flavor="sweet",
        description="Сладкое комбо: +5 HP в начале каждого хода (3 хода)",
        buff=Buff(tag="COMBO_REGEN", duration=3, multiplier=1.0, flat_bonus=5),
    ),
    "bitter": ComboEffect(
        name="Шипы",
        flavor="bitter",
        description="Горькое комбо: +3 блока в начале каждого хода (3 хода)",
        buff=Buff(tag="COMBO_THORNS", duration=3, multiplier=1.0, flat_bonus=3),
    ),
    "salty": ComboEffect(
        name="Соленая защита",
        flavor="salty",
        description="Соленое комбо: броня не сбрасывается в начале хода (3 хода)",
        buff=Buff(tag="SALTY_BUFF", duration=3, multiplier=1.0, flat_bonus=0),
    ),
}


FLAVOR_CAP_PER_INGREDIENT: int = 2  # - макс вклад одного ингредиента в каждый вкус


async def sum_ingredient_weights(
    ingredients: list[Ingredient],
) -> FlavorProfile:
    spicy = 0
    sour = 0
    sweet = 0
    bitter = 0
    salty = 0

    for ing in ingredients:
        # - Каждый ингредиент дает не больше FLAVOR_CAP_PER_INGREDIENT за каждый вкус
        cap = FLAVOR_CAP_PER_INGREDIENT
        spicy += min(ing.spicy, cap)
        sour += min(ing.sour, cap)
        sweet += min(ing.sweet, cap)
        bitter += min(ing.bitter, cap)
        salty += min(getattr(ing, "salty", 0), cap)

    return FlavorProfile(spicy=spicy, sour=sour, sweet=sweet, bitter=bitter, salty=salty)


async def resolve_dominant_flavor(profile: FlavorProfile) -> str | None:
    flavors = {
        "spicy": profile.spicy,
        "sour": profile.sour,
        "sweet": profile.sweet,
        "bitter": profile.bitter,
        "salty": getattr(profile, "salty", 0),
    }

    top_flavor = max(flavors, key=flavors.get)
    top_value = flavors[top_flavor]

    if top_value < DOMINANCE_THRESHOLD:
        return None

    return top_flavor


async def profile_to_buffs(
    profile: FlavorProfile,
    dominant: str | None,
) -> list[Buff]:
    buffs: list[Buff] = []

    if dominant and dominant in FLAVOR_BUFF_MAP:
        for template in FLAVOR_BUFF_MAP[dominant]:
            buffs.append(template.model_copy())

    return buffs


async def resolve_combo_effects(profile: FlavorProfile) -> list[ComboEffect]:
    effects: list[ComboEffect] = []
    flavors = {"spicy": profile.spicy, "sour": profile.sour, "sweet": profile.sweet, "bitter": profile.bitter, "salty": getattr(profile, "salty", 0)}
    for flavor, value in flavors.items():
        if value >= COMBO_THRESHOLD and flavor in COMBO_MAP:
            effects.append(COMBO_MAP[flavor].model_copy(deep=True))
    return effects


async def craft_dish(
    ingredients: list[Ingredient],
    debt_level: int = 0,
) -> CraftResult:
    profile = await sum_ingredient_weights(ingredients)
    dominant = await resolve_dominant_flavor(profile)
    buffs = await profile_to_buffs(profile, dominant)
    buffs = await nerf_buffs(buffs, debt_level)
    combos = await resolve_combo_effects(profile)

    # - Если хотя бы один ингредиент синтетический - добавить дебафф SYNTHETIC
    has_synthetic = any(getattr(ing, "is_synthetic", False) for ing in ingredients)
    synthetic_debuff: Buff | None = None
    if has_synthetic:
        synthetic_debuff = Buff(tag="SYNTHETIC_WEAK", duration=1, multiplier=0.75, flat_bonus=0)

    return CraftResult(
        profile=profile,
        buffs=[b.tag for b in buffs],
        dominant_flavor=dominant,
        combo_effects=[c.name for c in combos],
        synthetic_debuff=synthetic_debuff.tag if synthetic_debuff else None,
    )
