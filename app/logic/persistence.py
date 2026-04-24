from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game_state import GameState
from app.schemas.battle import BattleState, RunState


async def save_battle_state(
    session: AsyncSession,
    state: BattleState,
) -> GameState:
    result = await session.execute(
        select(GameState).where(GameState.user_id == state.user_id)
    )
    row = result.scalar_one_or_none()

    json_data = state.model_dump_json()

    if row is None:
        row = GameState(user_id=state.user_id, current_run_data_json=json_data)
        session.add(row)
    else:
        row.current_run_data_json = json_data

    await session.commit()
    await session.refresh(row)
    return row


async def load_battle_state(
    session: AsyncSession,
    user_id: int,
) -> BattleState | None:
    result = await session.execute(
        select(GameState).where(GameState.user_id == user_id)
    )
    row = result.scalar_one_or_none()

    if row is None or row.current_run_data_json is None:
        return None

    return BattleState.model_validate_json(row.current_run_data_json)


async def delete_battle_state(
    session: AsyncSession,
    user_id: int,
) -> None:
    result = await session.execute(
        select(GameState).where(GameState.user_id == user_id)
    )
    row = result.scalar_one_or_none()

    if row is not None:
        await session.delete(row)
        await session.commit()


async def save_run_state(
    session: AsyncSession,
    run: RunState,
) -> GameState:
    result = await session.execute(
        select(GameState).where(GameState.user_id == run.user_id)
    )
    row = result.scalar_one_or_none()

    json_data = run.model_dump_json()

    if row is None:
        row = GameState(user_id=run.user_id, current_run_data_json=json_data)
        session.add(row)
    else:
        row.current_run_data_json = json_data

    await session.commit()
    await session.refresh(row)
    return row


async def load_run_state(
    session: AsyncSession,
    user_id: int,
) -> RunState | None:
    result = await session.execute(
        select(GameState).where(GameState.user_id == user_id)
    )
    row = result.scalar_one_or_none()

    if row is None or row.current_run_data_json is None:
        return None

    return RunState.model_validate_json(row.current_run_data_json)


async def delete_run_state(
    session: AsyncSession,
    user_id: int,
) -> None:
    result = await session.execute(
        select(GameState).where(GameState.user_id == user_id)
    )
    row = result.scalar_one_or_none()

    if row is not None:
        await session.delete(row)
        await session.commit()
