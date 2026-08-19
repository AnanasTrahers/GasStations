from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.schema import MetaData

from src.config import project_settings

metadata = MetaData(schema="app")


class Base(DeclarativeBase):
    metadata: MetaData = metadata


engine = create_async_engine(
    project_settings.DATABASE_URL,
    echo=project_settings.DB_ECHO,
    pool_recycle=1800,
    connect_args={
        "server_settings": {"search_path": "app, public, topology"}
    }
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
