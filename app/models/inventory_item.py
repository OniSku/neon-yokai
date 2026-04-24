from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("user_id", "ingredient_id", name="uq_user_ingredient"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ingredient_id: Mapped[int] = mapped_column(Integer, ForeignKey("ingredients.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
