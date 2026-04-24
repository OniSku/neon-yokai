import pytest

from app.logic.combat import (
    apply_buffs_for_tags,
    apply_damage,
    calculate_damage,
    check_battle_end,
    end_turn,
    enemy_turn,
    execute_card,
    resolve_parry,
    start_turn,
    tick_buffs,
)
from app.logic.deck import init_deck
from app.schemas.battle import BattleState, Buff, CardInstance, EnemyAction, Fighter, ParryResult


def _attack(
    name: str = "Strike",
    power: int = 6,
    cost: int = 1,
    damage_type: str = "slashing",
    tags: list[str] | None = None,
) -> CardInstance:
    return CardInstance(card_id=0, name=name, cost=cost, type="attack", power=power, damage_type=damage_type, tags=tags or [])


def _skill(
    name: str = "Defend",
    power: int = 5,
    cost: int = 1,
    damage_type: str = "none",
) -> CardInstance:
    return CardInstance(card_id=0, name=name, cost=cost, type="skill", power=power, damage_type=damage_type)


def _state() -> BattleState:
    return BattleState(
        user_id=1,
        player=Fighter(hp=80, max_hp=80, energy=3),
        enemy=Fighter(name="Enemy", hp=50, max_hp=50),
    )


@pytest.mark.asyncio
async def test_apply_damage_no_block() -> None:
    target = Fighter(hp=50, block=0)
    dealt = await apply_damage(target, 10)
    assert target.hp == 40
    assert dealt == 10


@pytest.mark.asyncio
async def test_apply_damage_partial_block() -> None:
    target = Fighter(hp=50, block=4)
    dealt = await apply_damage(target, 10)
    assert target.hp == 44
    assert target.block == 0
    assert dealt == 6


@pytest.mark.asyncio
async def test_apply_damage_full_block() -> None:
    target = Fighter(hp=50, block=15)
    dealt = await apply_damage(target, 10)
    assert target.hp == 50
    assert target.block == 5
    assert dealt == 0


@pytest.mark.asyncio
async def test_apply_damage_hp_floors_at_zero() -> None:
    target = Fighter(hp=5, block=0)
    await apply_damage(target, 100)
    assert target.hp == 0


@pytest.mark.asyncio
async def test_apply_buffs_for_tags_creates_new_buff() -> None:
    fighter = Fighter()
    await apply_buffs_for_tags(fighter, ["HOT"])
    assert len(fighter.buffs) == 1
    assert fighter.buffs[0].tag == "SPICY_BUFF"


@pytest.mark.asyncio
async def test_apply_buffs_for_tags_extends_existing_duration() -> None:
    fighter = Fighter(buffs=[Buff(tag="SPICY_BUFF", duration=2)])
    await apply_buffs_for_tags(fighter, ["HOT"])
    assert len(fighter.buffs) == 1
    assert fighter.buffs[0].duration == 3


@pytest.mark.asyncio
async def test_apply_buffs_ignores_unknown_tags() -> None:
    fighter = Fighter()
    await apply_buffs_for_tags(fighter, ["UNKNOWN"])
    assert len(fighter.buffs) == 0


@pytest.mark.asyncio
async def test_calculate_damage_no_buff() -> None:
    fighter = Fighter()
    dmg = await calculate_damage(fighter, 10, ["HOT"])
    assert dmg == 10


@pytest.mark.asyncio
async def test_calculate_damage_with_matching_buff() -> None:
    fighter = Fighter(buffs=[Buff(tag="SPICY_BUFF", duration=2, multiplier=1.25, flat_bonus=2)])
    dmg = await calculate_damage(fighter, 10, ["HOT"])
    assert dmg == int(10 * 1.25) + 2


@pytest.mark.asyncio
async def test_tick_buffs_decrements_and_removes_expired() -> None:
    fighter = Fighter(buffs=[
        Buff(tag="A", duration=1),
        Buff(tag="B", duration=3),
    ])
    await tick_buffs(fighter)
    assert len(fighter.buffs) == 1
    assert fighter.buffs[0].tag == "B"
    assert fighter.buffs[0].duration == 2


