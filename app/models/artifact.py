from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    rarity: Mapped[str] = mapped_column(String(32), default="common", server_default="common")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(String(64), nullable=False)
    charges: Mapped[int] = mapped_column(Integer, default=-1, server_default="-1")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    broken_into: Mapped[str | None] = mapped_column(String(128), nullable=True)
