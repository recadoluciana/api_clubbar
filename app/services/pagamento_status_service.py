from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.venda import Venda 
from app.models.pagvenda import PagVenda
from app.models.loja import Loja
from app.models.itvenda import ItVenda
from app.models.carrinho import Carrinho
from app.models.itcarrinho import ItCarrinho 

def set_venda_como_paga(
    db: Session,
    *,
    venda_id: int,
    gateway: str = "PAGBANK",
    payload: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    - PagVenda.sitpagvenda = PAGO
    - Venda.sitvenda = PAGA
    - define dtconftranspagvenda
    - guarda idtransacaopagvenda (charge_id do PagBank)
    - calcula validade (Loja.nrdiavalidade, fallback 30) em ItVenda.dtexpiraitvenda
    - fecha carrinho e limpa itens
    Chamar dentro de: with db.begin():
    """
    payload = payload or {}

    # PagBank: tenta extrair charge id/status
    charge = (payload.get("charges") or [{}])[0]
    charge_id = charge.get("id")  # bom pra idtransacaopagvenda
    charge_status = charge.get("status") or ""

    venda = (
        db.query(Venda)
        .filter(Venda.venda_id == venda_id)
        .with_for_update()
        .first()
    )
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")

    pag = (
        db.query(PagVenda)
        .filter(PagVenda.venda_id == venda_id)
        .order_by(PagVenda.pagvenda_id.desc())
        .with_for_update()
        .first()
    )
    if not pag:
        raise HTTPException(status_code=404, detail="PagVenda não encontrada")

    # idempotência
    if (pag.sitpagvenda or "").upper() == "PAGO" and (venda.sitvenda or "").upper() == "PAGA":
        return {"ok": True, "already_processed": True, "venda_id": venda_id}

    # atualiza status
    pag.sitpagvenda = "PAGO"
    pag.provedor = gateway if gateway in {"PAGBANK", "OUTRO"} else "PAGBANK"
    pag.dtconftranspagvenda = datetime.now()
    pag.dtultatu = datetime.now()

    # guarda id da transação (charge id)
    if charge_id:
        pag.idtransacaopagvenda = str(charge_id)

    # venda
    venda.sitvenda = "PAGA"
    venda.dtultatu = datetime.now()

    # validade conforme loja.nrdiavalidade (fallback 30)
    loja = (
        db.query(Loja)
        .filter(
            Loja.loja_id == venda.loja_id,
            Loja.organizacao_id == venda.organizacao_id,
        )
        .first()
    )
    nr_dias = int(getattr(loja, "nrdiavalidade", 0) or 0) if loja else 0
    if nr_dias <= 0:
        nr_dias = 30

    data_expira = date.today() + timedelta(days=nr_dias)

    db.query(ItVenda).filter(ItVenda.venda_id == venda_id).update(
        {"dtexpiraitvenda": data_expira},
        synchronize_session=False,
    )

    # fecha carrinho + limpa itens
    carrinho_id = venda.carrinho_id
    carrinho_ok = False
    if carrinho_id:
        carrinho = (
            db.query(Carrinho)
            .filter(Carrinho.carrinho_id == carrinho_id)
            .with_for_update()
            .first()
        )
        if carrinho:
            carrinho.sitcarrinho = "FECHADO"
            db.query(ItCarrinho).filter(ItCarrinho.carrinho_id == carrinho_id).delete(
                synchronize_session=False
            )
            carrinho_ok = True

    return {
        "ok": True,
        "venda_id": venda_id,
        "charge_status": charge_status,
        "idtransacaopagvenda": pag.idtransacaopagvenda,
        "carrinho_fechado": carrinho_ok,
    }


def set_venda_como_cancelada(
    db: Session,
    *,
    venda_id: int,
    gateway: str = "PAGBANK",
    payload: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    - PagVenda.sitpagvenda = CANCELADO
    - Venda.sitvenda = CANCELADA
    - define dtconftranspagvenda
    - guarda idtransacaopagvenda (charge_id do PagBank)
    - fecha carrinho e limpa itens (mesmo padrão do seu webhook)
    Chamar dentro de: with db.begin():
    """
    payload = payload or {}

    charge = (payload.get("charges") or [{}])[0]
    charge_id = charge.get("id")
    charge_status = charge.get("status") or ""

    venda = (
        db.query(Venda)
        .filter(Venda.venda_id == venda_id)
        .with_for_update()
        .first()
    )
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")

    pag = (
        db.query(PagVenda)
        .filter(PagVenda.venda_id == venda_id)
        .order_by(PagVenda.pagvenda_id.desc())
        .with_for_update()
        .first()
    )
    if not pag:
        raise HTTPException(status_code=404, detail="PagVenda não encontrada")

    # idempotência
    if (pag.sitpagvenda or "").upper() == "CANCELADO" and (venda.sitvenda or "").upper() == "CANCELADA":
        return {"ok": True, "already_processed": True, "venda_id": venda_id}

    pag.sitpagvenda = "CANCELADO"
    pag.provedor = gateway if gateway in {"PAGBANK", "OUTRO"} else "PAGBANK"
    pag.dtconftranspagvenda = datetime.now()
    pag.dtultatu = datetime.now()

    if charge_id:
        pag.idtransacaopagvenda = str(charge_id)

    venda.sitvenda = "CANCELADA"
    venda.dtultatu = datetime.now()

    # fecha carrinho + limpa itens (se quiser manter carrinho aberto em cancelamento, comente este bloco)
    carrinho_id = venda.carrinho_id
    carrinho_ok = False
    if carrinho_id:
        carrinho = (
            db.query(Carrinho)
            .filter(Carrinho.carrinho_id == carrinho_id)
            .with_for_update()
            .first()
        )
        if carrinho:
            carrinho.sitcarrinho = "FECHADO"
            db.query(ItCarrinho).filter(ItCarrinho.carrinho_id == carrinho_id).delete(
                synchronize_session=False
            )
            carrinho_ok = True

    return {
        "ok": True,
        "venda_id": venda_id,
        "charge_status": charge_status,
        "idtransacaopagvenda": pag.idtransacaopagvenda,
        "carrinho_fechado": carrinho_ok,
    }