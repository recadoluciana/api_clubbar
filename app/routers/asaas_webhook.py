from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(
    prefix="/asaas",
    tags=["Asaas"],
)


@router.post("/webhook")
async def asaas_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        body = await request.json()
    except Exception:
        body = {}

    print("[ASAAS WEBHOOK]")
    print(body)

    return {"ok": True}