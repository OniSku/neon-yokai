from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import Artifact
from app.models.card import Card
from app.schemas.battle import (
    ArtifactInstance,
    EventChoice,
    EventScenario,
    RewardCard,
    RunState,
)


SCENARIOS: list[dict] = [
    {
        "event_id": "broken_vending",
        "title": "Сломанный автомат",
        "description": "Неоновый автомат с напитками мерцает и искрит. Кажется, внутри что-то застряло.",
        "choices": [
            {
                "choice_id": "hit",
                "label": "Ударить",
                "description": "-5 HP, 50% шанс на Common артефакт",
                "cost_type": "hp",
                "cost_value": 5,
            },
            {
                "choice_id": "pry",
                "label": "Вскрыть",
                "description": "Нужна карта с cost 0 в колоде - +30 кредитов",
                "cost_type": "none",
                "cost_value": 0,
            },
            {
                "choice_id": "ignore",
                "label": "Игнорировать",
                "description": "Уйти без последствий",
                "cost_type": "none",
                "cost_value": 0,
            },
        ],
    },
    {
        "event_id": "collectors",
        "title": "Коллекторы",
        "description": "Трое мрачных типов в костюмах заступают вам путь. 'Ты должен. Плати.'",
        "choices": [
            {
                "choice_id": "pay",
                "label": "Откупиться",
                "description": "-40 кредитов",
                "cost_type": "credits",
                "cost_value": 40,
            },
            {
                "choice_id": "give_item",
                "label": "Отдать товар",
                "description": "-1 редкий ингредиент из инвентаря",
                "cost_type": "none",
                "cost_value": 0,
            },
            {
                "choice_id": "fight",
                "label": "Драка",
                "description": "Начать бой с Элитой",
                "cost_type": "none",
                "cost_value": 0,
            },
        ],
    },
    {
        "event_id": "ripperdoc",
        "title": "Сломанный мед-дрон",
        "description": "Вы находите дрон корпорации. Он искрит, но медицинские системы еще работают.",
        "choices": [
            {
                "choice_id": "heal",
                "label": "Лечение",
                "description": "Восстановить 50% HP за 25 кредитов",
                "cost_type": "credits",
                "cost_value": 25,
            },
            {
                "choice_id": "implant",
                "label": "Имплант",
                "description": "+10 Max HP, но -15 текущего HP",
                "cost_type": "none",
                "cost_value": 0,
            },
            {
                "choice_id": "ignore",
                "label": "Уйти",
                "description": "Уйти без последствий",
                "cost_type": "none",
                "cost_value": 0,
            },
        ],
    },
    {
        "event_id": "informant",
        "title": "Встреча с уличным информатором",
        "description": "Темная фигура манит вас из переулка. Предлагает ценную информацию... за определенную цену.",
        "choices": [
            {
                "choice_id": "risk",
                "label": "Рискнуть",
                "description": "Потерять 15 HP, но получить редкую карту",
                "cost_type": "hp",
                "cost_value": 15,
            },
            {
                "choice_id": "pay",
                "label": "Заплатить",
                "description": "Отдать 25 кредитов за артефакт",
                "cost_type": "credits",
                "cost_value": 25,
            },
            {
                "choice_id": "ignore",
                "label": "Уйти",
                "description": "Уйти без последствий",
                "cost_type": "none",
                "cost_value": 0,
            },
        ],
    },
    {
        "event_id": "stray_cat",
        "title": "Бродячий кот екай",
        "description": "Светящийся кот преграждает вам дорогу. Он смотрит на вас выжидающе, будто чего-то хочет.",
        "choices": [
            {
                "choice_id": "risk",
                "label": "Погладить",
                "description": "50/50: получить артефакт или потерять 15 HP",
                "cost_type": "hp",
                "cost_value": 0,
            },
            {
                "choice_id": "pay",
                "label": "Покормить",
                "description": "Отдать 10 кредитов, получить артефакт",
                "cost_type": "credits",
                "cost_value": 10,
            },
            {
                "choice_id": "ignore",
                "label": "Обойти",
                "description": "Уйти без последствий",
                "cost_type": "none",
                "cost_value": 0,
            },
        ],
    },
]

