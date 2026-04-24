import pytest
from unittest.mock import AsyncMock, MagicMock

from app.logic.map_gen import BOSS_POSITION, MAP_SIZE, REST_POSITIONS, generate_map
from app.schemas.battle import MapNode, RunState


def _mock_session(enemies: list | None = None) -> AsyncMock:
    if enemies is None:
        enemies = []
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = enemies
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    return session


def _mock_enemy(eid: int = 1, name: str = "Mob", hp: int = 40) -> MagicMock:
    e = MagicMock()
    e.id = eid
    e.name = name
    e.hp = hp
    return e


@pytest.mark.asyncio
async def test_generate_map_size() -> None:
    session = _mock_session([_mock_enemy()])
    nodes = await generate_map(session, debt_level=0)
    assert len(nodes) == MAP_SIZE


@pytest.mark.asyncio
async def test_generate_map_rest_positions() -> None:
    session = _mock_session([_mock_enemy()])
    nodes = await generate_map(session, debt_level=0)
    for pos in REST_POSITIONS:
        assert nodes[pos].node_type == "rest"


@pytest.mark.asyncio
async def test_generate_map_boss_position() -> None:
    session = _mock_session([_mock_enemy()])
    nodes = await generate_map(session, debt_level=0)
    assert nodes[BOSS_POSITION].node_type == "boss"


@pytest.mark.asyncio
async def test_generate_map_combat_nodes() -> None:
    session = _mock_session([_mock_enemy()])
    nodes = await generate_map(session, debt_level=0)
    combat_indices = [i for i in range(MAP_SIZE) if i not in REST_POSITIONS and i != BOSS_POSITION]
    for idx in combat_indices:
        assert nodes[idx].node_type == "combat"


@pytest.mark.asyncio
async def test_generate_map_debt_level_4_ambush() -> None:
    session = _mock_session([_mock_enemy()])
    nodes = await generate_map(session, debt_level=4)
    assert nodes[0].node_type == "ambush"
    assert nodes[0].is_ambush is True
    assert nodes[0].enemy_name == "Засада коллекторов"


@pytest.mark.asyncio
async def test_generate_map_debt_level_3_no_ambush() -> None:
    session = _mock_session([_mock_enemy()])
    nodes = await generate_map(session, debt_level=3)
    assert nodes[0].node_type == "combat"
    assert nodes[0].is_ambush is False


@pytest.mark.asyncio
async def test_generate_map_no_enemies_fallback() -> None:
    session = _mock_session([])
    nodes = await generate_map(session, debt_level=0)
    assert len(nodes) == MAP_SIZE
    for node in nodes:
        if node.node_type == "combat":
            assert node.enemy_name == "Street Thug"
        elif node.node_type == "boss":
            assert node.enemy_name == "Boss"


def test_run_state_json_roundtrip() -> None:
    nodes = [
        MapNode(index=0, node_type="combat", enemy_name="A", enemy_hp=40),
        MapNode(index=1, node_type="rest", enemy_name="", enemy_hp=0),
        MapNode(index=2, node_type="boss", enemy_name="B", enemy_hp=80),
    ]
    run = RunState(user_id=1, map_nodes=nodes, current_node_index=0)

    json_str = run.model_dump_json()
    restored = RunState.model_validate_json(json_str)

    assert len(restored.map_nodes) == 3
    assert restored.map_nodes[0].node_type == "combat"
    assert restored.map_nodes[1].node_type == "rest"
    assert restored.map_nodes[2].node_type == "boss"
    assert restored.battle is None


def test_ambush_node_no_loot_flag() -> None:
    node = MapNode(
        index=0,
        node_type="ambush",
        enemy_name="Засада коллекторов",
        enemy_hp=70,
        is_ambush=True,
    )
    assert node.is_ambush is True
