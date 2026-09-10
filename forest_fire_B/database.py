# database.py
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, JSON

# 1. 数据库 URL
# sqlite+aiosqlite:///./forest_fire.db 表示在当前目录下创建名为 forest_fire.db 的文件
DATABASE_URL = "sqlite+aiosqlite:///./forest_fire.db"

# 2. 创建引擎
engine = create_async_engine(DATABASE_URL, echo=False) # echo=True 可以打印 SQL 语句用于调试

# 3. 创建会话工厂
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# 4. 基类
Base = declarative_base()

# 5. 定义用户模型 (对应数据库中的 users 表)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(String, unique=True, index=True, nullable=False)
    scene_id = Column(String, index=True, nullable=False)
    owner = Column(String, nullable=False, default="system")
    status = Column(String, nullable=False, default="pending")
    params = Column(JSON, nullable=True)
    wind_params = Column(JSON, nullable=True)
    current_fire_geojson = Column(JSON, nullable=True)
    current_step = Column(Integer, nullable=False, default=0)
    last_update = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

# 6. 依赖项：获取数据库会话
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()