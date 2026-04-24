import json
import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.logic.artifacts import on_combat_start, on_rest
from app.logic.meta import get_inventory_limit, get_max_hp_bonus, parse_meta, save_meta
from app.logic.combat import end_turn, execute_card, start_turn
from app.logic.events import pick_random_event, resolve_event_choice
from app.logic.debt import generate_debt_cards
from app.logic.economy import apply_interest
from app.logic.deck import init_deck
from app.logic.loot import claim_rewards, generate_pending_rewards
from app.logic.map_gen import generate_map
from app.logic.persistence import delete_run_state, load_run_state, save_run_state
from app.models.artifact import Artifact
from app.models.card import Card
from app.models.enemy import Enemy
from app.models.user import User
from app.models.user_deck_card import UserDeckCard
from app.schemas.battle import ArtifactInstance, BattleState, CardInstance, EnemyAction, EnemyState, EnemySlot, Fighter, MapNode, PendingRewards, RunState
from app.schemas.requests import ClaimRewardRequest, EventChoiceRequest, NextNodeRequest, RunActionRequest, RunStartRequest
from app.schemas.responses import (
    ClaimRewardResponse,
    EventChoiceResponse,
    EventResponse,
    LootItem,
    NextNodeResponse,
    RewardResponse,
    RunActionResponse,
    RunStartResponse,
)

router = APIRouter(prefix="/run", tags=["run"])


def _find_node(run: RunState) -> MapNode:
    for n in run.map_nodes:
        if n.index == run.current_node_index:
            return n
    return run.map_nodes[0]


def _card_to_instance(c: Card, is_upgraded: bool = False) -> CardInstance:
    tags = [t.strip() for t in c.tags.split(",") if t.strip()] if c.tags else []
    return CardInstance(
        card_id=c.id,
        name=c.name,
        cost=c.cost,
        type=c.type,
        power=c.power,
        damage_type=c.damage_type,
        tags=tags,
        is_exhaust=c.is_exhaust,
        rarity=c.rarity,
        is_upgraded=is_upgraded,
    )


STARTER_CARD_NAMES: list[tuple[str, int]] = [
    ("Удар тесаком", 3),
    ("Чугунная крышка", 2),
    ("Выпаривание", 1),
]


async def _build_user_deck(session: AsyncSession, user_id: int) -> list[CardInstance]:
    result = await session.execute(select(Card))
    all_cards = {c.id: c for c in result.scalars().all()}
    cards_by_name = {c.name: c for c in all_cards.values()}

    deck: list[CardInstance] = []

    for name, qty in STARTER_CARD_NAMES:
        card = cards_by_name.get(name)
        if card:
            for _ in range(qty):
                deck.append(_card_to_instance(card))

    if not deck:
        deck = [
            CardInstance(card_id=0, name="Удар тесаком", cost=1, type="attack", power=7, damage_type="slashing", tags=["HOT"]),
        ] * 5 + [
            CardInstance(card_id=0, name="Чугунная крышка", cost=1, type="skill", power=6, damage_type="blunt", tags=[]),
        ] * 5

    udc_result = await session.execute(
        select(UserDeckCard).where(UserDeckCard.user_id == user_id)
    )
    for udc in udc_result.scalars().all():
        card = all_cards.get(udc.card_id)
        if card is None:
            continue
        for _ in range(udc.quantity):
            deck.append(_card_to_instance(card, is_upgraded=udc.is_upgraded))

    return deck


STARTER_ARTIFACT_COUNT: int = 1


async def _load_starter_artifacts(session: AsyncSession) -> list[ArtifactInstance]:
    result = await session.execute(
        select(Artifact).where(Artifact.rarity == "common", Artifact.is_active == True)
    )
    pool = list(result.scalars().all())
    if not pool:
        return []
    chosen = random.sample(pool, k=min(STARTER_ARTIFACT_COUNT, len(pool)))
    return [
        ArtifactInstance(
            artifact_id=a.id,
            name=a.name,
            rarity=a.rarity,
            description=a.description,
            trigger=a.trigger,
            charges=a.charges,
            is_active=a.is_active,
        )
        for a in chosen
    ]


ELITE_DAMAGE_MULT: float = 1.2


def _scale_action_damage(data: dict, mult: float) -> dict:
    scaled = dict(data)
    if "damage" in scaled:
        scaled["damage"] = int(scaled["damage"] * mult)
    if "if_true" in scaled and scaled["if_true"]:
        scaled["if_true"] = _scale_action_damage(scaled["if_true"], mult)
    if "if_false" in scaled and scaled["if_false"]:
        scaled["if_false"] = _scale_action_damage(scaled["if_false"], mult)
    return scaled


