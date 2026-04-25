import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enemy import Enemy
from app.schemas.battle import EnemySlot, MapNode

NUM_FLOORS: int = 10
NUM_LANES: int = 3

ELITE_HP_MULT: float = 1.5
ELITE_ENEMY_NAMES: set[str] = {
    "Они-Обжора",
    "Тэнгу-Курьер",
}
BOSS_ENEMY_NAMES: set[str] = {"Нурарихён"}

COMBAT_GROUP_WEIGHTS: list[tuple[int, float]] = [(1, 0.5), (2, 0.35), (3, 0.15)]

AMBUSH_NODE = MapNode(
    index=0,
    floor=0,
    lane=1,
    node_type="ambush",
    enemy_id=None,
    enemy_name="Засада коллекторов",
    enemy_hp=70,
    is_ambush=True,
)


def _roll_group_size() -> int:
    r = random.random()
    cumulative = 0.0
    for size, weight in COMBAT_GROUP_WEIGHTS:
        cumulative += weight
        if r < cumulative:
            return size
    return 1


def _pick_enemy(
    enemies: list[Enemy],
    prefer_strong: bool = False,
    prefer_elite: bool = False,
    prefer_boss: bool = False,
) -> Enemy | None:
    if not enemies:
        return None
    if prefer_boss:
        pool = [e for e in enemies if e.name in BOSS_ENEMY_NAMES]
        if pool:
            return random.choice(pool)
        return sorted(enemies, key=lambda e: e.hp, reverse=True)[0]
    if prefer_elite:
        pool = [e for e in enemies if e.name in ELITE_ENEMY_NAMES]
        if pool:
            return random.choice(pool)
    if prefer_strong:
        return sorted(enemies, key=lambda e: e.hp, reverse=True)[0]
    normal = [e for e in enemies if e.name not in ELITE_ENEMY_NAMES and e.name not in BOSS_ENEMY_NAMES]
    return random.choice(normal) if normal else random.choice(enemies)


def _make_enemy_slots(
    enemies: list[Enemy],
    count: int,
    prefer_elite: bool = False,
) -> list[EnemySlot]:
    slots: list[EnemySlot] = []
    for _ in range(count):
        e = _pick_enemy(enemies, prefer_elite=prefer_elite)
        if e is None:
            continue
        hp = int(e.hp * ELITE_HP_MULT) if prefer_elite else e.hp
        slots.append(EnemySlot(enemy_id=e.id, name=e.name, hp=hp, max_hp=hp))
    return slots


def _build_1_3_1_structure() -> dict[tuple[int, int], list[tuple[int, int]]]:
    """Структура карты 1-3-1: Hub (1) -> 3 пути -> Boss (1).

    - Этаж 0: 1 HUB (lane=1)
    - Этажи 1-8: 3 узла (lanes 0,1,2) со связями
    - Этаж 9: 1 BOSS (lane=1)

    Связи:
    - С HUB (0,1) -> все 3 узла этажа 1
    - Этажи 1-7: каждый узел соединяется с соседними и своей lane на следующем этаже
    - Этаж 8: все 3 узла ведут к BOSS (9,1)
    """
    connections: dict[tuple[int, int], list[tuple[int, int]]] = {}

    # Этаж 0: HUB
    connections[(0, 1)] = [(1, 0), (1, 1), (1, 2)]

    # Этажи 1-7: переплетения
    for floor in range(1, 8):
        for lane in range(3):
            next_floor = floor + 1
            next_nodes: list[tuple[int, int]] = []

            # Связь с той же lane
            next_nodes.append((next_floor, lane))

            # Связь с соседней lane (если есть)
            if lane > 0:
                next_nodes.append((next_floor, lane - 1))
            if lane < 2:
                next_nodes.append((next_floor, lane + 1))

            connections[(floor, lane)] = list(set(next_nodes))

    # Этаж 8: все ведут к BOSS
    connections[(8, 0)] = [(9, 1)]
    connections[(8, 1)] = [(9, 1)]
    connections[(8, 2)] = [(9, 1)]

    # Этаж 9: BOSS (нет исходящих)
    connections[(9, 1)] = []

    return connections


