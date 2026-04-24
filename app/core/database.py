from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


async def sync_database_schema() -> None:
    """Синхронизация схемы БД с моделями SQLAlchemy."""
    async with engine.connect() as conn:
        # Получаем список таблиц в БД
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ))
        existing_tables = {row[0] for row in result.fetchall()}

        for table_name, table_obj in Base.metadata.tables.items():
            if table_name not in existing_tables:
                # Таблицы нет - она будет создана через create_all
                continue

            # Получаем существующие колонки
            result = await conn.execute(text(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
            """))
            existing_cols = {row[0] for row in result.fetchall()}

            # Добавляем недостающие колонки
            for col_name, column in table_obj.columns.items():
                if col_name not in existing_cols:
                    col_type = column.type
                    # Для PostgreSQL нужно правильное имя типа
                    type_str = str(col_type)
                    if "VARCHAR" in type_str:
                        type_str = f"VARCHAR({col_type.length})" if col_type.length else "VARCHAR"
                    elif "BOOLEAN" in type_str:
                        type_str = "BOOLEAN"
                    elif "INTEGER" in type_str:
                        type_str = "INTEGER"
                    elif "TEXT" in type_str:
                        type_str = "TEXT"

                    nullable = "NULL" if column.nullable else "NOT NULL"
                    default = ""
                    if column.default and hasattr(column.default, 'arg'):
                        default_arg = column.default.arg
                        if isinstance(default_arg, str):
                            default = f" DEFAULT '{default_arg}'"
                        elif isinstance(default_arg, bool):
                            default = f" DEFAULT {str(default_arg).lower()}"
                        elif isinstance(default_arg, int):
                            default = f" DEFAULT {default_arg}"

                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {type_str} {nullable}{default}"
                    print(f"[db-sync] Adding column: {table_name}.{col_name}")
                    await conn.execute(text(alter_sql))

        await conn.commit()
    print("[db-sync] Schema synchronization completed.")
