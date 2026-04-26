import math
import random

from app.logic.artifacts import on_card_played, on_damage_taken
from app.logic.deck import discard_hand, draw_cards, play_card
from app.schemas.battle import ArtifactInstance, BattleState, Buff, CardInstance, EnemyAction, EnemyIntent, EnemyState, Fighter, ParryResult

PARRY_BLOCK_RATIO: float = 0.5


TAG_BUFF_MAP: dict[str, str] = {
    "HOT": "SPICY_BUFF",
    "SOUR": "SOUR_BUFF",
    "SWEET": "SWEET_BUFF",
    "BITTER": "BITTER_BUFF",
    "SALTY": "SALTY_BUFF",
}

# 5 Вкусов для системы Комбо
FLAVOR_TAGS: set[str] = {"HOT", "SOUR", "SWEET", "BITTER", "SALTY"}
COMBO_THRESHOLD: int = 4
COMBO_THRESHOLD_WITH_CHARGE: int = 3


async def _add_combo_stack(state: BattleState, tags: list[str]) -> str | None:
    """Добавить стак комбо для каждого тега вкуса. Возвращает тег если комбо взорвалось."""
    exploded: str | None = None
    for tag in tags:
        if tag in FLAVOR_TAGS:
            state.combo_stacks[tag] += 1
            # Проверяем порог
            threshold = COMBO_THRESHOLD_WITH_CHARGE if state.combo_charges > 0 else COMBO_THRESHOLD
            if state.combo_stacks[tag] >= threshold:
                exploded = tag
    return exploded


async def _explode_combo(state: BattleState, flavor: str) -> str:
    """Активировать эффект комбо. Возвращает сообщение о эффекте."""
    # Вычитаем порог - остаток переносится на следующий круг
    threshold = COMBO_THRESHOLD_WITH_CHARGE if state.combo_charges > 0 else COMBO_THRESHOLD
    state.combo_stacks[flavor] = max(0, state.combo_stacks[flavor] - threshold)

    # Тратим заряд если был
    if state.combo_charges > 0:
        state.combo_charges -= 1

    # Применяем эффект
    if flavor == "HOT":
        # 15 чистого урона текущей цели
        target = _get_target(state)
        await apply_damage(target, 15)
        return "COMBO HOT: 15 урона!"

    elif flavor == "SOUR":
        # 2 Weak + 2 Vulnerable на всех врагов
        if state.enemies:
            for es in state.enemies:
                if es.alive:
                    es.fighter.buffs.append(Buff(tag="WEAK", duration=2))
                    es.fighter.buffs.append(Buff(tag="VULNERABLE", duration=2))
        return "COMBO SOUR: Weak + Vulnerable на всех!"

    elif flavor == "SWEET":
        # Лечение 4 HP + взять 2 карты
        state.player.hp = min(state.player.hp + 4, state.player.max_hp)
        await draw_cards(state, 2)
        return "COMBO SWEET: +4 HP, +2 карты!"

    elif flavor == "BITTER":
        # +2 Энергии + взять 1 карту
        state.player.energy += 2
        await draw_cards(state, 1)
        return "COMBO BITTER: +2 энергии, +1 карта!"

    elif flavor == "SALTY":
        # +12 Блока + Удержание текущего блока
        state.player.block += 12
        state.player.buffs.append(Buff(tag="RETAIN_BLOCK", duration=1))
        return "COMBO SALTY: +12 блока, удержание!"

    return ""


def _get_target(state: BattleState) -> Fighter:
    if state.enemies:
        alive = [es for es in state.enemies if es.alive]
        if alive:
            idx = state.target_index % len(alive)
            return alive[idx].fighter
    return state.enemy


async def apply_buffs_for_tags(
    fighter: Fighter,
    tags: list[str],
) -> None:
    for tag in tags:
        buff_tag = TAG_BUFF_MAP.get(tag)
        if buff_tag is None:
            continue

        existing = next((b for b in fighter.buffs if b.tag == buff_tag), None)
        if existing:
            existing.duration += 1
        else:
            fighter.buffs.append(
                Buff(tag=buff_tag, duration=2, multiplier=1.25, flat_bonus=2)
            )