@pytest.mark.asyncio
async def test_check_battle_end_enemy_dead() -> None:
    state = _state()
    state.enemy.hp = 0
    result = await check_battle_end(state)
    assert result is True
    assert state.finished is True
    assert state.winner == "player"


@pytest.mark.asyncio
async def test_check_battle_end_player_dead() -> None:
    state = _state()
    state.player.hp = 0
    result = await check_battle_end(state)
    assert result is True
    assert state.finished is True
    assert state.winner == "enemy"


@pytest.mark.asyncio
async def test_check_battle_end_both_alive() -> None:
    state = _state()
    result = await check_battle_end(state)
    assert result is False
    assert state.finished is False


@pytest.mark.asyncio
async def test_execute_attack_card_deals_damage() -> None:
    state = _state()
    state.hand = [_attack(power=10)]
    state.player.energy = 3

    card = await execute_card(state, 0)

    assert card.name == "Strike"
    assert state.enemy.hp == 40
    assert state.player.energy == 2


@pytest.mark.asyncio
async def test_execute_skill_card_adds_block() -> None:
    state = _state()
    state.hand = [_skill(power=5)]
    state.player.energy = 3

    await execute_card(state, 0)

    assert state.player.block == 5


@pytest.mark.asyncio
async def test_execute_card_kills_enemy_sets_finished() -> None:
    state = _state()
    state.enemy.hp = 5
    state.hand = [_attack(power=10)]

    await execute_card(state, 0)

    assert state.finished is True
    assert state.winner == "player"


@pytest.mark.asyncio
async def test_enemy_turn_deals_scaling_damage() -> None:
    state = _state()
    state.turn = 2
    dealt = await enemy_turn(state)
    expected = 8 + 2
    assert dealt == expected
    assert state.player.hp == 80 - expected


@pytest.mark.asyncio
async def test_enemy_turn_respects_block() -> None:
    state = _state()
    state.turn = 1
    state.player.block = 5
    dealt = await enemy_turn(state)
    assert state.player.block == 0
    assert dealt == (8 + 1) - 5


@pytest.mark.asyncio
async def test_start_turn_increments_and_draws() -> None:
    state = _state()
    state.hand_size = 3
    cards = [_attack(name=f"C{i}") for i in range(10)]
    await init_deck(state, cards)

    await start_turn(state)

    assert state.turn == 1
    assert state.phase == "player_turn"
    assert state.player.energy == 3
    assert len(state.hand) == 3


@pytest.mark.asyncio
async def test_end_turn_full_cycle() -> None:
    state = _state()
    state.hand_size = 3
    cards = [_attack(name=f"C{i}") for i in range(10)]
    await init_deck(state, cards)
    await start_turn(state)

    initial_hp = state.player.hp
    enemy_dmg = await end_turn(state)

    assert state.turn == 2
    assert state.player.hp == initial_hp - enemy_dmg
    assert len(state.hand) == 3
    assert state.phase == "player_turn"


@pytest.mark.asyncio
async def test_full_battle_until_victory() -> None:
    state = _state()
    state.enemy.hp = 15
    state.hand_size = 5
    cards = [_attack(power=6) for _ in range(10)]
    await init_deck(state, cards)
    await start_turn(state)

    while not state.finished:
        if state.hand:
            await execute_card(state, 0)
        else:
            await end_turn(state)

    assert state.winner is not None


@pytest.mark.asyncio
async def test_parry_skill_sets_parry_type() -> None:
    state = _state()
    parry_card = _skill(name="Parry", power=3, damage_type="slashing")
    state.hand = [parry_card]
    state.player.energy = 3

    await execute_card(state, 0)

    assert state.player.parry_type == "slashing"
    assert state.player.block == 3


@pytest.mark.asyncio
async def test_parry_skill_none_damage_type_no_parry() -> None:
    state = _state()
    defend = _skill(name="Defend", power=5, damage_type="none")
    state.hand = [defend]
    state.player.energy = 3

    await execute_card(state, 0)

    assert state.player.parry_type is None


@pytest.mark.asyncio
async def test_resolve_parry_matching_type() -> None:
    state = _state()
    state.player.parry_type = "slashing"

    result = await resolve_parry(state, 20, "slashing")

    assert result.triggered is True
    assert result.blocked == 10
    assert result.reflected == 10
    assert state.player.parry_type is None


