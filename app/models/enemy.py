from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Enemy(Base):
    __tablename__ = "enemies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    hp: Mapped[int] = mapped_column(Integer, default=50, server_default="50")
    base_damage: Mapped[int] = mapped_column(Integer, default=8, server_default="8")
    damage_type: Mapped[str] = mapped_column(String(32), default="slashing", server_default="slashing")
    ai_pattern: Mapped[str] = mapped_column(Text, nullable=False)
