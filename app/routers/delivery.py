from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from app.db import fetchone, execute
from app.security import sha256_text
from app.main import get_current_user

router = APIRouter(prefix="/garcom", tags=["garcom"])

class ScanIn(BaseModel):
    qr_token: str

@router.post("/itens/scan")
def scan_item(data: ScanIn, user=Depends(get_current_user)):
    # no default: mesmo app. você pode liberar "role=garcom" depois.
    # por enquanto, só bloqueia se quiser:
    # if user["role"] != "garcom": raise HTTPException(403, "Sem permissão")

    token_hash = sha256_text(data.qr_token)

    item = fetchone("""
      SELECT iv.id, iv.status, iv.venda_id, v.status AS venda_status
      FROM itens_venda iv
      JOIN vendas v ON v.id = iv.venda_id
      WHERE iv.qr_token_hash=%s
      LIMIT 1
    """, (token_hash,))

    if not item:
        raise HTTPException(404, "QR inválido")

    if item["venda_status"] != "paga":
        raise HTTPException(400, "Venda não está paga")

    if item["status"] == "entregue":
        return {"ok": True, "status": "entregue"}

    execute("UPDATE itens_venda SET status='entregue', entregue_em=%s WHERE id=%s", (datetime.utcnow(), item["id"]))
    return {"ok": True, "status": "entregue", "item_id": item["id"]}