ULTRA_RARE_SCENARIO: dict = {
    "event_id": "synth_trip",
    "title": "Синтетический приход",
    "description": "Мир плывет. Голоса шепчут. Назад дороги нет.",
    "choices": [
        {
            "choice_id": "fear",
            "label": "Вспомнить страх",
            "description": "Немедленный бой с Боссом. Награда: Legendary артефакт",
            "cost_type": "none",
            "cost_value": 0,
        },
        {
            "choice_id": "chaos",
            "label": "Хаос",
            "description": "Удалить все attack/defend карты, заменить случайными",
            "cost_type": "none",
            "cost_value": 0,
        },
        {
            "choice_id": "debt",
            "label": "Абсолютный долг",
            "description": "+999 кредитов, но +3 проклятия 'Мертвый груз' в колоду",
            "cost_type": "none",
            "cost_value": 0,
        },
    ],
}

ULTRA_RARE_CHANCE: float = 0.05
ULTRA_RARE_FLOORS: set[int] = {6, 7}


SCENARIOS.extend([
    {
        "event_id": "supply_cache",
        "title": "Склад концентратов",
        "description": "За раздвижной плитой - запасный склад. Химикаты в ряд. Но нести много.",
        "choices": [
            {
                "choice_id": "take_credits",
                "label": "Взять кредиты",
                "description": "+30 кредитов",
                "cost_type": "none",
                "cost_value": 0,
            },
            {
                "choice_id": "remove_card",
                "label": "Удалить слабую карту",
                "description": "Удалить случайную карту из колоды (бесплатно)",
                "cost_type": "none",
                "cost_value": 0,
            },
        ],
    },
    {
        "event_id": "forgotten_recipe",
        "title": "Забытый рецепт",
        "description": "Старый чип в стене мерцает. На нем - техника которую вы забыли. Флэшбэк болезнен.",
        "choices": [
            {
                "choice_id": "download",
                "label": "Скачать рецепт",
                "description": "-10 HP, получить случайную Rare карту",
                "cost_type": "hp",
                "cost_value": 10,
            },
            {
                "choice_id": "ignore",
                "label": "Пройти мимо",
                "description": "Уйти без последствий",
                "cost_type": "none",
                "cost_value": 0,
            },
        ],
    },
    {
        "event_id": "street_altar",
        "title": "Уличный алтарь",
        "description": "В нише - алтарь из обломков и неоновых лент Екайа. Он призывает. Повар чувствует узнаваемое.",
        "choices": [
            {
                "choice_id": "pray",
                "label": "Помолиться",
                "description": "-30% текущих кредитов, полное восстановление HP",
                "cost_type": "none",
                "cost_value": 0,
            },
            {
                "choice_id": "ignore",
                "label": "Пройти мимо",
                "description": "Уйти без последствий",
                "cost_type": "none",
                "cost_value": 0,
            },
        ],
    },
    # === ШАГ 52: Новые ивенты ===
    {
        "event_id": "elite_patrol",
        "title": "Патруль Элиты",
        "description": "Трое бойцов якудзы перекрывают дорогу. Можно откупиться, а можно - рискнуть и украсть Ядра.",
        "choices": [
            {
                "choice_id": "bribe",
                "label": "Откупиться",
                "description": "-50 кредитов. Патруль пропускает.",
                "cost_type": "credits",
                "cost_value": 50,
            },
            {
                "choice_id": "steal",
                "label": "Рискнуть (50/50)",
                "description": "Удача: +40 кредитов. Провал: элитный бой.",
                "cost_type": "none",
                "cost_value": 0,
            },
        ],
    },
    {
        "event_id": "broken_vend",
        "title": "Сломанный торговый автомат",
        "description": "Автомат мигает неоном и гудит. Внутри - ингредиенты по ценам вчерашнего дня.",
        "choices": [
            {
                "choice_id": "smash",
                "label": "Ударить",
                "description": "50%% - случайный ингредиент. 50%% - -8 HP от разряда.",
                "cost_type": "none",
                "cost_value": 0,
            },
            {
                "choice_id": "hack",
                "label": "Взломать (-20 кр)",
                "description": "Гарантированно даёт ингредиент.",
                "cost_type": "credits",
                "cost_value": 20,
            },
            {
                "choice_id": "ignore",
                "label": "Пройти мимо",
                "description": "Уйти без последствий.",
                "cost_type": "none",
                "cost_value": 0,
            },
        ],
    },
])


def pick_random_event(floor: int = 0, seen_event_ids: list[str] | None = None) -> EventScenario:
    if floor in ULTRA_RARE_FLOORS and random.random() < ULTRA_RARE_CHANCE:
        data = ULTRA_RARE_SCENARIO
    else:
        seen = seen_event_ids or []
        available = [s for s in SCENARIOS if s["event_id"] not in seen]
        # - Если все ивенты уже просмотрены, сбрасываем список
        if not available:
            available = SCENARIOS
        data = random.choice(available)
    choices = [EventChoice(**c) for c in data["choices"]]
    return EventScenario(
        event_id=data["event_id"],
        title=data["title"],
        description=data["description"],
        choices=choices,
    )