async def calculate_damage(
    attacker: Fighter,
    base_power: int,
    tags: list[str],
) -> int:
    damage = base_power

    for buff in attacker.buffs:
        if buff.tag in [TAG_BUFF_MAP.get(t) for t in tags]:
            damage = int(damage * buff.multiplier) + buff.flat_bonus
        elif buff.tag == "COMBO_BURN":
            damage += buff.flat_bonus

    return max(damage, 0)


async def apply_damage(target: Fighter, damage: int) -> int:
    absorbed = min(target.block, damage)
    target.block -= absorbed
    remaining = damage - absorbed
    target.hp = max(target.hp - remaining, 0)
    return remaining


def update_enemy_intents(state: BattleState) -> None:
    """Обновление намерений врагов на следующий ход."""
    enemies = state.enemies if state.enemies else []
    if not enemies and state.enemy:
        # Legacy single enemy mode
        enemies = [EnemyState(fighter=state.enemy)]

    for es in enemies:
        if not es.alive or es.fighter.hp <= 0:
            es.intent = None
            continue

        name = es.fighter.name
        r = random.random()

        if "Гаки" in name:
            # Гаки: 70% атака (7), 30% кража (10 кр)
            if r < 0.7:
                es.intent = EnemyIntent(type="attack", value=7, description="Атака 7")
            else:
                es.intent = EnemyIntent(type="steal", value=10, description="Кража 10 кр")

        elif "Каппа" in name:
            # Каппа: 50% атака (5), 50% блок (6)
            if r < 0.5:
                es.intent = EnemyIntent(type="attack", value=5, description="Атака 5")
            else:
                es.intent = EnemyIntent(type="defend", value=6, description="Блок 6")

        elif "Рокурокуби" in name:
            # Рокурокуби: всегда атака с вариацией
            dmg = random.randint(4, 8)
            es.intent = EnemyIntent(type="attack", value=dmg, description=f"Атака {dmg}")

        elif "Они" in name:
            # Они: тяжелая атака
            es.intent = EnemyIntent(type="attack", value=12, description="Атака 12")

        elif "Тэнгу" in name:
            # Тэнгу: быстрая атака + уклонение
            es.intent = EnemyIntent(type="attack", value=6, description="Атака 6")

        elif "Нурарихён" in name:
            # Босс Нурарихён: проверяем наличие мертвых Гаки и живых
            has_dead_gaki = any(
                not e.alive and "Гаки" in e.fighter.name
                for e in enemies
            )
            has_alive_gaki = any(
                e.alive and "Гаки" in e.fighter.name
                for e in enemies
            )

            if has_dead_gaki and r < 0.4:
                es.intent = EnemyIntent(type="summon", value=0, description="Воскрешение Гаки")
            elif has_alive_gaki and r < 0.5:
                es.intent = EnemyIntent(type="buff", value=8, description="Ярость Гаки + Блок")
            else:
                es.intent = EnemyIntent(type="attack", value=15, description="Атака 15")

        else:
            # Default: атака
            es.intent = EnemyIntent(type="attack", value=5, description="Атака 5")


async def apply_damage_with_artifacts(
    state: BattleState,
    damage: int,
    artifacts: list[ArtifactInstance],
) -> int:
    final_damage, _ = await on_damage_taken(state, artifacts, damage)
    return await apply_damage(state.player, final_damage)


async def tick_buffs(fighter: Fighter) -> None:
    for buff in fighter.buffs:
        buff.duration -= 1
    fighter.buffs = [b for b in fighter.buffs if b.duration > 0]


def _sync_primary_enemy(state: BattleState) -> None:
    if state.enemies:
        alive = [es for es in state.enemies if es.alive]
        for es in state.enemies:
            if es.fighter.hp <= 0:
                es.alive = False
        if alive:
            state.enemy = alive[0].fighter


async def check_battle_end(state: BattleState) -> bool:
    if state.enemies:
        for es in state.enemies:
            if es.fighter.hp <= 0:
                es.alive = False
                # Коллапс Аномалии: смерть босса убивает всех оставшихся Гаки
                if "Нурарихён" in es.fighter.name:
                    for gaki in state.enemies:
                        if gaki is not es and "Гаки" in gaki.fighter.name:
                            gaki.fighter.hp = 0
                            gaki.alive = False
        alive = [es for es in state.enemies if es.alive]
        if not alive:
            state.finished = True
            state.winner = "player"
            state.enemy.hp = 0
            return True
    else:
        if state.enemy.hp <= 0:
            state.finished = True
            state.winner = "player"
            return True

    if state.player.hp <= 0:
        state.finished = True
        state.winner = "enemy"
        return True
    return False


