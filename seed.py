import asyncio
import json

from sqlalchemy import select

from app.core.database import async_session_factory, engine, Base
from app.models.artifact import Artifact
from app.models.card import Card
from app.models.enemy import Enemy
from app.models.ingredient import Ingredient
from app.models.shop_item import ShopItem


CARDS: list[dict] = [
    # === STARTER DECK (6 cards) ===
    {
        "name": "Удар тесаком",
        "cost": 1, "type": "attack", "power": 7,
        "damage_type": "none", "tags": "HOT",
        "is_exhaust": False, "rarity": "common",
        "is_starting": True,
    },
    {
        "name": "Чугунная крышка",
        "cost": 1, "type": "skill", "power": 6,
        "damage_type": "none", "tags": "",
        "is_exhaust": False, "rarity": "common",
        "is_starting": True,
    },
    {
        "name": "Выпаривание",
        "cost": 2, "type": "attack", "power": 6,
        "damage_type": "none", "tags": "UNIQUE",
        "is_exhaust": False, "rarity": "common",
        "is_starting": True,
    },
    # === REWARD POOL (not starting) ===
    {
        "name": "Быстрый порез",
        "cost": 0, "type": "attack", "power": 4,
        "damage_type": "none", "tags": "HOT",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Укол вилкой",
        "cost": 1, "type": "attack", "power": 9,
        "damage_type": "none", "tags": "HOT",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Удар скалкой",
        "cost": 2, "type": "attack", "power": 14,
        "damage_type": "none", "tags": "BITTER",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Блок крышкой",
        "cost": 1, "type": "skill", "power": 6,
        "damage_type": "none", "tags": "SALTY",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Сладкая передышка",
        "cost": 1, "type": "skill", "power": 4,
        "damage_type": "none", "tags": "SWEET",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    # === RARE (25% drop) ===
    {
        "name": "Быстрая шинковка",
        "cost": 1, "type": "attack", "power": 5,
        "damage_type": "none", "tags": "HOT,DRAW_1",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Ревизия запасов",
        "cost": 1, "type": "skill", "power": 4,
        "damage_type": "none", "tags": "SWEET",
        "is_exhaust": True, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Фламбе",
        "cost": 2, "type": "attack", "power": 12,
        "damage_type": "none", "tags": "HOT,SWEET",
        "is_exhaust": True, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Маринад",
        "cost": 1, "type": "skill", "power": 8,
        "damage_type": "none", "tags": "SOUR,SALTY",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Кислотный бросок",
        "cost": 1, "type": "attack", "power": 5,
        "damage_type": "none", "tags": "SOUR",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Горький настой",
        "cost": 1, "type": "skill", "power": 8,
        "damage_type": "none", "tags": "BITTER",
        "is_exhaust": True, "rarity": "rare",
        "is_starting": False,
    },
    # === EPIC (shop only) ===
    {
        "name": "Глутамат натрия",
        "cost": 2, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "HOT,SOUR,SWEET,BITTER,DRAW_1",
        "is_exhaust": True, "rarity": "epic",
        "is_starting": False,
    },
    {
        "name": "Секретный ингредиент",
        "cost": 0, "type": "attack", "power": 15,
        "damage_type": "none", "tags": "SWEET,DRAW_1",
        "is_exhaust": True, "rarity": "epic",
        "is_starting": False,
    },
    # === LEGENDARY (5% drop, boss guaranteed) ===
    {
        "name": "Мастер-класс шефа",
        "cost": 3, "type": "skill", "power": 20,
        "damage_type": "none", "tags": "HOT,SOUR,SWEET,BITTER,DRAW_2",
        "is_exhaust": True, "rarity": "legendary",
        "is_starting": False,
    },
    {
        "name": "Техника тысячи порезов",
        "cost": 3, "type": "attack", "power": 25,
        "damage_type": "none", "tags": "HOT,DRAW_1",
        "is_exhaust": True, "rarity": "legendary",
        "is_starting": False,
    },
    # === AOE (rare) ===
    {
        "name": "Раскаленное масло",
        "cost": 2, "type": "attack", "power": 4,
        "damage_type": "none", "tags": "AOE,BURN,HOT",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Бросок вока",
        "cost": 2, "type": "attack", "power": 8,
        "damage_type": "none", "tags": "AOE,HOT",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    # === SALTY (defense) ===
    {
        "name": "Соляная корка",
        "cost": 1, "type": "skill", "power": 6,
        "damage_type": "none", "tags": "SALTY",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Кристаллизация",
        "cost": 1, "type": "skill", "power": 4,
        "damage_type": "none", "tags": "SALTY",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Консервация",
        "cost": 2, "type": "skill", "power": 12,
        "damage_type": "none", "tags": "SALTY,RETAIN",
        "is_exhaust": False, "rarity": "epic",
        "is_starting": False,
    },
    # === NEW CARDS (Step 38) ===
    {
        "name": "Фламбирование",
        "cost": 1, "type": "attack", "power": 9,
        "damage_type": "none", "tags": "HOT",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Раскаленный вок",
        "cost": 2, "type": "attack", "power": 16,
        "damage_type": "none", "tags": "HOT",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Едкий маринад",
        "cost": 1, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "SOUR",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Ферментация",
        "cost": 0, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "SOUR",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Карамелизация",
        "cost": 1, "type": "skill", "power": 5,
        "damage_type": "none", "tags": "SWEET",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Синтетический сироп",
        "cost": 1, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "SWEET",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Грязный эспрессо",
        "cost": 0, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "BITTER",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Пережженная корка",
        "cost": 1, "type": "attack", "power": 5,
        "damage_type": "none", "tags": "BITTER",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Глубокая засолка",
        "cost": 1, "type": "skill", "power": 10,
        "damage_type": "none", "tags": "SALTY",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Чугунная стойка",
        "cost": 2, "type": "skill", "power": 16,
        "damage_type": "none", "tags": "SALTY",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    # === CURSE ===
    {
        "name": "Мертвый груз",
        "cost": -1, "type": "curse", "power": 0,
        "damage_type": "none", "tags": "CURSE",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
]


ENEMIES: list[dict] = [
    # === YOKAI (только по GDD) ===
    {
        "name": "Голодный Гаки",
        "hp": 25,
        "base_damage": 5,
        "damage_type": "none",
        "ai_pattern": json.dumps([
            {"action": "attack", "damage": 5, "damage_type": "none", "steal": 3},
            {"action": "attack", "damage": 5, "damage_type": "none", "steal": 3},
            {"action": "flee", "condition": "stolen_gte_9"},
        ]),
    },
    # === BOSS ===
    {
        "name": "Нурарихён",
        "hp": 150,
        "base_damage": 15,
        "damage_type": "none",
        "ai_pattern": json.dumps([
            {"action": "summon_gaki", "condition": "gaki_count_lt_2"},
            {"action": "buff_all_gaki", "buff_tag": "RAGE", "duration": 1, "multiplier": 1.25, "self_block": 15},
            {"action": "attack", "damage": 15, "damage_type": "none", "apply_debuff": "VULNERABLE", "debuff_duration": 2},
            {"action": "attack", "damage": 20, "damage_type": "none"},
        ]),
    },
]


SHOP_ITEMS: list[dict] = [
    {
        "name": "Набор острых специй",
        "description": "Пакет из 3 редких специй для готовки",
        "price": 30,
        "category": "ingredient",
        "payload": '{"ingredient_ids": [5, 6, 7]}',
    },
    {
        "name": "Заточка тесака",
        "description": "Увеличивает урон slashing-карт на 2 до конца забега",
        "price": 50,
        "category": "upgrade",
        "payload": '{"buff_tag": "SHARPEN", "flat_bonus": 2}',
    },
    {
        "name": "Аптечка",
        "description": "Восстанавливает 20 HP в начале следующего боя",
        "price": 25,
        "category": "consumable",
        "payload": '{"heal": 20}',
    },
    {
        "name": "Дополнительная энергия",
        "description": "+1 к максимальной энергии на один бой",
        "price": 80,
        "category": "upgrade",
        "payload": '{"extra_energy": 1}',
    },
    {
        "name": "Карта: Двойной удар",
        "description": "Добавляет карту Двойной удар (ATK 12, slashing, exhaust) в колоду",
        "price": 60,
        "category": "card",
        "payload": '{"card_name": "Двойной удар", "type": "attack", "power": 12, "damage_type": "none", "cost": 2, "is_exhaust": true}',
    },
]


ARTIFACTS: list[dict] = [
    {
        "name": "Энергетик",
        "rarity": "common",
        "description": "+1 энергия в начале каждого боя",
        "trigger": "on_combat_start",
        "charges": -1,
        "is_active": True,
    },
    {
        "name": "Острый соус",
        "rarity": "common",
        "description": "+2 ко всему урону на весь бой",
        "trigger": "on_combat_start",
        "charges": -1,
        "is_active": True,
    },
    {
        "name": "Бронежилет шефа",
        "rarity": "rare",
        "description": "+5 блока в начале каждого боя",
        "trigger": "on_combat_start",
        "charges": -1,
        "is_active": True,
    },
    {
        "name": "Магнитная доска",
        "rarity": "rare",
        "description": "Возвращает первые 3 exhaust-карты в руку",
        "trigger": "on_card_played",
        "charges": 3,
        "is_active": True,
    },
    {
        "name": "Точильный камень",
        "rarity": "common",
        "description": "+1 блок после каждой атаки",
        "trigger": "on_card_played",
        "charges": -1,
        "is_active": True,
    },
    {
        "name": "Дефибриллятор",
        "rarity": "legendary",
        "description": "Одноразово спасает от смерти (HP = 1)",
        "trigger": "on_damage_taken",
        "charges": 1,
        "is_active": True,
    },
    {
        "name": "Шипованный фартук",
        "rarity": "rare",
        "description": "Отражает 3 урона врагу при каждом попадании",
        "trigger": "on_damage_taken",
        "charges": -1,
        "is_active": True,
    },
    {
        "name": "Свинья-копилка",
        "rarity": "common",
        "description": "Разбивается на отдыхе, дает +50 кредитов",
        "trigger": "on_rest",
        "charges": 1,
        "is_active": True,
        "broken_into": "Разбитая копилка",
    },
]


INGREDIENTS: list[dict] = [
    {"name": "Перец чили", "spicy": 5, "sour": 0, "sweet": 0, "bitter": 1, "salty": 0, "rarity": "common"},
    {"name": "Лайм", "spicy": 0, "sour": 5, "sweet": 1, "bitter": 0, "salty": 0, "rarity": "common"},
    {"name": "Мед", "spicy": 0, "sour": 0, "sweet": 6, "bitter": 0, "salty": 0, "rarity": "common"},
    {"name": "Горький корень", "spicy": 0, "sour": 1, "sweet": 0, "bitter": 5, "salty": 0, "rarity": "common"},
    {"name": "Васаби", "spicy": 7, "sour": 0, "sweet": 0, "bitter": 2, "salty": 0, "rarity": "uncommon"},
    {"name": "Тамаринд", "spicy": 1, "sour": 4, "sweet": 3, "bitter": 0, "salty": 0, "rarity": "uncommon"},
    {"name": "Нефритовый чай", "spicy": 0, "sour": 0, "sweet": 2, "bitter": 7, "salty": 0, "rarity": "rare"},
    {"name": "Кровавый апельсин", "spicy": 2, "sour": 6, "sweet": 3, "bitter": 0, "salty": 0, "rarity": "rare"},
    {"name": "Соевый соус", "spicy": 0, "sour": 0, "sweet": 0, "bitter": 0, "salty": 6, "rarity": "common"},
    {"name": "Морская соль", "spicy": 0, "sour": 0, "sweet": 0, "bitter": 0, "salty": 8, "rarity": "common"},
    {"name": "Мисо-паста", "spicy": 0, "sour": 0, "sweet": 1, "bitter": 1, "salty": 6, "rarity": "uncommon"},
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        for card_data in CARDS:
            result = await session.execute(
                select(Card).where(Card.name == card_data["name"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(Card(**card_data))
            else:
                # Обновляем существующую карту новыми данными
                for key, value in card_data.items():
                    setattr(existing, key, value)

        for enemy_data in ENEMIES:
            result = await session.execute(
                select(Enemy).where(Enemy.name == enemy_data["name"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(Enemy(**enemy_data))
            else:
                for key, value in enemy_data.items():
                    setattr(existing, key, value)

        for ing_data in INGREDIENTS:
            result = await session.execute(
                select(Ingredient).where(Ingredient.name == ing_data["name"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(Ingredient(**ing_data))
            else:
                for key, value in ing_data.items():
                    setattr(existing, key, value)

        for shop_data in SHOP_ITEMS:
            result = await session.execute(
                select(ShopItem).where(ShopItem.name == shop_data["name"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(ShopItem(**shop_data))
            else:
                for key, value in shop_data.items():
                    setattr(existing, key, value)

        for art_data in ARTIFACTS:
            result = await session.execute(
                select(Artifact).where(Artifact.name == art_data["name"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(Artifact(**art_data))
            else:
                for key, value in art_data.items():
                    setattr(existing, key, value)

        await session.commit()

    print("Seed completed: cards, enemies, ingredients, shop items, artifacts loaded.")


if __name__ == "__main__":
    asyncio.run(seed())
