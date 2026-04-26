from pydantic import BaseModel, Field


class FlavorProfile(BaseModel):
    spicy: int = 0
    sour: int = 0
    sweet: int = 0
    bitter: int = 0
    salty: int = 0


class CraftResult(BaseModel):
    profile: FlavorProfile
    buffs: list[str] = Field(default_factory=list)
    dominant_flavor: str | None = None
    combo_effects: list[str] = Field(default_factory=list)
    synthetic_debuff: str | None = None  # - \u0442\u0435\u0433 \u0434\u0435\u0431\u0430\u0444\u0444\u0430 \u0435\u0441\u043b\u0438 \u0432 \u0440\u0435\u0446\u0435\u043f\u0442\u0435 \u0435\u0441\u0442\u044c \u0441\u0438\u043d\u0442\u0435\u0442\u0438\u043a\u0430