def _is_aoe(card: CardInstance) -> bool:
    return "AOE" in card.tags


async def execute_card(
    state: BattleState,
    hand_index: int,
    artifacts: list[ArtifactInstance] | None = None,
    target_index: int | None = None,
) -> CardInstance:
    if hand_index < 0 or hand_index >= len(state.hand):
        raise ValueError("Invalid hand index")

    peeked = state.hand[hand_index]

    if peeked.type == "curse":
        raise ValueError("Curse cards cannot be played")

    if peeked.cost > state.player.energy:
        raise ValueError("Not enough energy")

    card = await play_card(state, hand_index)
    state.player.energy -= card.cost

    if target_index is not None:
        state.target_index = target_index

    await apply_buffs_for_tags(state.player, card.tags)

    if card.type == "attack":
        power_with_upgrade = math.ceil(card.power * 1.5) if card.is_upgraded else card.power
        damage = await calculate_damage(state.player, power_with_upgrade, card.tags)
        is_vyparivanie = card.name == "Выпаривание" or "UNIQUE" in card.tags
        if _is_aoe(card) and state.enemies:
            for es in state.enemies:
                if es.alive:
                    if is_vyparivanie:
                        strip_amount = min(es.fighter.block, 10)
                        es.fighter.block -= strip_amount
                    await apply_damage(es.fighter, damage)
                    if "BURN" in card.tags or "IGNITE" in card.tags:
                        es.fighter.buffs.append(
                            Buff(tag="BURN", duration=2, multiplier=1.0, flat_bonus=3)
                        )
        else:
            target = _get_target(state)
            if is_vyparivanie:
                strip_amount = min(target.block, 10)
                target.block -= strip_amount
            await apply_damage(target, damage)

    elif card.type == "skill":
        block_amount = math.ceil(card.power * 1.5) if card.is_upgraded else card.power
        state.player.block += block_amount
        if card.damage_type != "none":
            state.player.parry_type = card.damage_type
        if "SALTY" in card.tags:
            salty_buff = next((b for b in state.player.buffs if b.tag == "SALTY_BUFF"), None)
            if salty_buff:
                retain = next((b for b in state.player.buffs if b.tag == "RETAIN_BLOCK"), None)
                if retain:
                    retain.duration = max(retain.duration, 1)
                else:
                    state.player.buffs.append(Buff(tag="RETAIN_BLOCK", duration=1, multiplier=1.0, flat_bonus=0))
        if "THORNS" in card.tags or card.name == "Кристаллизация":
            thorns = next((b for b in state.player.buffs if b.tag == "THORNS"), None)
            if thorns:
                thorns.flat_bonus += 3
            else:
                state.player.buffs.append(Buff(tag="THORNS", duration=3, multiplier=1.0, flat_bonus=3))

    if artifacts:
        await on_card_played(state, artifacts, card)

    extra_draw = 0
    extra_discard = 0
    for tag in card.tags:
        if tag.startswith("DRAW_"):
            extra_draw += int(tag.split("_")[1])
        elif tag.startswith("DISCARD_"):
            extra_discard += int(tag.split("_")[1])

    if extra_draw > 0 and not state.finished:
        await draw_cards(state, extra_draw)

    if extra_discard > 0 and len(state.hand) > 0:
        for _ in range(min(extra_discard, len(state.hand))):
            if state.hand:
                state.discard_pile.append(state.hand.pop(0))

    # - \u0413\u043e\u0440\u044c\u043a\u0438\u0439 \u0444\u0438\u043d\u0430\u043b: \u0443\u0440\u043e\u043d = 3 \u0445 BITTER \u0441\u0442\u0430\u043a\u043e\u0432
    if "BITTER_SCALE" in card.tags and state.enemy:
        bitter_stacks = state.combo_stacks.get("BITTER", 0)
        bonus_dmg = bitter_stacks * 3
        if bonus_dmg > 0:
            await apply_damage(state.enemy.fighter, bonus_dmg)

    # - \u041f\u0435\u0440\u0435\u0441\u043e\u043b\u0435\u043d\u043d\u044b\u0439 \u0431\u0443\u043b\u044c\u043e\u043d: Exhaust \u0441\u043b\u0443\u0447\u0430\u0439\u043d\u0443\u044e \u043a\u0430\u0440\u0442\u0443 \u0438\u0437 \u0440\u0443\u043a\u0438
    if "EXHAUST_RANDOM" in card.tags and state.hand:
        victim = random.choice(state.hand)
        state.hand.remove(victim)
        state.exhaust_pile.append(victim)

    # - \u0421\u0430\u0445\u0430\u0440\u043d\u044b\u0439 \u0448\u043e\u043a: +2 \u044d\u043d\u0435\u0440\u0433\u0438\u0438
    if "ENERGY_2" in card.tags:
        state.player.energy = min(state.player.energy + 2, state.player.max_energy + 2)

    # - \u0421\u0430\u0445\u0430\u0440\u043d\u044b\u0439 \u0448\u043e\u043a: \u043d\u0430\u043b\u0438\u0447\u0438\u0435 SELF_VULNERABLE - \u0438\u0433\u0440\u043e\u043a \u043f\u043e\u043b\u0443\u0447\u0430\u0435\u0442 Vulnerable 1 \u0445\u043e\u0434
    if "SELF_VULNERABLE" in card.tags:
        state.player.buffs.append(Buff(tag="VULNERABLE", duration=1, multiplier=1.25, flat_bonus=0))

    # Система Комбо Вкусов - добавляем стаки и проверяем взрыв
    state.last_combo_messages = []
    exploded = await _add_combo_stack(state, card.tags)
    if exploded:
        msg = await _explode_combo(state, exploded)
        if msg:
            state.last_combo_messages.append(msg)
            # Если один вкус взорвался, другие тоже могли достичь порога
            # Проверяем все вкусы еще раз
            for flavor in FLAVOR_TAGS:
                threshold = COMBO_THRESHOLD_WITH_CHARGE if state.combo_charges > 0 else COMBO_THRESHOLD
                if state.combo_stacks[flavor] >= threshold:
                    msg2 = await _explode_combo(state, flavor)
                    if msg2:
                        state.last_combo_messages.append(msg2)

    _sync_primary_enemy(state)
    await check_battle_end(state)
    return card


