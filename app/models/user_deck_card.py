from sqlalchemy import Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserDeckCard(Base):
    __tablename__ = "user_deck_cards"
    __table_args__ = (UniqueConstraint("user_id", "card_id", name="uq_user_card"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    card_id: Mapped[int] = mapped_column(Integer, ForeignKey("cards.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_upgraded: Mapped[bool] = mapped_column(default=False, server_default="0")