@pytest.mark.asyncio
async def test_resolve_parry_mismatched_type() -> None:
    state = _state()
    state.player.parry_type = "slashing"

    result = await resolve_parry(state, 20, "piercing")

    assert result.triggered is False
    assert result.blocked == 0
    assert state.player.parry_type == "slashing"


@pytest.mark.asyncio
async def test_resolve_parry_no_parry_set() -> None:
    state = _state()
    state.player.parry_type = None

    result = await resolve_parry(state, 20, "slashing")

    assert result.triggered is False


@pytest.mark.asyncio
async def test_enemy_turn_with_parry_reduces_and_reflects() -> None:
    state = _state()
    state.turn = 2
    state.player.parry_type = "slashing"
    initial_enemy_hp = state.enemy.hp

    dealt = await enemy_turn(state, enemy_damage_type="slashing")

    base = 8 + 2
    blocked = int(base * 0.5)
    expected_dealt = base - blocked
    assert dealt == expected_dealt
    assert state.player.hp == 80 - expected_dealt
    assert state.enemy.hp == initial_enemy_hp - blocked
    assert state.player.parry_type is None


@pytest.mark.asyncio
async def test_enemy_turn_parry_mismatch_no_effect() -> None:
    state = _state()
    state.turn = 2
    state.player.parry_type = "slashing"
    initial_enemy_hp = state.enemy.hp

    dealt = await enemy_turn(state, enemy_damage_type="blunt")

    base = 8 + 2
    assert dealt == base
    assert state.player.hp == 80 - base
    assert state.enemy.hp == initial_enemy_hp
    assert state.player.parry_type == "slashing"


@pytest.mark.asyncio
async def test_battle_state_json_roundtrip() -> None:
    state = _state()
    state.hand = [_attack(), _skill()]
    state.player.buffs = [Buff(tag="SPICY_BUFF", duration=2, multiplier=1.25, flat_bonus=2)]

    json_str = state.model_dump_json()
    restored = BattleState.model_validate_json(json_str)

    assert restored.user_id == state.user_id
    assert restored.player.hp == state.player.hp
    assert len(restored.hand) == 2
    assert restored.player.buffs[0].tag == "SPICY_BUFF"


@pytest.mark.asyncio
async def test_ai_pattern_attack_cycles() -> None:
    state = _state()
    state.turn = 1
    state.ai_pattern = [
        EnemyAction(action="attack", damage=5, damage_type="slashing"),
        EnemyAction(action="block", block=10),
    ]
    state.ai_index = 0

    dealt = await enemy_turn(state)
    assert dealt == 5 + 1
    assert state.player.hp == 80 - (5 + 1)

    dealt2 = await enemy_turn(state)
    assert dealt2 == 0
    assert state.enemy.block == 10


@pytest.mark.asyncio
async def test_ai_pattern_buff_action() -> None:
    state = _state()
    state.turn = 0
    state.ai_pattern = [
        EnemyAction(action="buff", buff_tag="RAGE", duration=2, multiplier=1.5),
    ]
    state.ai_index = 0

    await enemy_turn(state)

    assert len(state.enemy.buffs) == 1
    assert state.enemy.buffs[0].tag == "RAGE"
    assert state.enemy.buffs[0].duration == 2


@pytest.mark.asyncio
async def test_ai_pattern_debuff_action() -> None:
    state = _state()
    state.turn = 0
    state.ai_pattern = [
        EnemyAction(action="debuff", debuff_tag="POISON", duration=3, flat_damage=3),
    ]
    state.ai_index = 0

    await enemy_turn(state)

    poison = next((b for b in state.player.buffs if b.tag == "POISON"), None)
    assert poison is not None
    assert poison.duration == 3
    assert poison.flat_bonus == 3


@pytest.mark.asyncio
async def test_ai_pattern_wraps_around() -> None:
    state = _state()
    state.turn = 0
    state.ai_pattern = [
        EnemyAction(action="attack", damage=5, damage_type="slashing"),
        EnemyAction(action="block", block=3),
    ]
    state.ai_index = 0

    for _ in range(4):
        await enemy_turn(state)

    assert state.ai_index == 4
    assert state.enemy.block == 3 + 3
