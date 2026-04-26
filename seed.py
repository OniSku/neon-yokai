import asyncio
import json

from sqlalchemy import select

from app.core.database import async_session_factory, engine, Base
from app.models.artifact import Artifact
from app.models.card import Card
from app.models.enemy import Enemy
from app.models.ingredient import Ingredient
from app.models.shop_item import ShopItem
from app.models.suture_relic import SutureRelic


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
    # === ШАГ 44: Common SOUR/BITTER ===
    {
        "name": "Уксусный выпад",
        "cost": 1, "type": "attack", "power": 7,
        "damage_type": "none", "tags": "SOUR",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Пролитая эссенция",
        "cost": 1, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "SOUR,AOE_WEAK",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Горчичный газ",
        "cost": 1, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "SOUR,AOE_VULNERABLE",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Холодный остаток",
        "cost": 1, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "BITTER,DRAW_1",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Обугленная щепа",
        "cost": 1, "type": "attack", "power": 8,
        "damage_type": "none", "tags": "BITTER",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Жженый сахар",
        "cost": 0, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "BITTER,ENERGY_1",
        "is_exhaust": True, "rarity": "common",
        "is_starting": False,
    },
    # === ШАГ 44: Rare (двойные теги) ===
    {
        "name": "Морская карамель",
        "cost": 2, "type": "skill", "power": 8,
        "damage_type": "none", "tags": "SALTY,SWEET,DRAW_1",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Кисло-сладкий соус",
        "cost": 1, "type": "skill", "power": 4,
        "damage_type": "none", "tags": "SWEET,SOUR",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Жгучая горечь",
        "cost": 2, "type": "attack", "power": 12,
        "damage_type": "none", "tags": "HOT,BITTER",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    # === ШАГ 44: Epic (shop-only) ===
    {
        "name": "Нейро-уксус",
        "cost": 2, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "SOUR,BITTER,DRAW_2",
        "is_exhaust": True, "rarity": "epic",
        "is_starting": False,
    },
    {
        "name": "Соль и перец",
        "cost": 1, "type": "skill", "power": 10,
        "damage_type": "none", "tags": "SALTY,HOT",
        "is_exhaust": True, "rarity": "epic",
        "is_starting": False,
    },
    # === ШАГ 44: Legendary ===
    {
        "name": "Пять вкусов изнанки",
        "cost": 3, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "HOT,SOUR,SWEET,BITTER,SALTY,DRAW_1",
        "is_exhaust": True, "rarity": "legendary",
        "is_starting": False,
    },
    # === ШАГ 50: Новые карты ===
    {
        "name": "Уксусный туман",
        "cost": 1, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "SOUR,AOE_WEAK",
        "is_exhaust": False, "rarity": "common",
        "is_starting": False,
    },
    {
        "name": "Горький финал",
        "cost": 2, "type": "attack", "power": 0,
        "damage_type": "none", "tags": "BITTER,BITTER_SCALE",
        "is_exhaust": True, "rarity": "epic",
        "is_starting": False,
    },
    {
        "name": "Пересоленный бульон",
        "cost": 2, "type": "skill", "power": 12,
        "damage_type": "none", "tags": "SALTY,EXHAUST_RANDOM",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Сахарный шок",
        "cost": 1, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "SWEET,ENERGY_2,SELF_VULNERABLE",
        "is_exhaust": True, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Двойная перегонка",
        "cost": 1, "type": "attack", "power": 6,
        "damage_type": "none", "tags": "HOT,SOUR",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Ферментированный яд",
        "cost": 1, "type": "skill", "power": 0,
        "damage_type": "none", "tags": "SOUR,BITTER,DRAW_1",
        "is_exhaust": False, "rarity": "rare",
        "is_starting": False,
    },
    {
        "name": "Солёная карамель",
        "cost": 2, "type": "skill", "power": 6,
        "damage_type": "none", "tags": "SALTY,SWEET,DRAW_1",
        "is_exhaust": False, "rarity": "rare",
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
    # === ШАГ 51: СТАДИЯ 3 ===
    {
        "name": "Тэнгу",
        "hp": 45,
        "base_damage": 7,
        "damage_type": "none",
        "ai_pattern": json.dumps([
            {"action": "attack", "damage": 5},
            {"action": "attack", "damage": 5},
            {"action": "attack", "damage": 5},
            {"action": "block", "amount": 8},
            {"action": "attack", "damage": 5},
            {"action": "attack", "damage": 5},
            {"action": "attack", "damage": 5},
        ]),
    },
    {
        "name": "Они",
        "hp": 60,
        "base_damage": 12,
        "damage_type": "none",
        "ai_pattern": json.dumps([
            {"action": "block", "amount": 10},
            {"action": "charge"},
            {"action": "attack", "damage": 28},
            {"action": "block", "amount": 10},
            {"action": "charge"},
            {"action": "attack", "damage": 28},
        ]),
    },
    # === СТАДИЯ 2 ===
    {
        "name": "Каппа",
        "hp": 40,
        "base_damage": 8,
        "damage_type": "none",
        "ai_pattern": json.dumps([
            {"action": "block", "amount": 15},
            {"action": "attack", "damage": 6},
            {"action": "block", "amount": 10},
            {"action": "attack", "damage": 12},
            {"action": "attack", "damage": 8, "apply_debuff": "VULNERABLE", "debuff_duration": 1},
        ]),
    },
    {
        "name": "Рокурокуби",
        "hp": 30,
        "base_damage": 5,
        "damage_type": "none",
        "ai_pattern": json.dumps([
            {"action": "apply_debuff", "debuff": "VULNERABLE", "debuff_duration": 2},
            {"action": "attack", "damage": 4},
            {"action": "attack", "damage": 4},
            {"action": "apply_debuff", "debuff": "WEAK", "debuff_duration": 2},
            {"action": "attack", "damage": 6},
            {"action": "apply_debuff", "debuff": "VULNERABLE", "debuff_duration": 1},
            {"action": "apply_debuff", "debuff": "WEAK", "debuff_duration": 1},
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
    # === Ингредиенты ===
    {
        "name": "Лемонграсс",
        "description": "Чистый SOUR (уязвимость). +1 в инвентарь.",
        "price": 20,
        "category": "ingredient",
        "payload": '{"ingredient_name": "Лайм"}',
    },
    {
        "name": "Перец чили",
        "description": "Сильный HOT. В инвентарь.",
        "price": 20,
        "category": "ingredient",
        "payload": '{"ingredient_name": "Перец чили"}',
    },
    {
        "name": "Мисо-паста",
        "description": "Смешанный SALTY+BITTER. В инвентарь.",
        "price": 25,
        "category": "ingredient",
        "payload": '{"ingredient_name": "Мисо-паста"}',
    },
    {
        "name": "Синтетический концентрат \'\u0423мами\'",
        "description": "Много стаков, но дает -5 макс HP на 1 бой. Дёшево, но токсично.",
        "price": 15,
        "category": "ingredient",
        "payload": '{"ingredient_name": "Синтетический концентрат \\"\u0423мами\\""}',
    },
    # === Услуги ===
    {
        "name": "Аптечка повара",
        "description": "Восстанавливает 20 HP немедленно.",
        "price": 30,
        "category": "consumable",
        "payload": '{"heal": 20}',
    },
    {
        "name": "Перепрошивка чипа",
        "description": "+1 энергии только на первый бой следующего забега.",
        "price": 40,
        "category": "consumable",
        "payload": '{"bonus_energy_first_fight": 1}',
    },
    {
        "name": "Чистка инвентаря",
        "description": "Удалить карту из колоды. Цена растёт: 50, 75, 100...",
        "price": 50,
        "category": "remove_card",
        "payload": '{"base_price": 50, "price_step": 25}',
    },
    # === Инструмент (артефакт) ===
    {
        "name": "Случайный инструмент",
        "description": "Случайный common-артефакт из запасов поставщика.",
        "price": 60,
        "category": "artifact",
        "payload": '{"rarity": "common"}',
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
    # === ШАГ 44: Новые артефакты ===
    {
        "name": "Банка старого маринада",
        "rarity": "rare",
        "description": "В начале боя все враги получают 1 стак кислоты (SOUR)",
        "trigger": "on_combat_start",
        "charges": -1,
        "is_active": True,
    },
    {
        "name": "Утяжеленный вок",
        "rarity": "common",
        "description": "+2 стака SALTY в начале каждого боя",
        "trigger": "on_combat_start",
        "charges": -1,
        "is_active": True,
    },
    {
        "name": "Заначка шефа",
        "rarity": "rare",
        "description": "Отдых восстанавливает на 10% HP больше обычного",
        "trigger": "on_rest",
        "charges": -1,
        "is_active": True,
    },
    # === ШАГ 51: Новые артефакты ===
    {
        "name": "Старый респиратор",
        "rarity": "rare",
        "description": "Первый дебафф в каждом бою автоматически отменяется. Один раз за бой.",
        "trigger": "on_combat_start",
        "charges": -1,
        "is_active": True,
    },
    {
        "name": "Заточка из арматуры",
        "rarity": "common",
        "description": "Каждая 3-я атака за бой наносит +5 урона.",
        "trigger": "on_card_played",
        "charges": -1,
        "is_active": True,
    },
    {
        "name": "Грязный фартук",
        "rarity": "common",
        "description": "После получения урона - отражает 3 урона врагу.",
        "trigger": "on_damage_taken",
        "charges": -1,
        "is_active": True,
    },
]


INGREDIENTS: list[dict] = [
    # === Натуральные (чистые, без дебаффов) ===
    {"name": "Дикий лемонграсс", "spicy": 0, "sour": 2, "sweet": 0, "bitter": 0, "salty": 0, "rarity": "common", "is_synthetic": False},
    {"name": "Морская соль из опреснителя", "spicy": 0, "sour": 0, "sweet": 0, "bitter": 0, "salty": 2, "rarity": "common", "is_synthetic": False},
    {"name": "Горный перец чили", "spicy": 2, "sour": 0, "sweet": 0, "bitter": 0, "salty": 0, "rarity": "common", "is_synthetic": False},
    {"name": "Сушеный гриб шиитаке", "spicy": 0, "sour": 0, "sweet": 0, "bitter": 1, "salty": 1, "rarity": "common", "is_synthetic": False},
    {"name": "Тростниковый сироп", "spicy": 0, "sour": 0, "sweet": 2, "bitter": 0, "salty": 0, "rarity": "common", "is_synthetic": False},
    {"name": "Корень хрена", "spicy": 2, "sour": 1, "sweet": 0, "bitter": 0, "salty": 0, "rarity": "uncommon", "is_synthetic": False},
    {"name": "Зеленый чай высшего сорта", "spicy": 0, "sour": 0, "sweet": 0, "bitter": 2, "salty": 0, "rarity": "uncommon", "is_synthetic": False},
    {"name": "Ферментированные бобы", "spicy": 0, "sour": 0, "sweet": 0, "bitter": 0, "salty": 2, "rarity": "uncommon", "is_synthetic": False},
    {"name": "Сушеная цедра юдзу", "spicy": 0, "sour": 2, "sweet": 0, "bitter": 0, "salty": 0, "rarity": "rare", "is_synthetic": False},
    {"name": "Мед диких пчел", "spicy": 0, "sour": 0, "sweet": 2, "bitter": 0, "salty": 0, "rarity": "rare", "is_synthetic": False},
    # === Синтетика (дебафф SYNTHETIC_WEAK при готовке) ===
    {"name": "Неоновый соевый соус", "spicy": 0, "sour": 0, "sweet": 0, "bitter": 0, "salty": 2, "rarity": "common", "is_synthetic": True},
    {"name": "Глитч-корень", "spicy": 0, "sour": 2, "sweet": 0, "bitter": 0, "salty": 0, "rarity": "common", "is_synthetic": True},
    {"name": "Пластиковый имбирь", "spicy": 2, "sour": 0, "sweet": 0, "bitter": 1, "salty": 0, "rarity": "common", "is_synthetic": True},
    {"name": "Синтетический Умами-порошок", "spicy": 2, "sour": 2, "sweet": 2, "bitter": 2, "salty": 2, "rarity": "common", "is_synthetic": True},
    {"name": "Цифровой сахар", "spicy": 0, "sour": 0, "sweet": 2, "bitter": 0, "salty": 0, "rarity": "common", "is_synthetic": True},
    {"name": "Жидкий хлор-лайм", "spicy": 0, "sour": 2, "sweet": 0, "bitter": 0, "salty": 0, "rarity": "uncommon", "is_synthetic": True},
    {"name": "Био-масло Элита", "spicy": 2, "sour": 0, "sweet": 0, "bitter": 0, "salty": 2, "rarity": "uncommon", "is_synthetic": True},
    {"name": "Эссенция Синий дракон", "spicy": 0, "sour": 0, "sweet": 0, "bitter": 2, "salty": 0, "rarity": "uncommon", "is_synthetic": True},
    {"name": "Порошок васаби v.2.0", "spicy": 2, "sour": 0, "sweet": 0, "bitter": 0, "salty": 0, "rarity": "uncommon", "is_synthetic": True},
    {"name": "Текстурированный белок Якудза", "spicy": 2, "sour": 2, "sweet": 2, "bitter": 2, "salty": 2, "rarity": "rare", "is_synthetic": True},
]


SUTURE_RELICS: list[dict] = [
    {
        "id": 1,
        "name": "Токсичная оплетка",
        "description": "В начале боя накладывает 2 Уязвимости на всех врагов и 1 на Повара.",
        "effect_tag": "ON_COMBAT_START_TOXIC_WRAP",
        "currency": "slime",
        "price": 5,
    },
    {
        "id": 2,
        "name": "Гнилой фильтр",
        "description": "В начале боя дает 1 стак защиты от дебаффа (Artifact).",
        "effect_tag": "ON_COMBAT_START_ROTTEN_FILTER",
        "currency": "cores",
        "price": 2,
    },
    {
        "id": 3,
        "name": "Хватка Каппы",
        "description": "При взрыве HOT-комбо лечит 1 HP.",
        "effect_tag": "ON_HOT_COMBO_KAPPA_GRIP",
        "currency": "slime",
        "price": 10,
    },
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

    async with async_session_factory() as session:
        for relic_data in SUTURE_RELICS:
            result = await session.execute(
                select(SutureRelic).where(SutureRelic.id == relic_data["id"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(SutureRelic(**relic_data))
            else:
                for key, value in relic_data.items():
                    setattr(existing, key, value)
        await session.commit()

    print("Seed completed: cards, enemies, ingredients, shop items, artifacts, suture relics loaded.")


if __name__ == "__main__":
    asyncio.run(seed())