async def _random_rare_card(session: AsyncSession) -> RewardCard | None:
    result = await session.execute(
        select(Card).where(Card.rarity.in_(["rare", "legendary"]))
    )
    pool = list(result.scalars().all())
    if not pool:
        return None
    c = random.choice(pool)
    tags = [t.strip() for t in c.tags.split(",") if t.strip()] if c.tags else []
    return RewardCard(
        card_id=c.id, name=c.name, cost=c.cost, type=c.type,
        power=c.power, damage_type=c.damage_type, tags=tags,
        is_exhaust=c.is_exhaust, rarity=c.rarity,
    )


async def _random_common_artifact(session: AsyncSession) -> ArtifactInstance | None:
    result = await session.execute(
        select(Artifact).where(Artifact.is_active == True, Artifact.rarity == "common")
    )
    pool = list(result.scalars().all())
    if not pool:
        return None
    a = random.choice(pool)
    return ArtifactInstance(
        artifact_id=a.id, name=a.name, rarity=a.rarity,
        description=a.description, trigger=a.trigger,
        charges=a.charges, is_active=a.is_active,
    )


async def _random_artifact(
    session: AsyncSession,
    rarity: str | None = None,
) -> ArtifactInstance | None:
    q = select(Artifact).where(Artifact.is_active == True)
    if rarity:
        q = q.where(Artifact.rarity == rarity)
    result = await session.execute(q)
    pool = list(result.scalars().all())
    if not pool:
        return None
    a = random.choice(pool)
    return ArtifactInstance(
        artifact_id=a.id, name=a.name, rarity=a.rarity,
        description=a.description, trigger=a.trigger,
        charges=a.charges, is_active=a.is_active,
    )


