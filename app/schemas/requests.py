from pydantic import BaseModel, Field


class RunStartRequest(BaseModel):
    enemy_id: int | None = None
    enemy_name: str = "Street Thug"
    enemy_hp: int = 50


class RunActionRequest(BaseModel):
    action: str
    hand_index: int | None = None
    target_index: int | None = None


class ClaimRewardRequest(BaseModel):
    chosen_card_id: int | None = None


class NextNodeRequest(BaseModel):
    chosen_node_index: int


class EventChoiceRequest(BaseModel):
    choice_id: str


class UpgradeRequest(BaseModel):
    branch: str


class CookRequest(BaseModel):
    ingredient_ids: list[int] = Field(..., min_length=1, max_length=5)
