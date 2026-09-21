from fastapi import APIRouter

from app.services.rule_base_service import load_rule_base_summary

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("/fire-emergency")
async def fire_emergency_rules() -> dict:
    return {"ok": True, "data": load_rule_base_summary()}