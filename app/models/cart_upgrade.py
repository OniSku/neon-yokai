from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CartUpgrade(Base):
    """Мета-прогрессия тележки повара (улучшения в хабе).

    Разделена от забега - это постоянные улучшения за XP.
    """

    __tablename__ = "cart_upgrades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Уровни улучшений (0-5)
    kitchen_level: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    fridge_level: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ads_level: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Связь
    user: Mapped["User"] = relationship(back_populates="cart_upgrade")

    def get_max_hp_bonus(self) -> int:
        """+5 к макс HP за каждый уровень кухни."""
        return self.kitchen_level * 5

    def get_ingredient_slots_bonus(self) -> int:
        """+1 слот ингредиента за каждый уровень холодильника."""
        return self.fridge_level

    def get_shop_discount_percent(self) -> int:
        """-5% цены за каждый уровень рекламы."""
        return self.ads_level * 5
