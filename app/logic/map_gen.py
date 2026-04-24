import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enemy import Enemy
from app.schemas.battle import EnemySlot, MapNode

NUM_FLOORS: int = 10
NUM_LANES: int = 3
NUM_PATHS: int = 4

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


def _carve_paths() -> dict[tuple[int, int], set[tuple[int, int]]]:
    grid: dict[tuple[int, int], set[tuple[int, int]]] = {}
    for _ in range(NUM_PATHS):
        lane = random.randint(0, NUM_LANES - 1)
        for floor_idx in range(NUM_FLOORS - 1):
            pos = (floor_idx, lane)
            delta = random.choice([-1, 0, 0, 1])
            next_lane = max(0, min(NUM_LANES - 1, lane + delta))
            next_pos = (floor_idx + 1, next_lane)
            grid.setdefault(pos, set()).add(next_pos)
            grid.setdefault(next_pos, set())
            lane = next_lane
        grid.setdefault((NUM_FLOORS - 1, lane), set())
    return grid


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

    grid = _carve_paths()

    pos_to_idx: dict[tuple[int, int], int] = {}
    nodes: list[MapNode] = []

    sorted_positions = sorted(grid.keys())
    for i, pos in enumerate(sorted_positions):
        pos_to_idx[pos] = i

    prev_types: dict[int, str] = {}

    for pos in sorted_positions:
        idx = pos_to_idx[pos]
        floor_idx, lane = pos

        nt = _assign_node_type(floor_idx, prev_types.get(lane))
        prev_types[lane] = nt

        next_indices = sorted(pos_to_idx[np] for np in grid[pos] if np in pos_to_idx)

        if floor_idx == 9:
            next_indices = []

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
            gaki_slot_1 = EnemySlot(
                enemy_id=None,
                name="Голодный Гаки",
                hp=25,
                max_hp=25,
            )
            gaki_slot_2 = EnemySlot(
                enemy_id=None,
                name="Голодный Гаки",
                hp=0,
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

    if nodes:
        boss_indices = [n.index for n in nodes if n.node_type == "boss"]
        if boss_indices:
            for n in nodes:
                if n.floor == 8:
                    n.next_nodes = boss_indices

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