async def _load_enemy_pattern(
    session: AsyncSession,
    enemy_id: int | None,
    damage_mult: float = 1.0,
) -> list[EnemyAction]:
    if enemy_id is None:
        return []
    result = await session.execute(
        select(Enemy).where(Enemy.id == enemy_id)
    )
    db_enemy = result.scalar_one_or_none()
    if db_enemy is None:
        return []
    raw = json.loads(db_enemy.ai_pattern)
    if damage_mult != 1.0:
        raw = [_scale_action_damage(step, damage_mult) for step in raw]
    return [EnemyAction(**step) for step in raw]


async def _start_node_battle(
    session: AsyncSession,
    run: RunState,
    user_debt_level: int,
    max_hp: int = 80,
) -> None:
    node = _find_node(run)

    dmg_mult = ELITE_DAMAGE_MULT if node.node_type == "elite" else 1.0

    deck = await _build_user_deck(session, run.user_id)
    debt_cards = await generate_debt_cards(user_debt_level)
    deck.extend(debt_cards)

    enemy_states: list[EnemyState] = []
    if node.enemies:
        for slot in node.enemies:
            pattern = await _load_enemy_pattern(session, slot.enemy_id, damage_mult=dmg_mult)
            alive = slot.hp > 0
            start_block = 25 if "Каппа" in slot.name else 0
            enemy_states.append(EnemyState(
                fighter=Fighter(name=slot.name, hp=slot.hp, max_hp=slot.max_hp, block=start_block),
                ai_pattern=pattern,
                alive=alive,
            ))

    primary_pattern = await _load_enemy_pattern(session, node.enemy_id, damage_mult=dmg_mult)

    primary_fighter = Fighter(name=node.enemy_name, hp=node.enemy_hp, max_hp=node.enemy_hp)
    if enemy_states:
        primary_fighter = enemy_states[0].fighter

    battle = BattleState(
        user_id=run.user_id,
        player=Fighter(hp=run.current_hp, max_hp=max_hp),
        enemy=primary_fighter,
        enemies=enemy_states,
        ai_pattern=primary_pattern,
    )
    await init_deck(battle, deck)
    for combo in run.combo_effects:
        buff_copy = combo.buff.model_copy()
        if combo.flavor == "sour":
            if enemy_states:
                for es in enemy_states:
                    es.fighter.buffs.append(buff_copy.model_copy())
            else:
                battle.enemy.buffs.append(buff_copy)
        else:
            battle.player.buffs.append(buff_copy)
    await on_combat_start(battle, run.artifacts)
    await start_turn(battle)
    run.battle = battle


