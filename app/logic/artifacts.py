from __future__ import annotations

from app.schemas.battle import ArtifactInstance, BattleState, CardInstance


def _use_charge(art: ArtifactInstance) -> bool:
    if art.charges == -1:
        return True
    art.charges -= 1
    if art.charges <= 0:
        art.is_active = False
    return True


async def on_combat_start(
    state: BattleState,
    artifacts: list[ArtifactInstance],
) -> list[str]:
    log: list[str] = []
    for art in artifacts:
        if not art.is_active:
            continue

        if art.name == "Энергетик":
            state.player.max_energy += 1
            state.player.energy += 1
            _use_charge(art)
            log.append(f"[{art.name}] +1 energy")

        elif art.name == "Острый соус":
            state.player.buffs.append(
                _make_buff("HOT_SAUCE", duration=99, flat_bonus=2)
            )
            _use_charge(art)
            log.append(f"[{art.name}] +2 flat damage")

        elif art.name == "Бронежилет шефа":
            state.player.block += 5
            _use_charge(art)
            log.append(f"[{art.name}] +5 block")

        elif art.name == "Свинья-копилка":
            log.append(f"[{art.name}] active (breaks on rest for +50 cr)")

        elif art.name == "Банка старого маринада":
            # - Все враги получают 1 стак SOUR игрока (стаки накапливаются на BattleState)
            state.combo_stacks["SOUR"] = state.combo_stacks.get("SOUR", 0) + 1
            _use_charge(art)
            log.append(f"[{art.name}] +1 SOUR stack at combat start")

        elif art.name == "Утяжеленный вок":
            # - Игроку +2 стака SALTY
            state.combo_stacks["SALTY"] = state.combo_stacks.get("SALTY", 0) + 2
            _use_charge(art)
            log.append(f"[{art.name}] player +2 SALTY stacks")

    _cleanup(artifacts)
    return log


async def on_card_played(
    state: BattleState,
    artifacts: list[ArtifactInstance],
    card: CardInstance,
) -> list[str]:
    log: list[str] = []
    for art in artifacts:
        if not art.is_active:
            continue

        if art.name == "Магнитная доска":
            if card.is_exhaust and art.charges != 0:
                state.hand.append(card)
                if card in state.exhaust_pile:
                    state.exhaust_pile.remove(card)
                _use_charge(art)
                log.append(f"[{art.name}] returned {card.name} to hand")

        elif art.name == "Точильный камень":
            if card.type == "attack":
                state.player.block += 1
                _use_charge(art)
                log.append(f"[{art.name}] +1 block after attack")

    _cleanup(artifacts)
    return log


async def on_damage_taken(
    state: BattleState,
    artifacts: list[ArtifactInstance],
    damage: int,
) -> tuple[int, list[str]]:
    log: list[str] = []
    final_damage = damage
    for art in artifacts:
        if not art.is_active:
            continue

        if art.name == "Дефибриллятор":
            if state.player.hp - final_damage <= 0:
                state.player.hp = 1
                final_damage = 0
                _use_charge(art)
                log.append(f"[{art.name}] prevented death! HP set to 1")

        elif art.name == "Шипованный фартук":
            state.enemy.hp = max(state.enemy.hp - 3, 0)
            _use_charge(art)
            log.append(f"[{art.name}] reflected 3 damage to enemy")

    _cleanup(artifacts)
    return final_damage, log


async def on_rest(
    artifacts: list[ArtifactInstance],
) -> tuple[int, list[str]]:
    bonus_credits = 0
    log: list[str] = []
    for art in artifacts:
        if not art.is_active:
            continue

        if art.name == "Свинья-копилка":
            bonus_credits += 50
            art.is_active = False
            art.name = "Разбитая копилка"
            art.description = "Пусто. Была свиньей-копилкой."
            log.append("[Свинья-копилка] broken! +50 credits")

        elif art.name == "Заначка шефа":
            # - Дополнительные 10% HP отдаётся как +bonus_credits=0 + через heal_bonus
            bonus_credits += 0  # - заглушка: логика допхила в run.py по тегу "Заначка шефа"
            _use_charge(art)
            log.append("[Заначка шефа] rest heal +10%")

    _cleanup(artifacts)
    return bonus_credits, log


def _make_buff(tag: str, duration: int = 1, multiplier: float = 1.0, flat_bonus: int = 0):
    from app.schemas.battle import Buff
    return Buff(tag=tag, duration=duration, multiplier=multiplier, flat_bonus=flat_bonus)


def _cleanup(artifacts: list[ArtifactInstance]) -> None:
    i = 0
    while i < len(artifacts):
        if not artifacts[i].is_active and artifacts[i].charges == 0:
            artifacts.pop(i)
        else:
            i += 1
