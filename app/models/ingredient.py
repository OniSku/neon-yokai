from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    spicy: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sour: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sweet: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    bitter: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    salty: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rarity: Mapped[str] = mapped_column(String(32), default="common", server_default="common")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
