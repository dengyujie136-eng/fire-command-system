# [Scene-Cache-Integration] 注册表幂等写入服务
from __future__ import annotations

from typing import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.registry import PersonnelRegistry, ResourceRegistry, UAVRegistry


class DBService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def clear_registries(self) -> None:
        await self.db.execute(delete(UAVRegistry))
        await self.db.execute(delete(ResourceRegistry))
        await self.db.execute(delete(PersonnelRegistry))
        await self.db.commit()

    async def _upsert_rows(self, model, rows: Sequence[dict], key_fields: Iterable[str]):
        created = False
        updated = False
        for row in rows:
            clause = None
            for field in key_fields:
                cond = getattr(model, field) == row[field]
                clause = cond if clause is None else clause & cond
            result = await self.db.execute(select(model).where(clause))
            existing = result.scalars().first()
            if existing is None:
                self.db.add(model(**row))
                created = True
            else:
                for k, v in row.items():
                    setattr(existing, k, v)
                updated = True
        await self.db.commit()
        return created, updated

    async def upsert_uav(self, rows: Sequence[dict]):
        return await self._upsert_rows(UAVRegistry, rows, ["id"])

    async def upsert_resource(self, rows: Sequence[dict]):
        return await self._upsert_rows(ResourceRegistry, rows, ["id"])

    async def upsert_personnel(self, rows: Sequence[dict]):
        return await self._upsert_rows(PersonnelRegistry, rows, ["id"])

    async def upsert_by_composite_key(self, model, rows: Sequence[dict], key_fields: Iterable[str]) -> int:
        count = 0
        for row in rows:
            criteria = {field: row.get(field) for field in key_fields}
            stmt = None
            for field, value in criteria.items():
                clause = getattr(model, field) == value
                stmt = clause if stmt is None else stmt & clause
            result = await self.db.execute(select(model).where(stmt))
            existing = result.scalars().first()
            if existing is None:
                self.db.add(model(**row))
            else:
                for k, v in row.items():
                    setattr(existing, k, v)
            count += 1
        await self.db.commit()
        return count
