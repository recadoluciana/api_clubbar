#asaas_webhook.py
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
    body = await request.json()

    print("[ASAAS WEBHOOK]")
    print(body)

    return {"ok": True}