async def resolve_parry(
    state: BattleState,
    incoming_damage: int,
    enemy_damage_type: str,
) -> ParryResult:
    if state.player.parry_type is None:
        return ParryResult()
    if state.player.parry_type != enemy_damage_type:
        return ParryResult()

    blocked = int(incoming_damage * PARRY_BLOCK_RATIO)
    reflected = blocked

    state.player.parry_type = None
    return ParryResult(triggered=True, blocked=blocked, reflected=reflected)


def _evaluate_condition(state: BattleState, condition: str, enemy_fighter: Fighter | None = None, es: any = None) -> bool:
    ef = enemy_fighter or state.enemy
    if condition == "player_block_gt_10":
        return state.player.block > 10
    if condition == "player_hp_lt_30":
        return state.player.hp < 30
    if condition == "enemy_hp_lt_half":
        return ef.hp < ef.max_hp // 2
    if condition == "player_no_block":
        return state.player.block == 0
    if condition == "self_has_block":
        return ef.block > 0
    if condition == "stolen_gte_9":
        return getattr(es, "stolen_credits", 0) >= 9
    if condition == "gaki_count_lt_2":
        if not state.enemies:
            return False
        gaki_count = sum(1 for e in state.enemies if e.alive and "Гаки" in e.fighter.name)
        return gaki_count < 2
    return False


def _peek_enemy_action_from(
    state: BattleState,
    es: EnemyState,
) -> EnemyAction:
    if not es.ai_pattern:
        return EnemyAction(
            action="attack",
            damage=5,
            damage_type="slashing",
        )
    action = es.ai_pattern[es.ai_index % len(es.ai_pattern)]
    if action.action == "conditional" and action.condition:
        branch = action.if_true if _evaluate_condition(state, action.condition, es.fighter, es) else action.if_false
        if branch:
            return EnemyAction(**branch)
        return EnemyAction(action="attack", damage=5, damage_type="slashing")
    if action.action == "flee" and action.condition:
        if _evaluate_condition(state, action.condition, es.fighter, es):
            return EnemyAction(action="flee")
        return EnemyAction(action="attack", damage=2, damage_type="slashing", steal=3)
    if action.action == "summon_gaki" and action.condition:
        if _evaluate_condition(state, action.condition, es.fighter, es):
            return action
        return EnemyAction(action="block", block=15)
    if action.action == "buff_all_gaki":
        return action
    return action


