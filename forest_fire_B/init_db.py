# init_db.py
import asyncio
from database import engine, Base

async def init_models():
    async with engine.begin() as conn:
        # 创建所有继承自 Base 的表
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(init_models())
    print("✅ SQLite 数据库表已创建/更新 (forest_fire.db)")