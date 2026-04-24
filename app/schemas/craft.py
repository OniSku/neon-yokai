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