def _build_intent(action: EnemyAction, turn: int) -> EnemyIntent:
    if action.action == "attack":
        dmg = max(action.damage, 0)
        desc = f"Собирается нанести {dmg} урона"
        if getattr(action, "steal", 0) > 0:
            desc += f" (крадет {action.steal} кредитов)"
        return EnemyIntent(type="attack", value=dmg, description=desc)
    if action.action == "block":
        return EnemyIntent(type="defend", value=action.block, description=f"Собирается защититься (+{action.block} блок)")
    if action.action == "buff":
        return EnemyIntent(type="buff", value=0, description="Собирается усилиться")
    if action.action == "debuff":
        return EnemyIntent(type="debuff", value=0, description="Собирается наложить дебафф")
    if action.action == "flee":
        return EnemyIntent(type="buff", value=0, description="Собирается сбежать!")
    if action.action == "summon_gaki":
        return EnemyIntent(type="buff", value=0, description="Призывает Гаки!")
    if action.action == "buff_all_gaki":
        return EnemyIntent(type="buff", value=0, description="Усиливает Гаки!")
    return EnemyIntent(type="attack", value=0, description="Неизвестное намерение")


async def generate_intents(state: BattleState) -> None:
    for es in state.enemies:
        if not es.alive:
            es.intent = None
            continue
        action = _peek_enemy_action_from(state, es)
        es.intent = _build_intent(action, state.turn)


async def _get_enemy_action_from(
    state: BattleState,
    es: EnemyState,
) -> EnemyAction:
    # Специальная логика для босса Нурарихён на основе intent
    if es.intent and "Нурарихён" in es.fighter.name:
        intent_type = es.intent.type

        if intent_type == "summon":
            # Воскрешение всех мертвых Гаки
            return EnemyAction(
                action="summon_gaki",
                damage=0,
                damage_type="none",
            )

        elif intent_type == "buff":
            # Ярость всем Гаки + блок боссу
            return EnemyAction(
                action="buff_all_gaki",
                buff_tag="RAGE",
                duration=2,
                multiplier=1.25,
                self_block=8,
                damage=0,
                damage_type="none",
            )

    if not es.ai_pattern:
        return EnemyAction(
            action="attack",
            damage=5,
            damage_type="slashing",
        )

    action = es.ai_pattern[es.ai_index % len(es.ai_pattern)]
    es.ai_index += 1

    if action.action == "conditional" and action.condition:
        branch = action.if_true if _evaluate_condition(state, action.condition, es.fighter) else action.if_false
        if branch:
            return EnemyAction(**branch)
        return EnemyAction(action="attack", damage=5, damage_type="slashing")

    return action


async def _get_enemy_action(state: BattleState) -> EnemyAction:
    if not state.ai_pattern:
        return EnemyAction(
            action="attack",
            damage=5,
            damage_type="slashing",
        )

    action = state.ai_pattern[state.ai_index % len(state.ai_pattern)]
    state.ai_index += 1

    if action.action == "conditional" and action.condition:
        branch = action.if_true if _evaluate_condition(state, action.condition) else action.if_false
        if branch:
            return EnemyAction(**branch)
        return EnemyAction(action="attack", damage=5, damage_type="slashing")

    return action


