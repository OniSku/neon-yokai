from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, select, text

from app.api.cart import router as cart_router
from app.api.craft import router as craft_router
from app.api.run import router as run_router
from app.api.shop import router as shop_router
from app.api.user import router as user_router
from app.core.config import settings
from app.core.database import Base, async_session_factory, engine, sync_database_schema

import app.models  # noqa: F401  ensure all models are registered


async def _migrate_schema() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'ingredients' AND column_name = 'salty'
        """))
        has_salty = result.fetchone() is not None

        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'user_deck_cards' AND column_name = 'is_upgraded'
        """))
        has_is_upgraded = result.fetchone() is not None

        if not has_salty:
            print("[migrate] Missing 'salty' in ingredients, dropping table...")
            await conn.execute(text("DROP TABLE IF EXISTS ingredients CASCADE"))

        if not has_is_upgraded:
            print("[migrate] Missing 'is_upgraded' in user_deck_cards, dropping table...")
            await conn.execute(text("DROP TABLE IF EXISTS user_deck_cards CASCADE"))

        if not has_salty or not has_is_upgraded:
            print("[migrate] Recreating tables...")
            await conn.run_sync(Base.metadata.create_all)


async def _auto_seed() -> None:
    from app.models.artifact import Artifact
    from app.models.card import Card
    from app.models.enemy import Enemy
    from app.models.ingredient import Ingredient
    from app.models.shop_item import ShopItem
    from seed import ARTIFACTS, CARDS, ENEMIES, INGREDIENTS, SHOP_ITEMS

    async with async_session_factory() as session:
        updated: list[str] = []

        # Cards - insert or update
        for card_data in CARDS:
            result = await session.execute(
                select(Card).where(Card.name == card_data["name"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(Card(**card_data))
            else:
                for key, value in card_data.items():
                    setattr(existing, key, value)
        updated.append("cards")

        # Enemies - полная очистка перед сидированием (удаляем призрачных врагов)
        await session.execute(delete(Enemy))
        await session.flush()

        # Enemies - insert or update
        for enemy_data in ENEMIES:
            result = await session.execute(
                select(Enemy).where(Enemy.name == enemy_data["name"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(Enemy(**enemy_data))
            else:
                for key, value in enemy_data.items():
                    setattr(existing, key, value)
        updated.append("enemies")

        # Ingredients - insert or update
        for ing_data in INGREDIENTS:
            result = await session.execute(
                select(Ingredient).where(Ingredient.name == ing_data["name"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(Ingredient(**ing_data))
            else:
                for key, value in ing_data.items():
                    setattr(existing, key, value)
        updated.append("ingredients")

        # Shop items - insert or update
        for shop_data in SHOP_ITEMS:
            result = await session.execute(
                select(ShopItem).where(ShopItem.name == shop_data["name"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(ShopItem(**shop_data))
            else:
                for key, value in shop_data.items():
                    setattr(existing, key, value)
        updated.append("shop_items")

        # Artifacts - insert or update
        for art_data in ARTIFACTS:
            result = await session.execute(
                select(Artifact).where(Artifact.name == art_data["name"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(Artifact(**art_data))
            else:
                for key, value in art_data.items():
                    setattr(existing, key, value)
        updated.append("artifacts")

        await session.commit()
        print(f"[auto-seed] Updated: {', '.join(updated)}")


@asynccontextmanager
async def lifespan(application: FastAPI):
    await sync_database_schema()
    await _migrate_schema()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _auto_seed()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(user_router)
app.include_router(run_router)
app.include_router(craft_router)
app.include_router(shop_router)
app.include_router(cart_router)

_static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir), html=True), name="static")
