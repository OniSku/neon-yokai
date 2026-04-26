from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.cart_upgrade import CartUpgrade


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    experience: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    credits: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    debt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    debt_level: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    meta_progress: Mapped[str | None] = mapped_column(Text, nullable=True)
    slime: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cores: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Связи
    cart_upgrade: Mapped["CartUpgrade"] = relationship(back_populates="user")
