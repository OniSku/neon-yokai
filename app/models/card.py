from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    cost: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    power: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    damage_type: Mapped[str] = mapped_column(String(32), default="none", server_default="none")
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_exhaust: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_starting: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    rarity: Mapped[str] = mapped_column(String(32), default="common", server_default="common")
