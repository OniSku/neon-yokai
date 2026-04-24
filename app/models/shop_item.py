from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ShopItem(Base):
    __tablename__ = "shop_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    category: Mapped[str] = mapped_column(String(32), default="card", server_default="card")
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