async def resolve_event_choice(
    session: AsyncSession,
    run: RunState,
    choice_id: str,
    user_credits: int,
    max_hp: int = 80,
) -> tuple[str, int, int, RewardCard | None, ArtifactInstance | None]:
    event = run.active_event
    if event is None:
        raise ValueError("No active event")

    choice = next((c for c in event.choices if c.choice_id == choice_id), None)
    if choice is None:
        raise ValueError(f"Invalid choice: {choice_id}")

    msg = ""
    hp_delta = 0
    credits_delta = 0
    card_reward: RewardCard | None = None
    artifact_reward: ArtifactInstance | None = None

    eid = event.event_id

    # ---- Сломанный автомат ----
    if eid == "broken_vending":
        if choice_id == "hit":
            hp_delta = -5
            if random.random() < 0.5:
                artifact_reward = await _random_common_artifact(session)
                msg = "Вы ударили автомат! Выпал артефакт! -5 HP"
            else:
                msg = "Автомат загудел, но ничего не выпало. -5 HP"
        elif choice_id == "pry":
            # Проверяем наличие карты с cost=0 в колоде забега
            from app.models.user_deck_card import UserDeckCard
            udc_res = await session.execute(
                select(UserDeckCard).where(UserDeckCard.user_id == run.user_id)
            )
            all_udc = list(udc_res.scalars().all())
            has_zero_cost = False
            for udc in all_udc:
                card_res = await session.execute(select(Card).where(Card.id == udc.card_id))
                c = card_res.scalar_one_or_none()
                if c and c.cost == 0:
                    has_zero_cost = True
                    break
            if has_zero_cost:
                credits_delta = 30
                msg = "Быстрый удар изолентой картой! Автомат сломался. +30 кредитов"
            else:
                msg = "Нет нужной карты. Автомат не поддался."
        elif choice_id == "ignore":
            msg = "Вы прошли мимо."

    # ---- Коллекторы ----
    elif eid == "collectors":
        if choice_id == "pay":
            if user_credits < 40:
                raise ValueError("Not enough credits")
            credits_delta = -40
            msg = "Заплатили 40 кредитов. Коллекторы отступили."
        elif choice_id == "give_item":
            from app.models.inventory_item import InventoryItem
            inv_result = await session.execute(
                select(InventoryItem).where(
                    InventoryItem.user_id == run.user_id,
                    InventoryItem.quantity > 0,
                )
            )
            inv_items = list(inv_result.scalars().all())
            if not inv_items:
                raise ValueError("No ingredients to give")
            target_item = random.choice(inv_items)
            target_item.quantity -= 1
            if target_item.quantity <= 0:
                await session.delete(target_item)
            msg = "Вы отдали редкий ингредиент. Коллекторы довольны."
        elif choice_id == "fight":
            msg = "FIGHT_ELITE"

    # ---- Сломанный мед-дрон ----
    elif eid == "ripperdoc":
        if choice_id == "heal":
            if user_credits < 25:
                raise ValueError("Not enough credits")
            credits_delta = -25
            heal_amount = max_hp // 2
            hp_delta = heal_amount
            msg = f"Дрон залатал вас. +{heal_amount} HP, -25 кредитов"
        elif choice_id == "implant":
            hp_delta = -15
            msg = "IMPLANT_MAX_HP_10"
        elif choice_id == "ignore":
            msg = "Вы ушли."

    # ---- Синтетический приход (ultra-rare) ----
    elif eid == "synth_trip":
        if choice_id == "fear":
            msg = "FIGHT_BOSS_LEGENDARY"
        elif choice_id == "chaos":
            msg = "CHAOS_REPLACE_DECK"
        elif choice_id == "debt":
            credits_delta = 999
            msg = "ABSOLUTE_DEBT"

    # ---- Информатор (legacy) ----
    elif eid == "informant":
        if choice_id == "ignore":
            msg = "Вы ушли без последствий."
        elif choice_id == "risk":
            hp_delta = -15
            card_reward = await _random_rare_card(session)
            msg = "Вы потеряли 15 HP, но получили карту!"
        elif choice_id == "pay":
            if user_credits < 25:
                raise ValueError("Not enough credits")
            credits_delta = -25
            artifact_reward = await _random_artifact(session)
            msg = "Заплатили 25 кр. Информатор передал артефакт."

    # ---- Бродячий кот (legacy) ----
    elif eid == "stray_cat":
        if choice_id == "ignore":
            msg = "Вы обошли кота."
        elif choice_id == "risk":
            if random.random() < 0.5:
                artifact_reward = await _random_artifact(session)
                msg = "Кот мурлычет! Он оставил вам подарок."
            else:
                hp_delta = -15
                msg = "Кот оказался злым! Вы потеряли 15 HP."
        elif choice_id == "pay":
            if user_credits < 10:
                raise ValueError("Not enough credits")
            credits_delta = -10
            artifact_reward = await _random_artifact(session)
            msg = "Заплатили 10 кр. Кот доволен и оставил подарок."

    # ---- Склад концентратов ----
    elif eid == "supply_cache":
        if choice_id == "take_credits":
            credits_delta = 30
            msg = "Набрали химикатов на обмен. +30 кредитов."
        elif choice_id == "remove_card":
            # - Сигнал для run.py - удалить случайную non-curse карту из колоды
            msg = "REMOVE_RANDOM_CARD"

    # ---- Забытый рецепт ----
    elif eid == "forgotten_recipe":
        if choice_id == "download":
            hp_delta = -10
            card_reward = await _random_rare_card(session)
            msg = "Флэшбэк жжет, но техника ваша. -10 HP, получена Rare карта."
        elif choice_id == "ignore":
            msg = "Вы прошли мимо чипа."

    # ---- Уличный алтарь ----
    elif eid == "street_altar":
        if choice_id == "pray":
            # - run.py применит полное лечение и спишет 30% кредитов
            msg = "STREET_ALTAR_HEAL"
        elif choice_id == "ignore":
            msg = "Вы не задержались у алтаря."

    # ---- Патруль Элиты ----
    elif eid == "elite_patrol":
        if choice_id == "bribe":
            if user_credits < 50:
                raise ValueError("Недостаточно кредитов")
            credits_delta = -50
            msg = "Патруль пропустил. -50 кредитов."
        elif choice_id == "steal":
            if random.random() < 0.5:
                credits_delta = 40
                msg = "Удача! Вы выскользнули Ядра. +40 кредитов."
            else:
                msg = "FIGHT_ELITE"  # - сигнал для run.py

    # ---- Сломанный торговый автомат ----
    elif eid == "broken_vend":
        if choice_id == "smash":
            if random.random() < 0.5:
                msg = "VEND_DROP_INGREDIENT"  # - сигнал для run.py - дроп в run_ingredients
            else:
                hp_delta = -8
                msg = "Электрический разряд! -8 HP."
        elif choice_id == "hack":
            if user_credits < 20:
                raise ValueError("Недостаточно кредитов")
            credits_delta = -20
            msg = "VEND_DROP_INGREDIENT"  # - гарантированный дроп
        elif choice_id == "ignore":
            msg = "Вы прошли мимо."

    else:
        msg = "Вы ушли без последствий."

    return msg, hp_delta, credits_delta, card_reward, artifact_reward
