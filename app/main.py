from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from app.api.craft import router as craft_router
from app.api.run import router as run_router
from app.api.shop import router as shop_router
from app.api.user import router as user_router
from app.core.config import settings
from app.core.database import Base, async_session_factory, engine

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
        seeded: list[str] = []

        has_cards = (await session.execute(select(Card).limit(1))).scalar_one_or_none()
        if has_cards is None:
            for card_data in CARDS:
                session.add(Card(**card_data))
            seeded.append("cards")

        has_enemies = (await session.execute(select(Enemy).limit(1))).scalar_one_or_none()
        if has_enemies is None:
            for enemy_data in ENEMIES:
                session.add(Enemy(**enemy_data))
            seeded.append("enemies")

        has_ingredients = (await session.execute(select(Ingredient).limit(1))).scalar_one_or_none()
        if has_ingredients is None:
            for ing_data in INGREDIENTS:
                session.add(Ingredient(**ing_data))
            seeded.append("ingredients")

        has_shop = (await session.execute(select(ShopItem).limit(1))).scalar_one_or_none()
        if has_shop is None:
            for shop_data in SHOP_ITEMS:
                session.add(ShopItem(**shop_data))
            seeded.append("shop_items")

        has_artifacts = (await session.execute(select(Artifact).limit(1))).scalar_one_or_none()
        if has_artifacts is None:
            for art_data in ARTIFACTS:
                session.add(Artifact(**art_data))
            seeded.append("artifacts")

        if seeded:
            await session.commit()
            print(f"[auto-seed] Seeded: {', '.join(seeded)}")
        else:
            print("[auto-seed] All tables already populated, skipping.")


@asynccontextmanager
async def lifespan(application: FastAPI):
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

_static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir), html=True), name="static")
