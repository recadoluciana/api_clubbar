from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda

import uuid

def gerar_token_qr() -> str:
    return uuid.uuid4().hex
    
async def criar_ou_obter_venda_idempotente(
    db: Session,
    *,
    cliente_id: int,
    loja_id: int,
    organizacao_id: int,
    carrinho: Dict[str, Any],
    chave: Optional[str] = None,
    plataforma: str = "ANDROID",
) -> Dict[str, Any]:
    """
    Regras:
    - Reaproveita venda PENDENTE mais recente do mesmo carrinho_id (idempotência).
    - Sincroniza ItVenda com os itens atuais do carrinho.
    - Garante PagVenda PENDENTE.
    - Não chama PagBank.
    - Não faz commit/rollback (rota controla com db.begin()).
    """
    carrinho_id = int(carrinho.get("carrinho_id") or 0)

    itens = carrinho.get("itens", [])
    total = float(carrinho.get("total") or 0)

    print ("aqui é o ultimo print", itens)

    if not carrinho_id:
        raise HTTPException(status_code=400, detail="carrinho_id inválido")
    if not itens:
        raise HTTPException(status_code=400, detail="Carrinho sem itens")

    # 1) procura venda pendente desse carrinho
    venda = (
        db.query(Venda)
        .filter(
            Venda.loja_id == loja_id,
            Venda.cliente_id == cliente_id,
            Venda.carrinho_id == carrinho_id,
            Venda.sitvenda == "PENDENTE",
        )
        .order_by(Venda.venda_id.desc())
        .first()
    )

    def _sync_itens_venda(venda_id: int) -> None:
        db.execute(delete(ItVenda).where(ItVenda.venda_id == venda_id))

        agora = datetime.now()
        fim = agora + timedelta(days=30)

        print("estou no _sync_itens_venda", itens)

        for it in itens:
            produto_id     = int(it["produto_id"])
            qtd = int(it.get("qtitcarrinho", 1) or 1)
            vr_unit = float(it.get("vrunitario", 0) or 0)
            dsobsitcar = it.get("dsobsitcar")


            db.add(
                ItVenda(
                    venda_id=venda_id,
                    produto_id=produto_id,
                    qtitvenda=qtd,
                    vrunititvenda=vr_unit,
                    dsobsitvenda=dsobsitcar,
                    identregaitvenda="NAO",
                    qrtokenitvenda=gerar_token_qr(),
                    dtexpiraitvenda=fim,
                )
            )

    # 2) se existe venda pendente -> reaproveita
    if venda:
        _sync_itens_venda(venda.venda_id)

        venda.totalvenda = float(total)
        if hasattr(venda, "dsplataforma"):
            venda.dsplataforma = plataforma
        if chave and hasattr(venda, "idempotency_key") and not getattr(venda, "idempotency_key", None):
            venda.idempotency_key = chave

        # 2.1) garante PagVenda pendente
        pag = (
            db.query(PagVenda)
            .filter(
                PagVenda.venda_id == venda.venda_id,
                PagVenda.sitpagvenda == "PENDENTE",
            )
            .order_by(PagVenda.pagvenda_id.desc())
            .first()
        )

        if not pag:
            pag = PagVenda(
                venda_id=venda.venda_id,
                dsmetodopag="CREDITO",
                vrpagvenda=float(total),
                sitpagvenda="PENDENTE",
                reference_id=f"VENDA-{venda.venda_id}",
                provedor="PAGBANK",
            )
            if chave and hasattr(pag, "idempotency_key"):
                pag.idempotency_key = chave
            db.add(pag)
            db.flush()
        else:
            pag.vrpagvenda = float(total)
            if not getattr(pag, "reference_id", None):
                pag.reference_id = f"VENDA-{venda.venda_id}"
            if not getattr(pag, "provedor", None):
                pag.provedor = "PAGBANK"
            if chave and hasattr(pag, "idempotency_key") and not getattr(pag, "idempotency_key", None):
                pag.idempotency_key = chave

        return {
            "venda_id": int(venda.venda_id),
            "pagvenda_id": int(pag.pagvenda_id),
            "reference_id": pag.reference_id,
        }

    # 3) se não existe venda pendente -> cria venda + itens + pagvenda
    venda = Venda(
        loja_id=loja_id,
        organizacao_id=organizacao_id,
        cliente_id=cliente_id,
        carrinho_id=carrinho_id,
        sitvenda="PENDENTE",
        totalvenda=float(total),
    )
    if hasattr(venda, "dsplataforma"):
        venda.dsplataforma = plataforma
    if chave and hasattr(venda, "idempotency_key"):
        venda.idempotency_key = chave

    db.add(venda)
    db.flush()  # gera venda_id

    _sync_itens_venda(venda.venda_id)

    reference_id = f"VENDA-{venda.venda_id}"
    pag = PagVenda(
        venda_id=venda.venda_id,
        dsmetodopag="CREDITO",
        vrpagvenda=float(total),
        sitpagvenda="PENDENTE",
        reference_id=reference_id,
        provedor="PAGBANK",
    )
    if chave and hasattr(pag, "idempotency_key"):
        pag.idempotency_key = chave

    db.add(pag)
    db.flush()

    return {
        "venda_id": int(venda.venda_id),
        "pagvenda_id": int(pag.pagvenda_id),
        "reference_id": reference_id,
    }