def _assign_node_type(
    floor_idx: int,
    prev_type: str | None,
) -> str:
    # GDD Layer structure: 0-Start, 7-Elite, 9-Boss
    if floor_idx == 0:
        return "hub"
    if floor_idx == 7:
        return "elite"
    if floor_idx == 9:
        return "boss"

    # Stage progression per GDD:
    # 1-3: Stage 1 (Гаки)
    # 4-6: Stage 2 (Рокурокуби, Каппа)
    # 7-9: Stage 3 (Они, Тэнгу)
    if floor_idx in (1, 2, 3):
        pool = ["combat", "combat", "combat", "event", "shop"]
    elif floor_idx in (4, 5, 6):
        pool = ["combat", "combat", "event", "shop", "rest"]
    elif floor_idx == 8:
        pool = ["combat", "event", "rest", "shop"]
    else:
        pool = ["combat", "event"]

    if prev_type == "elite":
        pool = [t for t in pool if t != "elite"]
    if prev_type == "rest":
        pool = [t for t in pool if t != "rest"]

    if not pool:
        pool = ["combat"]

    return random.choice(pool)


async def generate_map(
    session: AsyncSession,
    debt_level: int = 0,
) -> list[MapNode]:
    result = await session.execute(select(Enemy))
    all_enemies = list(result.scalars().all())

    connections = _build_1_3_1_structure()

    # Фиксированная структура позиций
    positions: list[tuple[int, int]] = [
        (0, 1),  # HUB
        (1, 0), (1, 1), (1, 2),
        (2, 0), (2, 1), (2, 2),
        (3, 0), (3, 1), (3, 2),
        (4, 0), (4, 1), (4, 2),
        (5, 0), (5, 1), (5, 2),
        (6, 0), (6, 1), (6, 2),
        (7, 0), (7, 1), (7, 2),
        (8, 0), (8, 1), (8, 2),
        (9, 1),  # BOSS
    ]

    pos_to_idx: dict[tuple[int, int], int] = {pos: i for i, pos in enumerate(positions)}
    nodes: list[MapNode] = []

    prev_types: dict[int, str] = {}

    for pos in positions:
        idx = pos_to_idx[pos]
        floor_idx, lane = pos

        nt = _assign_node_type(floor_idx, prev_types.get(lane))
        prev_types[lane] = nt

        # Получаем next_indices из структуры 1-3-1
        next_positions = connections.get(pos, [])
        next_indices = sorted(pos_to_idx[np] for np in next_positions if np in pos_to_idx)

        enemy: Enemy | None = None
        enemy_slots: list[EnemySlot] = []

        if nt == "boss":
            enemy = _pick_enemy(all_enemies, prefer_boss=True)
            ehp = (enemy.hp if enemy else 200) + 50
            boss_slot = EnemySlot(
                enemy_id=enemy.id if enemy else None,
                name=enemy.name if enemy else "Boss",
                hp=ehp,
                max_hp=ehp,
            )
            # Два мертвых Гаки для механики некромантии
            gaki_slot_1 = EnemySlot(
                enemy_id=None,
                name="Голодный Гаки",
                hp=0,  # Мертв
                max_hp=25,
            )
            gaki_slot_2 = EnemySlot(
                enemy_id=None,
                name="Голодный Гаки",
                hp=0,  # Мертв
                max_hp=25,
            )
            enemy_slots = [boss_slot, gaki_slot_1, gaki_slot_2]
        elif nt == "elite":
            enemy = _pick_enemy(all_enemies, prefer_elite=True)
            ehp = int((enemy.hp if enemy else 80) * ELITE_HP_MULT)
            enemy_slots = [EnemySlot(
                enemy_id=enemy.id if enemy else None,
                name=enemy.name if enemy else "Elite",
                hp=ehp,
                max_hp=ehp,
            )]
        elif nt in ("combat", "ambush"):
            group_size = _roll_group_size()
            enemy_slots = _make_enemy_slots(all_enemies, group_size)
            if enemy_slots:
                enemy = None
        # event, rest, treasure -> no enemies

        primary_name = ""
        primary_hp = 0
        primary_id = None
        if enemy_slots:
            primary_name = enemy_slots[0].name
            primary_hp = enemy_slots[0].hp
            primary_id = enemy_slots[0].enemy_id
        if enemy:
            primary_name = enemy.name
            primary_hp = enemy.hp
            primary_id = enemy.id

        node = MapNode(
            index=idx,
            floor=floor_idx,
            lane=lane,
            node_type=nt,
            enemy_id=primary_id,
            enemy_name=primary_name,
            enemy_hp=primary_hp,
            enemies=enemy_slots,
            next_nodes=next_indices,
        )
        nodes.append(node)

    if debt_level >= 4 and nodes:
        first = nodes[0]
        if first.node_type == "hub":
            ambush = AMBUSH_NODE.model_copy()
            ambush.index = first.index
            ambush.floor = 0
            ambush.lane = first.lane
            ambush.next_nodes = first.next_nodes
            nodes[0] = ambush

    return nodes
