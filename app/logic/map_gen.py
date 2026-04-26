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
    "Тэнгу",
    "Они",
}
STAGE2_ENEMY_NAMES: set[str] = {
    "Каппа",
    "Рокурокуби",
}
STAGE1_ENEMY_NAMES: set[str] = {
    "Голодный Гаки",
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


def _pick_enemy_for_floor(
    enemies: list[Enemy],
    floor_idx: int,
) -> Enemy | None:
    # - Стадии по этажам: 1-3 Гаки, 4-6 Стадия 2, 7+ элиты
    if not enemies:
        return None
    if floor_idx in (1, 2, 3):
        pool = [e for e in enemies if e.name in STAGE1_ENEMY_NAMES]
    elif floor_idx in (4, 5, 6):
        pool = [e for e in enemies if e.name in STAGE2_ENEMY_NAMES]
    else:
        pool = [e for e in enemies if e.name not in ELITE_ENEMY_NAMES and e.name not in BOSS_ENEMY_NAMES]
    return random.choice(pool) if pool else _pick_enemy(enemies)


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


def _build_sts_structure() -> dict[tuple[int, int], list[tuple[int, int]]]:
    """Структура карты Slay the Spire style.

    - Этаж 0: 1 узел (HUB, lane=1)
    - Этаж 1: 3 узла (lanes 0,1,2). Узел 0 связан со всеми тремя.
    - Этажи 2-8: 3 узла. Каждый узел (f,l) связан с (f+1,l) [прямо],
      и с 50% шансом с (f+1,l-1) или (f+1,l+1) [диагональ].
    - Этаж 9: 1 узел (BOSS, lane=1). Все 3 узла этажа 8 связаны с ним.
    """
    connections: dict[tuple[int, int], list[tuple[int, int]]] = {}

    # Этаж 0: HUB -> все 3 узла этажа 1
    connections[(0, 1)] = [(1, 0), (1, 1), (1, 2)]

    # Этажи 1-8: связи согласно правилам
    for floor in range(1, 9):
        for lane in range(3):
            next_floor = floor + 1
            next_nodes: list[tuple[int, int]] = []

            # Гарантированная прямая связь
            next_nodes.append((next_floor, lane))

            # Случайная диагональ с 50% шансом
            if random.random() < 0.5:
                # Выбираем направление диагонали
                if lane == 0:
                    # Только вправо
                    next_nodes.append((next_floor, 1))
                elif lane == 2:
                    # Только влево
                    next_nodes.append((next_floor, 1))
                else:  # lane == 1
                    # Лево или право с равным шансом
                    if random.random() < 0.5:
                        next_nodes.append((next_floor, 0))
                    else:
                        next_nodes.append((next_floor, 2))

            connections[(floor, lane)] = list(set(next_nodes))

    # Этаж 9: BOSS - гарантируем связь от всех узлов этажа 8
    # Сначала добавляем обратные связи к боссу
    for lane in range(3):
        if (8, lane) in connections:
            # Добавляем босса в next_nodes каждого узла этажа 8
            if (9, 1) not in connections[(8, lane)]:
                connections[(8, lane)].append((9, 1))
        else:
            connections[(8, lane)] = [(9, 1)]

    # Босс не имеет исходящих связей
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

    connections = _build_sts_structure()

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
            # - Выбираем врагов по стадии этажа
            slots: list[EnemySlot] = []
            for _ in range(group_size):
                e = _pick_enemy_for_floor(all_enemies, floor_idx)
                if e:
                    slots.append(EnemySlot(enemy_id=e.id, name=e.name, hp=e.hp, max_hp=e.hp))
            enemy_slots = slots
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

    # Засада Якудзы: при debt_level >= 2 сужаем depth=7 до одного AMBUSH узла
    if debt_level >= 2:
        # Собираем узлы depth=7 (floor_idx=7, lanes 0,1,2)
        floor7_indices = [i for i, n in enumerate(nodes) if n.floor == 7]

        # Громила Якудзы - Гаки с баффом +5 к Силе
        yakuza_hp = 55
        yakuza_slot = EnemySlot(
            enemy_id=None,
            name="Громила Якудзы",
            hp=yakuza_hp,
            max_hp=yakuza_hp,
        )

        if floor7_indices:
            # Оставляем только средний узел (lane=1), остальные помечаем как недоступные
            # Находим узел lane=1 на floor=7
            center_idx = next(
                (i for i, n in enumerate(nodes) if n.floor == 7 and n.lane == 1),
                floor7_indices[0]
            )
            center_node = nodes[center_idx]
            center_node.node_type = "ambush"
            center_node.enemy_name = "Громила Якудзы"
            center_node.enemy_hp = yakuza_hp
            center_node.enemies = [yakuza_slot]

            # Узлы lane=0 и lane=2 на floor=7 - перенаправляем их next_nodes на center
            for i, n in enumerate(nodes):
                if n.floor == 7 and n.lane != 1:
                    # Заменяем тип на пустой/недоступный, убираем врагов
                    nodes[i] = MapNode(
                        index=n.index,
                        floor=n.floor,
                        lane=n.lane,
                        node_type="ambush",
                        enemy_name="Громила Якудзы",
                        enemy_hp=yakuza_hp,
                        enemies=[yakuza_slot],
                        next_nodes=center_node.next_nodes,
                    )

            # Перенаправляем все узлы с floor=6, у которых next_nodes включает боковые узлы floor=7,
            # чтобы они вели только к center_node
            for i, n in enumerate(nodes):
                if n.floor == 6:
                    # Заменяем все ссылки на floor=7 узлы -> только center_idx
                    floor7_node_indices = {nd.index for nd in nodes if nd.floor == 7}
                    new_next = [center_node.index if ni in floor7_node_indices else ni for ni in n.next_nodes]
                    # Убираем дубли
                    nodes[i].next_nodes = list(dict.fromkeys(new_next))

    elif debt_level >= 4 and nodes:
        first = nodes[0]
        if first.node_type == "hub":
            ambush = AMBUSH_NODE.model_copy()
            ambush.index = first.index
            ambush.floor = 0
            ambush.lane = first.lane
            ambush.next_nodes = first.next_nodes
            nodes[0] = ambush

    return nodes