@router.post("/start", response_model=RunStartResponse)
async def run_start(
    body: RunStartRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RunStartResponse:
    existing = await load_run_state(session, user.id)
    if existing:
        await delete_run_state(session, user.id)

    await session.execute(
        delete(UserDeckCard).where(UserDeckCard.user_id == user.id)
    )
    await session.commit()

    cards_result = await session.execute(select(Card).where(Card.is_starting == True))
    starting_cards = {c.name: c for c in cards_result.scalars().all()}

    starter_quantities = [
        ("Удар тесаком", 3),
        ("Чугунная крышка", 2),
        ("Выпаривание", 1),
    ]
    for card_name, qty in starter_quantities:
        card = starting_cards.get(card_name)
        if card:
            udc = UserDeckCard(
                user_id=user.id,
                card_id=card.id,
                quantity=qty,
                is_upgraded=False,
            )
            session.add(udc)
    await session.commit()

    map_nodes = await generate_map(session, debt_level=user.debt_level)
    starter_arts = await _load_starter_artifacts(session)
    hp_bonus = get_max_hp_bonus(user)
    base_max_hp = 80 + hp_bonus

    first_node = map_nodes[0] if map_nodes else None
    run = RunState(
        user_id=user.id,
        map_nodes=map_nodes,
        current_node_index=first_node.index if first_node else 0,
        current_hp=base_max_hp,
        artifacts=starter_arts,
    )

    if first_node and first_node.node_type in ("combat", "boss", "ambush", "elite"):
        await _start_node_battle(session, run, user.debt_level, max_hp=base_max_hp)

    await save_run_state(session, run)

    return RunStartResponse(run=run)


@router.post("/action", response_model=RunActionResponse)
async def run_action(
    body: RunActionRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RunActionResponse:
    run = await load_run_state(session, user.id)
    if run is None or run.run_finished:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active run",
        )

    if run.battle is None or run.battle.finished:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active battle on current node",
        )

    state = run.battle
    current_node = _find_node(run)

    if body.action == "play_card":
        if body.hand_index is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="hand_index is required for play_card",
            )
        card = await execute_card(state, body.hand_index, artifacts=run.artifacts, target_index=body.target_index)
        if state.finished:
            run.current_hp = state.player.hp
            run.combo_effects = []
            if state.winner == "player":
                current_node.completed = True
                ec = max(len(current_node.enemies), 1)
                rewards = await generate_pending_rewards(session, node_type=current_node.node_type, enemy_count=ec)
                run.reward_phase = True
                run.pending_rewards = rewards
            else:
                run.run_finished = True
                await apply_interest(session, user)
        await save_run_state(session, run)
        return RunActionResponse(
            message=f"Сыграна: {card.name}",
            card_played=card.name,
            run=run,
        )

    if body.action == "end_turn":
        enemy_dmg = await end_turn(state, artifacts=run.artifacts)
        if state.finished:
            run.current_hp = state.player.hp
            run.combo_effects = []
            if state.winner == "player":
                current_node.completed = True
                ec = max(len(current_node.enemies), 1)
                rewards = await generate_pending_rewards(session, node_type=current_node.node_type, enemy_count=ec)
                run.reward_phase = True
                run.pending_rewards = rewards
            else:
                run.run_finished = True
                await apply_interest(session, user)
        await save_run_state(session, run)
        return RunActionResponse(
            message=f"Ход завершен. {state.enemy.name} нанес {enemy_dmg} урона",
            enemy_damage=enemy_dmg,
            run=run,
        )

    if body.action == "abandon":
        run.combo_effects = []
        await delete_run_state(session, user.id)
        await apply_interest(session, user)
        return RunActionResponse(
            message="Забег брошен",
            run=run,
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown action: {body.action}",
    )


async def _handle_treasure(
    session: AsyncSession,
    run: RunState,
    node: MapNode,
) -> str:
    from app.logic.loot import _roll_artifact_reward
    run.battle = None
    node.completed = True
    artifact = await _roll_artifact_reward(session, node_type="combat")
    cr = random.randint(20, 40)
    run.reward_phase = True
    run.pending_rewards = PendingRewards(
        credits=cr,
        experience=0,
        artifact_reward=artifact,
    )
    return f"Сокровище! Найдено {cr} кредитов" + (f" и {artifact.name}" if artifact else "")


@router.post("/next_node", response_model=NextNodeResponse)
async def next_node(
    body: NextNodeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NextNodeResponse:
    run = await load_run_state(session, user.id)
    if run is None or run.run_finished:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active run",
        )

    if run.reward_phase:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Claim rewards before moving to next node",
        )

    if run.active_event is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resolve event before moving to next node",
        )

    current = _find_node(run)
    if current.node_type in ("combat", "boss", "ambush", "elite", "event") and not current.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current node not completed",
        )

    chosen_idx = body.chosen_node_index
    if chosen_idx not in current.next_nodes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move to node {chosen_idx}. Valid: {current.next_nodes}",
        )

    target_node = None
    for n in run.map_nodes:
        if n.index == chosen_idx:
            target_node = n
            break

    if target_node is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Node {chosen_idx} not found",
        )

    run.current_node_index = chosen_idx
    node = target_node

    if node.node_type in ("combat", "boss", "ambush", "elite"):
        hp_bonus = get_max_hp_bonus(user)
        await _start_node_battle(session, run, user.debt_level, max_hp=80 + hp_bonus)
        tag = "☠ ЭЛИТА: " if node.node_type == "elite" else ""
        enemy_count = len(node.enemies) if node.enemies else 1
        msg = f"Бой: {tag}{node.enemy_name}" + (f" (+{enemy_count - 1} ещё)" if enemy_count > 1 else "")
    elif node.node_type == "event":
        run.battle = None
        event = pick_random_event(floor=node.floor)
        node.event_id = event.event_id
        run.active_event = event
        msg = f"Событие: {event.title}"
    elif node.node_type == "rest":
        run.battle = None
        run.rest_choice_pending = True
        msg = "Тележка повара: выберите действие - Сон (30% HP) или Заточка (улучшить карту)"
    elif node.node_type == "treasure":
        msg = await _handle_treasure(session, run, node)
    else:
        run.battle = None
        node.completed = True
        msg = f"Узел {chosen_idx}: {node.node_type}"

    await save_run_state(session, run)

    return NextNodeResponse(
        message=msg,
        node=node,
        run=run,
    )