async def _do_enemy_action(
    state: BattleState,
    action: EnemyAction,
    enemy_fighter: Fighter,
    artifacts: list[ArtifactInstance] | None = None,
    es: any = None,
) -> int:
    dealt = 0

    if action.action == "attack":
        damage = max(action.damage, 0)
        dtype = action.damage_type

        parry = await resolve_parry(state, damage, dtype)
        if parry.triggered:
            damage -= parry.blocked
            await apply_damage(enemy_fighter, parry.reflected)

        if artifacts:
            dealt = await apply_damage_with_artifacts(state, damage, artifacts)
        else:
            dealt = await apply_damage(state.player, damage)

        if getattr(action, "steal", 0) > 0 and es:
            es.stolen_credits = getattr(es, "stolen_credits", 0) + action.steal

        if getattr(action, "apply_debuff", None):
            state.player.buffs.append(
                Buff(tag=action.apply_debuff, duration=getattr(action, "debuff_duration", 2), flat_bonus=0)
            )

    elif action.action == "block":
        enemy_fighter.block += action.block

    elif action.action == "buff":
        if action.buff_tag:
            existing = next((b for b in enemy_fighter.buffs if b.tag == action.buff_tag), None)
            if existing:
                existing.duration += action.duration
            else:
                enemy_fighter.buffs.append(
                    Buff(tag=action.buff_tag, duration=action.duration, multiplier=action.multiplier)
                )

    elif action.action == "debuff":
        if action.debuff_tag:
            state.player.buffs.append(
                Buff(tag=action.debuff_tag, duration=action.duration, flat_bonus=action.flat_damage)
            )

    elif action.action == "flee":
        es.alive = False
        es.fighter.hp = 0

    elif action.action == "summon_gaki":
        if state.enemies:
            for e in state.enemies:
                if not e.alive and "Гаки" in e.fighter.name:
                    e.alive = True
                    e.fighter.hp = 25
                    e.fighter.max_hp = 25
                    break

    elif action.action == "buff_all_gaki":
        if state.enemies:
            for e in state.enemies:
                if e.alive and "Гаки" in e.fighter.name:
                    existing = next((b for b in e.fighter.buffs if b.tag == action.buff_tag), None)
                    if existing:
                        existing.duration += action.duration
                    else:
                        e.fighter.buffs.append(
                            Buff(tag=action.buff_tag, duration=action.duration, multiplier=action.multiplier)
                        )
        enemy_fighter.block += getattr(action, "self_block", 0)

    elif action.action == "debuff_self":
        if action.debuff_tag == "FEAR":
            es.skip_next_turn = True

    return dealt


async def enemy_turn(
    state: BattleState,
    enemy_damage_type: str | None = None,
    artifacts: list[ArtifactInstance] | None = None,
) -> int:
    total_dealt = 0

    if state.enemies:
        for es in state.enemies:
            if not es.alive:
                continue
            if getattr(es, "skip_next_turn", False):
                es.skip_next_turn = False
                continue
            action = await _get_enemy_action_from(state, es)
            dealt = await _do_enemy_action(state, action, es.fighter, artifacts, es)
            total_dealt += dealt
            await tick_buffs(es.fighter)
            if state.player.hp <= 0:
                break
    else:
        action = await _get_enemy_action(state)
        total_dealt = await _do_enemy_action(state, action, state.enemy, artifacts)
        await tick_buffs(state.enemy)

    _sync_primary_enemy(state)
    await check_battle_end(state)
    return total_dealt


async def start_turn(state: BattleState) -> None:
    state.turn += 1
    state.phase = "player_turn"
    state.player.energy = state.player.max_energy

    salty_buff = next((b for b in state.player.buffs if b.tag == "SALTY_BUFF"), None)
    retain = next((b for b in state.player.buffs if b.tag == "RETAIN_BLOCK"), None)
    if not salty_buff and not retain:
        state.player.block = 0
    elif salty_buff:
        salty_buff.duration -= 1

    for buff in state.player.buffs:
        if buff.tag == "COMBO_REGEN":
            state.player.hp = min(state.player.hp + buff.flat_bonus, state.player.max_hp)
        elif buff.tag == "COMBO_THORNS":
            state.player.block += buff.flat_bonus

    await draw_cards(state)

    for card in state.hand[:]:
        if "RETAIN" in card.tags:
            state.retained_cards.append(card)
            state.hand.remove(card)

    if state.enemies:
        update_enemy_intents(state)


async def end_turn(
    state: BattleState,
    artifacts: list[ArtifactInstance] | None = None,
) -> int:
    await tick_buffs(state.player)
    await discard_hand(state)

    state.phase = "enemy_turn"
    dealt = await enemy_turn(state, artifacts=artifacts)

    if not state.finished:
        await start_turn(state)

    return dealt
