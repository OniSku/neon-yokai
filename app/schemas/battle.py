from pydantic import BaseModel, Field


class CardInstance(BaseModel):
    card_id: int
    name: str
    cost: int = 0
    type: str = "attack"
    power: int = 0
    damage_type: str = "none"
    tags: list[str] = Field(default_factory=list)
    is_exhaust: bool = False
    rarity: str = "common"
    is_upgraded: bool = False


class Buff(BaseModel):
    tag: str
    duration: int = 1
    multiplier: float = 1.0
    flat_bonus: int = 0


class ParryResult(BaseModel):
    triggered: bool = False
    blocked: int = 0
    reflected: int = 0


class Fighter(BaseModel):
    name: str = "Player"
    hp: int = 80
    max_hp: int = 80
    block: int = 0
    energy: int = 3
    max_energy: int = 3
    buffs: list[Buff] = Field(default_factory=list)
    parry_type: str | None = None


class EnemyAction(BaseModel):
    action: str = "attack"
    damage: int = 0
    damage_type: str = "slashing"
    block: int = 0
    buff_tag: str | None = None
    debuff_tag: str | None = None
    duration: int = 0
    multiplier: float = 1.0
    flat_damage: int = 0
    condition: str | None = None
    if_true: dict | None = None
    if_false: dict | None = None


class EnemyIntent(BaseModel):
    type: str = "attack"
    value: int = 0
    description: str = ""


class EnemyState(BaseModel):
    fighter: Fighter = Field(default_factory=lambda: Fighter(name="Enemy", hp=50, max_hp=50))
    ai_pattern: list[EnemyAction] = Field(default_factory=list)
    ai_index: int = 0
    alive: bool = True
    intent: EnemyIntent | None = None


class BattleState(BaseModel):
    user_id: int
    turn: int = 0
    phase: str = "player_turn"

    player: Fighter = Field(default_factory=Fighter)
    enemy: Fighter = Field(default_factory=lambda: Fighter(name="Enemy", hp=50, max_hp=50))
    enemies: list[EnemyState] = Field(default_factory=list)
    target_index: int = 0

    draw_pile: list[CardInstance] = Field(default_factory=list)
    hand: list[CardInstance] = Field(default_factory=list)
    discard_pile: list[CardInstance] = Field(default_factory=list)
    exhaust_pile: list[CardInstance] = Field(default_factory=list)
    retained_cards: list[CardInstance] = Field(default_factory=list)

    ai_pattern: list[EnemyAction] = Field(default_factory=list)
    ai_index: int = 0

    hand_size: int = 5
    finished: bool = False
    winner: str | None = None

    # Система Комбо Вкусов (5 flavors)
    combo_stacks: dict[str, int] = Field(default_factory=lambda: {
        "HOT": 0, "SOUR": 0, "SWEET": 0, "BITTER": 0, "SALTY": 0
    })
    combo_charges: int = 0  # Заряды от готовки (снижают порог с 4 до 3)
    last_combo_messages: list[str] = Field(default_factory=list)  # Сообщения последнего хода


class EnemySlot(BaseModel):
    enemy_id: int | None = None
    name: str = "Unknown"
    hp: int = 50
    max_hp: int = 50


class MapNode(BaseModel):
    index: int
    floor: int = 0
    lane: int = 0
    node_type: str = "combat"
    enemy_id: int | None = None
    enemy_name: str = "Unknown"
    enemy_hp: int = 50
    enemies: list[EnemySlot] = Field(default_factory=list)
    next_nodes: list[int] = Field(default_factory=list)
    is_ambush: bool = False
    completed: bool = False
    event_id: str | None = None


class ComboEffect(BaseModel):
    name: str
    flavor: str
    description: str
    buff: Buff


class EventChoice(BaseModel):
    choice_id: str
    label: str
    description: str
    cost_type: str = "none"
    cost_value: int = 0


class EventScenario(BaseModel):
    event_id: str
    title: str
    description: str
    choices: list[EventChoice] = Field(default_factory=list)


class ArtifactInstance(BaseModel):
    artifact_id: int
    name: str
    rarity: str = "common"
    description: str = ""
    trigger: str = "passive"
    charges: int = -1
    is_active: bool = True
    stacks_used: int = 0  # - \u0443\u043d\u0438\u0432\u0435\u0440\u0441\u0430\u043b\u044c\u043d\u044b\u0439 \u0441\u0447\u0451\u0442\u0447\u0438\u043a (\u0434\u043b\u044f \u0430\u0440\u0442\u0435\u0444\u0430\u043a\u0442\u043e\u0432 \u0442\u0438\u043f\u0430 \u0437\u0430\u0442\u043e\u0447\u043a\u0430 \u0438\u0437 \u0430\u0440\u043c\u0430\u0442\u0443\u0440\u044b)


class RewardCard(BaseModel):
    card_id: int
    name: str
    cost: int = 0
    type: str = "attack"
    power: int = 0
    damage_type: str = "none"
    tags: list[str] = Field(default_factory=list)
    is_exhaust: bool = False
    rarity: str = "common"


class PendingRewards(BaseModel):
    credits: int = 0
    experience: int = 0
    loot: list[dict] = Field(default_factory=list)
    card_choices: list[RewardCard] = Field(default_factory=list)
    artifact_reward: ArtifactInstance | None = None


class RunState(BaseModel):
    user_id: int
    map_nodes: list[MapNode] = Field(default_factory=list)
    current_node_index: int = 0
    current_hp: int = 80
    combo_effects: list[ComboEffect] = Field(default_factory=list)
    artifacts: list[ArtifactInstance] = Field(default_factory=list)
    active_event: EventScenario | None = None
    battle: BattleState | None = None
    reward_phase: bool = False
    pending_rewards: PendingRewards | None = None
    run_finished: bool = False
    card_removals_this_run: int = 0
    rest_choice_pending: bool = False
    user_credits: int = 0
    seen_event_ids: list[str] = Field(default_factory=list)
    run_ingredients: list[dict] = Field(default_factory=list)