@router.get("/rewards", response_model=RewardResponse)
async def get_rewards(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RewardResponse:
    run = await load_run_state(session, user.id)
    if run is None or not run.reward_phase or run.pending_rewards is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending rewards",
        )

    rw = run.pending_rewards
    loot_items = [LootItem(**item) for item in rw.loot]
    return RewardResponse(
        credits=rw.credits,
        experience=rw.experience,
        loot=loot_items,
        card_choices=rw.card_choices,
        artifact_reward=rw.artifact_reward,
    )


@router.post("/claim_reward", response_model=ClaimRewardResponse)
async def claim_reward_endpoint(
    body: ClaimRewardRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ClaimRewardResponse:
    run = await load_run_state(session, user.id)
    if run is None or not run.reward_phase or run.pending_rewards is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending rewards to claim",
        )

    if run.pending_rewards.artifact_reward is not None:
        run.artifacts.append(run.pending_rewards.artifact_reward)

    inv_limit = get_inventory_limit(user)
    await claim_rewards(session, user, run.pending_rewards, body.chosen_card_id, inventory_limit=inv_limit)

    run.reward_phase = False
    run.pending_rewards = None
    await save_run_state(session, run)

    card_msg = ""
    if body.chosen_card_id is not None:
        card_msg = f" Карта добавлена в колоду."

    return ClaimRewardResponse(
        message=f"Награды получены.{card_msg}",
        credits=user.credits,
        run=run,
    )


@router.get("/event", response_model=EventResponse)
async def get_event(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EventResponse:
    run = await load_run_state(session, user.id)
    if run is None or run.active_event is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active event",
        )
    return EventResponse(event=run.active_event)


@router.post("/event_choice", response_model=EventChoiceResponse)
async def event_choice_endpoint(
    body: EventChoiceRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EventChoiceResponse:
    run = await load_run_state(session, user.id)
    if run is None or run.active_event is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active event",
        )

    max_hp = 80 + get_max_hp_bonus(user)

    msg, hp_delta, credits_delta, card_reward, artifact_reward = await resolve_event_choice(
        session, run, body.choice_id, user.credits, max_hp=max_hp,
    )

    # Handle special event signals
    if msg == "FIGHT_ELITE":
        node = _find_node(run)
        node.node_type = "elite"
        node.enemy_name = "Коллектор-Элита"
        node.enemy_hp = 100
        node.enemies = [EnemySlot(enemy_id=None, name="Коллектор-Элита", hp=100, max_hp=100)]
        run.active_event = None
        await _start_node_battle(session, run, user.debt_level, max_hp=max_hp)
        await save_run_state(session, run)
        return EventChoiceResponse(
            message="Коллекторы нападают! Бой с Элитой!",
            hp_delta=0, credits_delta=0,
            card_reward=None, artifact_reward=None, run=run,
        )

    if msg == "FIGHT_BOSS_LEGENDARY":
        from app.logic.events import _random_artifact
        node = _find_node(run)
        node.node_type = "boss"
        node.enemy_name = "Нурарихён"
        node.enemy_hp = 250
        node.enemies = [EnemySlot(enemy_id=None, name="Нурарихён", hp=250, max_hp=250)]
        run.active_event = None
        await _start_node_battle(session, run, user.debt_level, max_hp=max_hp)
        leg_art = await _random_artifact(session, rarity="legendary")
        if leg_art:
            run.artifacts.append(leg_art)
        await save_run_state(session, run)
        return EventChoiceResponse(
            message="Страх материализовался! Бой с Боссом! Legendary артефакт получен!",
            hp_delta=0, credits_delta=0,
            card_reward=None, artifact_reward=leg_art, run=run,
        )

    if msg == "CHAOS_REPLACE_DECK":
        all_cards_result = await session.execute(select(Card).where(Card.type.in_(["attack", "skill"])))
        replacement_pool = list(all_cards_result.scalars().all())
        udc_result = await session.execute(
            select(UserDeckCard).where(UserDeckCard.user_id == user.id)
        )
        all_udc = list(udc_result.scalars().all())
        replaced_count = 0
        for udc in all_udc:
            card_result = await session.execute(select(Card).where(Card.id == udc.card_id))
            card_obj = card_result.scalar_one_or_none()
            if card_obj and card_obj.type in ("attack", "skill") and replacement_pool:
                new_card = random.choice(replacement_pool)
                udc.card_id = new_card.id
                replaced_count += 1
        node = _find_node(run)
        node.completed = True
        run.active_event = None
        user.credits = max(0, user.credits + credits_delta)
        await session.commit()
        await save_run_state(session, run)
        return EventChoiceResponse(
            message=f"Хаос! {replaced_count} карт заменены случайными!",
            hp_delta=0, credits_delta=credits_delta,
            card_reward=None, artifact_reward=None, run=run,
        )

    if msg == "ABSOLUTE_DEBT":
        curse_result = await session.execute(
            select(Card).where(Card.name == "Мертвый груз")
        )
        curse_card = curse_result.scalar_one_or_none()
        if curse_card:
            udc_result = await session.execute(
                select(UserDeckCard).where(
                    UserDeckCard.user_id == user.id,
                    UserDeckCard.card_id == curse_card.id,
                )
            )
            existing_udc = udc_result.scalar_one_or_none()
            if existing_udc:
                existing_udc.quantity += 3
            else:
                session.add(UserDeckCard(user_id=user.id, card_id=curse_card.id, quantity=3))
        node = _find_node(run)
        node.completed = True
        run.active_event = None
        user.credits += credits_delta
        await session.commit()
        await save_run_state(session, run)
        return EventChoiceResponse(
            message="Абсолютный долг! +999 кредитов, но 3 проклятия добавлены в колоду.",
            hp_delta=0, credits_delta=credits_delta,
            card_reward=None, artifact_reward=None, run=run,
        )

    if msg == "IMPLANT_MAX_HP_10":
        meta = parse_meta(user)
        meta["implant_hp"] = meta.get("implant_hp", 0) + 10
        save_meta(user, meta)
        max_hp += 10
        msg = "Имплант установлен! +10 Max HP, -15 текущего HP"

    run.current_hp = max(1, min(run.current_hp + hp_delta, max_hp))
    user.credits = max(0, user.credits + credits_delta)

    if artifact_reward is not None:
        run.artifacts.append(artifact_reward)

    if card_reward is not None:
        deck_result = await session.execute(
            select(UserDeckCard).where(
                UserDeckCard.user_id == user.id,
                UserDeckCard.card_id == card_reward.card_id,
            )
        )
        existing = deck_result.scalar_one_or_none()
        if existing is None:
            session.add(UserDeckCard(user_id=user.id, card_id=card_reward.card_id, quantity=1))
        else:
            existing.quantity += 1

    node = _find_node(run)
    node.completed = True
    run.active_event = None

    await session.commit()
    await save_run_state(session, run)

    return EventChoiceResponse(
        message=msg,
        hp_delta=hp_delta,
        credits_delta=credits_delta,
        card_reward=card_reward,
        artifact_reward=artifact_reward,
        run=run,
    )


