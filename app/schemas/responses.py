from pydantic import BaseModel, Field

from app.schemas.battle import (
    ArtifactInstance,
    BattleState,
    EventScenario,
    MapNode,
    PendingRewards,
    RewardCard,
    RunState,
)
from app.schemas.craft import CraftResult


class BranchInfo(BaseModel):
    name: str
    description: str
    level: int = 0
    max_level: int = 5
    next_cost: int | None = None


class MetaProgress(BaseModel):
    kitchen: BranchInfo
    fridge: BranchInfo
    ads: BranchInfo


class UserProfileResponse(BaseModel):
    id: int
    telegram_id: int
    username: str | None = None
    experience: int = 0
    credits: int = 0
    debt: int = 0
    debt_level: int = 0
    debt_level_name: str = "Чисто"
    inventory_limit: int = 5
    meta: MetaProgress | None = None


class InventoryItemOut(BaseModel):
    ingredient_id: int
    ingredient_name: str
    quantity: int


class DeckCardOut(BaseModel):
    card_id: int
    name: str
    cost: int
    type: str
    power: int
    damage_type: str
    tags: list[str] = Field(default_factory=list)
    is_exhaust: bool = False
    is_upgraded: bool = False
    quantity: int = 1


class LootItem(BaseModel):
    ingredient_id: int
    name: str
    quantity: int


class RunStartResponse(BaseModel):
    message: str = "Забег начался"
    run: RunState


class RunActionResponse(BaseModel):
    message: str
    card_played: str | None = None
    enemy_damage: int | None = None
    loot: list[LootItem] = Field(default_factory=list)
    credits_earned: int = 0
    run: RunState


class NextNodeResponse(BaseModel):
    message: str
    node: MapNode
    run: RunState


class RewardResponse(BaseModel):
    credits: int = 0
    experience: int = 0
    loot: list[LootItem] = Field(default_factory=list)
    card_choices: list[RewardCard] = Field(default_factory=list)
    artifact_reward: ArtifactInstance | None = None


class ClaimRewardResponse(BaseModel):
    message: str
    credits: int = 0
    run: RunState


class EventResponse(BaseModel):
    event: EventScenario


class EventChoiceResponse(BaseModel):
    message: str
    hp_delta: int = 0
    credits_delta: int = 0
    card_reward: RewardCard | None = None
    artifact_reward: ArtifactInstance | None = None
    run: RunState


class UpgradeResponse(BaseModel):
    success: bool
    message: str
    experience: int = 0
    meta: MetaProgress | None = None


class CookResponse(BaseModel):
    message: str = "Блюдо готово"
    result: CraftResult
