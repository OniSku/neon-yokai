import json

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.security import validate_init_data
from app.models.user import User


async def get_current_user(
    x_init_data: str = Header(..., alias="X-Init-Data"),
    session: AsyncSession = Depends(get_session),
) -> User:
    validated = validate_init_data(x_init_data, settings.BOT_TOKEN)

    user_data_raw = validated.get("user")
    if not user_data_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No user payload in initData",
        )

    tg_user = json.loads(user_data_raw)
    telegram_id: int = tg_user["id"]
    username: str | None = tg_user.get("username")

    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    elif user.username != username:
        user.username = username
        await session.commit()
        await session.refresh(user)

    return user