@router.post("/rest/sleep")
async def rest_sleep(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    run = await load_run_state(session, user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="No active run")
    if not run.rest_choice_pending:
        raise HTTPException(status_code=400, detail="No rest choice pending")

    max_hp = 80 + get_max_hp_bonus(user)
    heal_amount = int(max_hp * 0.3)
    run.current_hp = min(run.current_hp + heal_amount, max_hp)

    bonus_cr, rest_log = await on_rest(run.artifacts)
    if bonus_cr > 0:
        user.credits += bonus_cr

    node = _find_node(run)
    node.completed = True
    run.rest_choice_pending = False

    await session.commit()
    await save_run_state(session, run)

    rest_extra = (" " + " ".join(rest_log)) if rest_log else ""
    return {
        "message": f"Сон восстановил {heal_amount} HP{rest_extra}",
        "current_hp": run.current_hp,
        "max_hp": max_hp,
        "run": run,
    }


@router.post("/rest/upgrade")
async def rest_upgrade(
    card_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    run = await load_run_state(session, user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="No active run")
    if not run.rest_choice_pending:
        raise HTTPException(status_code=400, detail="No rest choice pending")

    deck_result = await session.execute(
        select(UserDeckCard).where(
            UserDeckCard.user_id == user.id,
            UserDeckCard.card_id == card_id,
        )
    )
    deck_card = deck_result.scalar_one_or_none()
    if deck_card is None:
        raise HTTPException(status_code=404, detail="Card not in deck")

    deck_card.is_upgraded = True

    node = _find_node(run)
    node.completed = True
    run.rest_choice_pending = False

    await session.commit()
    await save_run_state(session, run)

    return {
        "message": "Карта улучшена! +3 к урону или блоку",
        "upgraded_card_id": card_id,
        "run": run,
    }
