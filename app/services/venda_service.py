from __future__ import annotations

from typing import Any, Dict, Optional
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda
from app.models.beneficio_produto import BeneficioProdutoCampanha
from app.utils.datetime_utils import FUSO_BRASIL

import uuid


def gerar_token_qr() -> str:
    return uuid.uuid4().hex


_CENTAVOS = Decimal("0.01")


def ratear_em_centavos(valor_total: Any, quantidade: int) -> list[Decimal]:
    """Rateia um total em fichas sem perder nem criar um centavo.

    Ex.: R$ 40,00 em 3 fichas resulta em 13,34 + 13,33 + 13,33.
    """
    if quantidade < 1:
        raise ValueError("A quantidade para rateio deve ser maior que zero.")
    centavos = int(
        (Decimal(str(valor_total or 0)) * 100).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    base, resto = divmod(centavos, quantidade)
    return [
        (Decimal(base + (1 if indice < resto else 0)) / 100).quantize(_CENTAVOS)
        for indice in range(quantidade)
    ]


def validar_limite_pacotes(
    db: Session,
    *,
    campanha: BeneficioProdutoCampanha,
    quantidade_pacotes: int,
) -> None:
    """Garante o limite da campanha usando pacotes, nunca as fichas geradas."""
    campanha = (
        db.query(BeneficioProdutoCampanha)
        .filter(
            BeneficioProdutoCampanha.beneficioprodutocampanha_id
            == campanha.beneficioprodutocampanha_id
        )
        .with_for_update()
        .first()
    )
    agora = datetime.now(FUSO_BRASIL).replace(tzinfo=None)
    if (
        not campanha
        or campanha.tipo != "PACOTE"
        or campanha.situacao != "ATIVA"
        or not (campanha.dthrinicio <= agora <= campanha.dthrfim)
    ):
        raise HTTPException(409, "Esta promoção não está mais disponível.")
    if campanha.qtlimite is None:
        return
    fichas_vendidas = int(
        db.query(ItVenda.itvenda_id)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(
            ItVenda.beneficioprodutocampanha_id
            == campanha.beneficioprodutocampanha_id,
            ItVenda.sititvenda == "ATIVO",
            Venda.sitvenda.in_(("PENDENTE", "PAGA")),
        )
        .count()
        or 0
    )
    pacotes_vendidos = fichas_vendidas // int(campanha.qtitenspacote or 1)
    if pacotes_vendidos + quantidade_pacotes > int(campanha.qtlimite):
        raise HTTPException(409, "Esta promoção já atingiu a quantidade disponível.")


def adicionar_itens_produto_venda(
    db: Session,
    *,
    venda_id: int,
    itens: list[Dict[str, Any]],
) -> None:
    """Cria fichas de produto, expandindo promoções em pacote em fichas unitárias."""
    campanhas_ids = {
        int(item["campanha_id"])
        for item in itens
        if item.get("campanha_id") is not None
    }
    campanhas = {
        int(campanha.beneficioprodutocampanha_id): campanha
        for campanha in db.query(BeneficioProdutoCampanha).filter(
            BeneficioProdutoCampanha.beneficioprodutocampanha_id.in_(
                campanhas_ids or {-1}
            )
        ).all()
    }

    for item in itens:
        produto_id = int(item["produto_id"])
        quantidade_linhas = int(
            item.get("qtitcarrinho") or item.get("qt") or 1
        )
        campanha_id = item.get("campanha_id")
        campanha = campanhas.get(int(campanha_id)) if campanha_id else None

        if campanha and campanha.tipo == "PACOTE":
            fichas_por_pacote = int(campanha.qtitenspacote or 0)
            if fichas_por_pacote < 2:
                raise HTTPException(409, "A promoção em pacote está inválida.")
            validar_limite_pacotes(
                db,
                campanha=campanha,
                quantidade_pacotes=quantidade_linhas,
            )
            valores = ratear_em_centavos(
                item.get("vrunitario"), fichas_por_pacote
            )
            taxas = ratear_em_centavos(
                item.get("vrtaxaitvenda"), fichas_por_pacote
            )
            for _ in range(quantidade_linhas):
                for indice in range(fichas_por_pacote):
                    db.add(
                        ItVenda(
                            venda_id=venda_id,
                            tipoitem="PRODUTO",
                            produto_id=produto_id,
                            cardapioitem_id=item.get("cardapioitem_id"),
                            beneficioprodutoresgate_id=item.get("beneficio_resgate_id"),
                            beneficioprodutocampanha_id=int(
                                campanha.beneficioprodutocampanha_id
                            ),
                            qtitvenda=1,
                            vrunititvenda=valores[indice],
                            dsobsitvenda=item.get("dsobsitcar"),
                            identregaitvenda="NAO",
                            qrtokenitvenda=gerar_token_qr(),
                            dtexpiraitvenda=None,
                            nmparticipante=item.get("nmparticipante"),
                            cpfparticipante=item.get("cpfparticipante"),
                            lote_id=None,
                            pctaxaitvenda=item.get("pctaxaitvenda"),
                            vrtaxaitvenda=taxas[indice],
                        )
                    )
            continue

        for _ in range(quantidade_linhas):
            db.add(
                ItVenda(
                    venda_id=venda_id,
                    tipoitem="PRODUTO",
                    produto_id=produto_id,
                    cardapioitem_id=item.get("cardapioitem_id"),
                    beneficioprodutoresgate_id=item.get("beneficio_resgate_id"),
                    beneficioprodutocampanha_id=campanha_id,
                    qtitvenda=1,
                    vrunititvenda=item.get("vrunitario", 0),
                    dsobsitvenda=item.get("dsobsitcar"),
                    identregaitvenda="NAO",
                    qrtokenitvenda=gerar_token_qr(),
                    dtexpiraitvenda=None,
                    nmparticipante=item.get("nmparticipante"),
                    cpfparticipante=item.get("cpfparticipante"),
                    lote_id=None,
                    pctaxaitvenda=item.get("pctaxaitvenda"),
                    vrtaxaitvenda=item.get("vrtaxaitvenda"),
                )
            )


async def criar_ou_obter_venda_idempotente(
    db: Session,
    *,
    cliente_id: int,
    loja_id: int,
    organizacao_id: int,
    carrinho: Dict[str, Any],
    usuario_id: int | None = None,
    chave: Optional[str] = None,
    plataforma: str = "ANDROID",
    metodo_pagamento: str = "CREDITO",  # PIX, CREDITO, DEBITO
) -> Dict[str, Any]:

    carrinho_id = int(carrinho.get("carrinho_id") or 0)
    itens = carrinho.get("itens", [])
    total = float(carrinho.get("total") or 0)

    if not carrinho_id:
        raise HTTPException(status_code=400, detail="carrinho_id inválido")

    if not itens:
        raise HTTPException(status_code=400, detail="Carrinho sem itens")

    metodo_pagamento = (metodo_pagamento or "CREDITO").strip().upper()

    if metodo_pagamento == "CREDIT_CARD":
        metodo_pagamento = "CREDITO"
    elif metodo_pagamento == "DEBIT_CARD":
        metodo_pagamento = "DEBITO"
    elif metodo_pagamento not in ["PIX", "CREDITO", "DEBITO", "OUTRO"]:
        metodo_pagamento = "OUTRO"

    ## testa venda PAGA PARA EVITAR duplicidade de criação da venda
    venda_paga = (
        db.query(Venda)
        .filter(
            Venda.loja_id == loja_id,
            Venda.cliente_id == cliente_id,
            Venda.carrinho_id == carrinho_id,
            Venda.sitvenda == "PAGA",
        )
        .order_by(Venda.venda_id.desc())
        .first()
    )

    if venda_paga:
        pag = (
            db.query(PagVenda)
            .filter(PagVenda.venda_id == venda_paga.venda_id)
            .order_by(PagVenda.pagvenda_id.desc())
            .first()
        )

        return {
            "venda_id": int(venda_paga.venda_id),
            "pagvenda_id": int(pag.pagvenda_id) if pag else 0,
            "reference_id": pag.reference_id if pag else f"VENDA-{venda_paga.venda_id}",
            "already_paid": True,
        }    
    ## >>>>>>>>>>>>>>>>>>>>>>>>>>>>>> fim >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

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
        adicionar_itens_produto_venda(db, venda_id=venda_id, itens=itens)

    if venda:
        venda.tipovenda = "PRODUTO"
        if venda.usuario_id is None:
            venda.usuario_id = usuario_id
        _sync_itens_venda(venda.venda_id)

        venda.totalvenda = float(total)

        if hasattr(venda, "dsplataforma"):
            venda.dsplataforma = plataforma

        if chave and hasattr(venda, "idempotency_key") and not getattr(venda, "idempotency_key", None):
            venda.idempotency_key = chave

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
                dsmetodopag=metodo_pagamento,
                vrpagvenda=float(total),
                sitpagvenda="PENDENTE",
                reference_id=f"VENDA-{venda.venda_id}",
                provedor="ASAAS",
            )
            db.add(pag)
            db.flush()
        else:
            pag.dsmetodopag = metodo_pagamento
            pag.vrpagvenda = float(total)

            if not getattr(pag, "reference_id", None):
                pag.reference_id = f"VENDA-{venda.venda_id}"

            if not getattr(pag, "provedor", None):
                pag.provedor = "ASAAS"

        return {
            "venda_id": int(venda.venda_id),
            "pagvenda_id": int(pag.pagvenda_id),
            "reference_id": pag.reference_id,
        }

    venda = Venda(
        loja_id=loja_id,
        organizacao_id=organizacao_id,
        cliente_id=cliente_id,
        usuario_id=usuario_id,
        carrinho_id=carrinho_id,
        tipovenda="PRODUTO",
        sitvenda="PENDENTE",
        totalvenda=float(total),
    )

    if hasattr(venda, "dsplataforma"):
        venda.dsplataforma = plataforma

    if chave and hasattr(venda, "idempotency_key"):
        venda.idempotency_key = chave

    db.add(venda)
    db.flush()

    _sync_itens_venda(venda.venda_id)

    reference_id = f"VENDA-{venda.venda_id}"

    pag = PagVenda(
        venda_id=venda.venda_id,
        dsmetodopag=metodo_pagamento,
        vrpagvenda=float(total),
        sitpagvenda="PENDENTE",
        reference_id=reference_id,
        provedor="ASAAS",
    )

    db.add(pag)
    db.flush()

    return {
        "venda_id": int(venda.venda_id),
        "pagvenda_id": int(pag.pagvenda_id),
        "reference_id": reference_id,
    }
