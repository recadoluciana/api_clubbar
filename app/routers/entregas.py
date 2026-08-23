# app/routers/entregas.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from app.utils.datetime_utils import formatar_data_br, iso_utc
from sqlalchemy import or_, case

from app.database import get_db
from app.core.security import get_usuario_logado
from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.produto import Produto
from app.models.loja import Loja
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.pagvenda import PagVenda
from app.core.config import ASAAS_API_KEY
from app.services.asaas_service import estornar_pagamento_asaas

from app.schemas.entregas import LojaRetiradaOut,AlterarParticipanteIn
router = APIRouter(prefix="/entregas", tags=["entregas"])
_FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def _hoje_brasil() -> date:
    return datetime.now(_FUSO_BRASIL).date()


def _cancelamento_ingresso_permitido(
    data_compra: datetime,
    data_evento: datetime,
    agora: datetime | None = None,
) -> bool:
    momento_atual = agora or datetime.now()
    return (
        momento_atual <= data_compra + timedelta(days=7)
        and momento_atual <= data_evento - timedelta(hours=48)
    )


@router.get("/pendentes")
def listar_itens_nao_entregues(
    cliente_id: int = Query(...),
    loja_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """
    Lista itens de vendas PAGAS que ainda NÃO foram entregues
    loja_id = 0 -> todas as lojas
    """

    hoje = _hoje_brasil()

    query = (
        db.query(
            ItVenda.itvenda_id,
            ItVenda.venda_id,
            ItVenda.qrtokenitvenda,
            Produto.produto_id,
            Produto.nmproduto,
            Produto.urlfotoproduto,
            Produto.idtipoproduto,
            Loja.nmloja,
            Loja.urllogoloja,
            Loja.dsinstaloja,
            Cliente.nmcliente,
            ItVenda.qtitvenda,
            ItVenda.vrunititvenda,
            ItVenda.dsobsitvenda,
            ItVenda.dtexpiraitvenda,
            ItVenda.nmparticipante,
            ItVenda.cpfparticipante,
            Venda.dtcriacao,
            Venda.loja_id,
        )
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(Cliente, Cliente.cliente_id == Venda.cliente_id)
        .join(Produto, Produto.produto_id == ItVenda.produto_id)
        .join(Loja, Loja.loja_id == Venda.loja_id)
        .outerjoin(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .outerjoin(Evento, Evento.evento_id == EventoLote.evento_id)
        .filter(Venda.cliente_id == cliente_id)
        .filter(Venda.sitvenda == "PAGA")
        .filter(ItVenda.identregaitvenda == "NAO")
        .filter(ItVenda.sititvenda == "ATIVO")
        .filter(
            or_(
                (
                    (Produto.idtipoproduto != "I")
                    & or_(
                        ItVenda.dtexpiraitvenda.is_(None),
                        ItVenda.dtexpiraitvenda >= hoje,
                    )
                ),
                (
                    (Produto.idtipoproduto == "I")
                    & (Evento.dtinicioevento.isnot(None))
                    & (func.date(Evento.dtinicioevento) >= hoje)
                ),
            )
        )
        .add_columns(
            Evento.nmtituloevento,
            Evento.dtinicioevento,
        )
    )

    # 🔹 filtro opcional por loja
    if loja_id != 0:
        query = query.filter(Venda.loja_id == loja_id)

    itens = query.order_by(ItVenda.dtexpiraitvenda.asc()).all()

    return [
        {
            "itvenda_id": row.itvenda_id,
            "venda_id": row.venda_id,
            "produto_id": row.produto_id,
            "qrtokenitvenda": row.qrtokenitvenda or "",
            "nmproduto": row.nmproduto,
            "urlfotoproduto": row.urlfotoproduto,
            "idtipoproduto": row.idtipoproduto,
            "qtitvenda": row.qtitvenda,
            "vrunititvenda": float(row.vrunititvenda or 0.0),
            "dsobsitvenda": row.dsobsitvenda,
            "dtexpiraitvenda": row.dtexpiraitvenda,
            "dtexpiraitvenda_fmt": row.dtexpiraitvenda.strftime("%d/%m/%Y") if row.dtexpiraitvenda else None,
            "dtcriacao": iso_utc(row.dtcriacao),
            "dtcriacao_fmt": formatar_data_br(row.dtcriacao) if row.dtcriacao else None,
            "nmevento": row.nmtituloevento,
            "dtinicioevento": row.dtinicioevento,
            "dtinicioevento_fmt": row.dtinicioevento.strftime("%d/%m/%Y %H:%M") if row.dtinicioevento else None,
            "loja_id": row.loja_id,
            "nmloja" : row.nmloja,
            "urllogoloja": row.urllogoloja,
            "dsinstaloja": row.dsinstaloja,
            "nmcliente" : row.nmcliente,
            "nmparticipante": row.nmparticipante,
            "cpfparticipante": row.cpfparticipante,
        }
        for row in itens
    ]


@router.post("/itvenda/{itvenda_id}/cancelar-ingresso")
async def cancelar_ingresso(
    itvenda_id: int,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    if payload.get("role") != "cliente":
        raise HTTPException(status_code=403, detail="Acesso exclusivo do cliente.")

    resultado = (
        db.query(ItVenda, Venda, Produto, EventoLote, Evento, PagVenda)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(Produto, Produto.produto_id == ItVenda.produto_id)
        .join(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .join(Evento, Evento.evento_id == EventoLote.evento_id)
        .join(PagVenda, PagVenda.venda_id == Venda.venda_id)
        .filter(ItVenda.itvenda_id == itvenda_id)
        .with_for_update()
        .first()
    )
    if not resultado:
        raise HTTPException(status_code=404, detail="Ingresso não encontrado.")

    item, venda, produto, lote, evento, pagamento = resultado
    if str(venda.cliente_id) != str(payload.get("sub")):
        raise HTTPException(status_code=403, detail="Este ingresso pertence a outro cliente.")
    if (produto.idtipoproduto or "").upper() != "I":
        raise HTTPException(status_code=400, detail="O item informado não é um ingresso.")
    if item.sititvenda == "CANCELADO":
        return {"ok": True, "cancelado": True, "itvenda_id": item.itvenda_id}
    if pagamento.sitpagvenda != "PAGO":
        raise HTTPException(status_code=409, detail="O pagamento da venda não está confirmado.")
    if item.sititvenda == "CANCELAMENTO_SOLICITADO":
        raise HTTPException(status_code=409, detail="Cancelamento já está sendo processado.")
    if (item.identregaitvenda or "NAO").upper() == "SIM":
        raise HTTPException(status_code=409, detail="Ingresso já utilizado não pode ser cancelado.")

    if not _cancelamento_ingresso_permitido(
        venda.dtcriacao,
        evento.dtinicioevento,
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Cancelamento não permitido. O ingresso só pode ser cancelado "
                "em até 7 dias após a compra e com no mínimo 48 horas de "
                "antecedência do início do evento."
            ),
        )
    payment_id = str(pagamento.idtransacaopagvenda or "").strip()
    if not payment_id or not ASAAS_API_KEY:
        raise HTTPException(status_code=503, detail="Pagamento Asaas indisponível para estorno.")

    valor_reembolso = round(
        float(item.vrunititvenda or 0) * int(item.qtitvenda or 1)
        + float(item.vrtaxaitvenda or 0),
        2,
    )
    item.sititvenda = "CANCELAMENTO_SOLICITADO"
    db.commit()

    try:
        estorno = await estornar_pagamento_asaas(
            payment_id=payment_id,
            valor=valor_reembolso,
            descricao=f"Cancelamento ingresso Clubbar item {item.itvenda_id}",
            api_key=ASAAS_API_KEY,
        )
    except HTTPException as exc:
        db.rollback()
        if exc.status_code < 500:
            item = db.query(ItVenda).filter(ItVenda.itvenda_id == itvenda_id).first()
            if item and item.sititvenda == "CANCELAMENTO_SOLICITADO":
                item.sititvenda = "ATIVO"
                db.commit()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail=(
                "O Asaas ainda não confirmou o cancelamento. A solicitação foi "
                "mantida em processamento para evitar reembolso duplicado."
            ),
        ) from exc

    item = db.query(ItVenda).filter(ItVenda.itvenda_id == itvenda_id).first()
    lote = db.query(EventoLote).filter(EventoLote.lote_id == item.lote_id).first()
    item.sititvenda = "CANCELADO"
    item.dtcancelamento = datetime.now()
    item.vrreembolso = valor_reembolso
    item.idreembolso = str(estorno.get("id") or "")
    if lote and lote.qtvendidalote:
        lote.qtvendidalote = max(
            0,
            lote.qtvendidalote - int(item.qtitvenda or 1),
        )
    itens_ativos = (
        db.query(func.count(ItVenda.itvenda_id))
        .filter(
            ItVenda.venda_id == venda.venda_id,
            ItVenda.sititvenda != "CANCELADO",
        )
        .scalar()
        or 0
    )
    if itens_ativos == 0:
        venda.sitvenda = "CANCELADA"
        pagamento.sitpagvenda = "CANCELADO"
    db.commit()
    return {
        "ok": True,
        "cancelado": True,
        "itvenda_id": item.itvenda_id,
        "valor_reembolso": valor_reembolso,
    }


@router.post("/{itvenda_id}/entregarproduto")
def entregar_produto(
    itvenda_id: int,
    usuario_id: int,
    db: Session = Depends(get_db),
):

    usuario = (
        db.query(Usuario)
        .filter(Usuario.usuario_id == usuario_id)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado.",
        )

    quantidade_atualizada = (
        db.query(ItVenda)
        .filter(ItVenda.itvenda_id == itvenda_id)
        .filter(ItVenda.identregaitvenda != "SIM")
        .filter(ItVenda.sititvenda == "ATIVO")
        .update(
            {
                ItVenda.identregaitvenda: "SIM",
                ItVenda.dtentregaitvenda: datetime.now(),
                ItVenda.userentregaitvenda: usuario.usuario_id,
                ItVenda.nmuserentregaitvenda: usuario.nmusuario,
            },
            synchronize_session=False,
        )
    )

    db.commit()

    if quantidade_atualizada == 0:
        raise HTTPException(
            status_code=409,
            detail="Este produto já foi utilizado.",
        )

    item = (
        db.query(ItVenda)
        .filter(ItVenda.itvenda_id == itvenda_id)
        .first()
    )

    return {
        "ok": True,
        "msg": "Produto entregue com sucesso.",
        "itvenda_id": item.itvenda_id,
        "dtentregaitvenda": item.dtentregaitvenda.isoformat(),
        "userentregaitvenda": item.userentregaitvenda,
        "nmuserentregaitvenda": item.nmuserentregaitvenda,
    }

@router.get("/{itvenda_id}/status")
def status_entrega(itvenda_id: int, db: Session = Depends(get_db)):
    
    item = db.query(ItVenda).filter(ItVenda.itvenda_id == itvenda_id).first()
    
    if not item:
        print("deu status_code 404, nao achou o item", itvenda_id)
        raise HTTPException(status_code=404, detail="Item não encontrado")

    entregue = (item.identregaitvenda == "SIM")

    return {
        "ok": True,
        "itvenda_id": itvenda_id,
        "entregue": entregue,
        "identregaitvenda": item.identregaitvenda,
        "dtentregaitvenda": item.dtentregaitvenda.isoformat() if item.dtentregaitvenda else None,
        "userentregaitvenda": item.userentregaitvenda,
        "nmuserentregaitvenda": item.nmuserentregaitvenda,
    }

@router.get("/entregues")
def listar_entregues_por_usuario(
    usuario_id: int = Query(...),
    organizacao_id: int = Query(...),
    loja_id: int = Query(...),
    horas: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """
    Lista itens entregues pelo usuário logado nas últimas X horas (padrão 24h),
    mais recentes primeiro.
    """

    desde = datetime.now() - timedelta(hours=horas)

    itens = (
        db.query(
            ItVenda.itvenda_id.label("itvenda_id"),
            ItVenda.venda_id.label("venda_id"),
            ItVenda.qtitvenda.label("qtitvenda"),
            ItVenda.vrunititvenda.label("vrunititvenda"),
            ItVenda.dsobsitvenda.label("dsobsitvenda"),
            ItVenda.dtentregaitvenda.label("dtentregaitvenda"),
            ItVenda.userentregaitvenda.label("userentregaitvenda"),
            ItVenda.nmuserentregaitvenda.label("nmuserentregaitvenda"),
            Produto.produto_id.label("produto_id"),
            Produto.nmproduto.label("nmproduto"),
        )
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(Produto, Produto.produto_id == ItVenda.produto_id)
        .filter(
            Venda.organizacao_id == organizacao_id,
            Venda.loja_id == loja_id,

            # entregue (você usa SIM / ENTREGUE em lugares diferentes — aceito ambos)
            or_(
                ItVenda.identregaitvenda == "SIM",
                ItVenda.identregaitvenda == "ENTREGUE",
            ),

            ItVenda.userentregaitvenda == usuario_id,
            ItVenda.dtentregaitvenda != None,
            ItVenda.dtentregaitvenda >= desde,
        )
        .order_by(ItVenda.dtentregaitvenda.desc())
        .all()
    )

    return [
        {
            "itvenda_id": r.itvenda_id,
            "venda_id": r.venda_id,
            "qtitvenda": int(r.qtitvenda or 0),
            "vrunititvenda": float(r.vrunititvenda or 0.0),
            "dsobsitvenda": r.dsobsitvenda,
            "dtentregaitvenda": r.dtentregaitvenda.isoformat() if r.dtentregaitvenda else None,
            "dtentregaitvenda_fmt": r.dtentregaitvenda.strftime("%d/%m/%Y %H:%M") if r.dtentregaitvenda else None,
            "userentregaitvenda": r.userentregaitvenda,
            "nmuserentregaitvenda": r.nmuserentregaitvenda,
            "produto_id": r.produto_id,
            "nmproduto": r.nmproduto,
        }
        for r in itens
    ]

@router.get("/get_carteira_qt")
def get_qt_itens_naoentregues(
    cliente_id: int = Query(...),
    loja_id: int = Query(0),
    db: Session = Depends(get_db),
):
    """
    Retorna a quantidade de itens ainda não entregues na carteira do cliente.

    Regras:
    - identregaitvenda = 'NAO'
    - se loja_id = 0, soma todas as lojas
    - se loja_id > 0, filtra pela loja informada
    """
    try:
        query = (
            db.query(
                func.coalesce(func.sum(ItVenda.qtitvenda), 0).label("qt_total"),
                func.coalesce(
                    func.sum(ItVenda.qtitvenda * ItVenda.vrunititvenda),
                    0,
                ).label("valor_total"),
            )
            .join(Venda, Venda.venda_id == ItVenda.venda_id)
            .join(Produto, Produto.produto_id == ItVenda.produto_id)
            .outerjoin(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
            .outerjoin(Evento, Evento.evento_id == EventoLote.evento_id)
            .filter(
                Venda.cliente_id == cliente_id,
                Venda.sitvenda == "PAGA",
                ItVenda.identregaitvenda == "NAO",
                ItVenda.sititvenda == "ATIVO",
            )
            .filter(
                or_(
                    (
                        (Produto.idtipoproduto != "I")
                        & or_(
                            ItVenda.dtexpiraitvenda.is_(None),
                            ItVenda.dtexpiraitvenda >= _hoje_brasil(),
                        )
                    ),
                    (
                        (Produto.idtipoproduto == "I")
                        & (Evento.dtinicioevento.isnot(None))
                        & (func.date(Evento.dtinicioevento) >= _hoje_brasil())
                    ),
                )
            )
        )

        if loja_id != 0:
            query = query.filter(Venda.loja_id == loja_id)

        resultado = query.first()

        qt_total = int(resultado.qt_total or 0)
        valor_total = float(resultado.valor_total or 0)
        valor_total = round(valor_total, 2)
        valor_total_fmt = f"{valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        return {
            "ok": True,
            "cliente_id": cliente_id,
            "loja_id": loja_id,
            "qt_total": qt_total,
            "valor_total": round(valor_total, 2),
            "valor_total_fmt": valor_total_fmt,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar quantidade da carteira: {e}")


@router.get("/lojas", response_model=list[LojaRetiradaOut])
def listar_lojas_com_retirada_pendente(
    cliente_id: int,
    db: Session = Depends(get_db)
):
    """
    Retorna as lojas onde o cliente tem itens pendentes de retirada.
    """

    rows = (
        db.query(
            Loja.loja_id.label("loja_id"),
            Loja.nmloja.label("nmloja"),
            Loja.dsbairroloja.label("dsbairroloja"),
            func.count(ItVenda.itvenda_id).label("total_itens"),
        )
        .join(Venda, Venda.loja_id == Loja.loja_id)
        .join(ItVenda, ItVenda.venda_id == Venda.venda_id)
        .join(Produto, Produto.produto_id == ItVenda.produto_id)
        .outerjoin(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .outerjoin(Evento, Evento.evento_id == EventoLote.evento_id)
        .filter(Venda.cliente_id == cliente_id)
        .filter(Venda.sitvenda == "PAGA")
        .filter(ItVenda.identregaitvenda == "NAO")
        .filter(ItVenda.sititvenda == "ATIVO")
        .filter(
            or_(
                (
                    (Produto.idtipoproduto != "I")
                    & or_(
                        ItVenda.dtexpiraitvenda.is_(None),
                        ItVenda.dtexpiraitvenda >= _hoje_brasil(),
                    )
                ),
                (
                    (Produto.idtipoproduto == "I")
                    & (Evento.dtinicioevento.isnot(None))
                    & (func.date(Evento.dtinicioevento) >= _hoje_brasil())
                ),
            )
        )
        .group_by(
            Loja.loja_id,
            Loja.nmloja,
            Loja.dsbairroloja,
        )
        .order_by(Loja.nmloja.asc())
        .all()
    )

    return [
        LojaRetiradaOut(
            loja_id=row.loja_id,
            nmloja=row.nmloja,
            dsbairroloja=row.dsbairroloja,
            total_itens=row.total_itens,
        )
        for row in rows
    ]

@router.put("/itvenda/{itvenda_id}/participante")
def alterar_participante_itvenda(
    itvenda_id: int,
    payload: AlterarParticipanteIn,
    db: Session = Depends(get_db),
):
    nome = payload.nmparticipante.strip()
    cpf = "".join(ch for ch in payload.cpfparticipante if ch.isdigit())

    if not nome:
        raise HTTPException(status_code=400, detail="Nome do participante obrigatório")

    if len(cpf) != 11:
        raise HTTPException(status_code=400, detail="CPF do participante inválido")

    item = db.query(ItVenda).filter(ItVenda.itvenda_id == itvenda_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item da venda não encontrado")

    item.nmparticipante = nome
    item.cpfparticipante = cpf

    db.commit()
    db.refresh(item)

    return {
        "ok": True,
        "tipo": "itvenda",
        "itvenda_id": item.itvenda_id,
        "nmparticipante": item.nmparticipante,
        "cpfparticipante": item.cpfparticipante,
    }

@router.get("/buscar-por-token/{token}")
def buscar_item_por_token(
    token: str,
    usuario_id: int,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    token = token.strip()
    if str(payload.get("sub", "")) != str(usuario_id):
        raise HTTPException(status_code=403, detail="Usuário autenticado inválido.")

    if not token:
        raise HTTPException(
            status_code=400,
            detail="Token não informado.",
        )

    usuario = (
        db.query(Usuario)
        .filter(Usuario.usuario_id == usuario_id)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Usuário responsável não encontrado.",
        )

    if not usuario.loja_id:
        raise HTTPException(
            status_code=403,
            detail="O usuário não está vinculado a uma loja.",
        )

    resultado = (
        db.query(
            ItVenda,
            Produto,
            Venda,
            Loja,
            Cliente,
        )
        .outerjoin(
            Produto,
            Produto.produto_id == ItVenda.produto_id,
        )
        .join(
            Venda,
            Venda.venda_id == ItVenda.venda_id,
        )
        .join(
            Loja,
            Loja.loja_id == Venda.loja_id,
        )
        .join(
            Cliente,
            Cliente.cliente_id == Venda.cliente_id,
        )
        .filter(ItVenda.qrtokenitvenda == token)
        .first()
    )

    if not resultado:
        raise HTTPException(
            status_code=404,
            detail="Item não encontrado ou QR Code inválido.",
        )

    item, produto, venda, loja, cliente = resultado

    if item.sititvenda != "ATIVO":
        raise HTTPException(status_code=409, detail="Este ingresso foi cancelado.")

    # Impede o usuário de visualizar produto de outra loja
    if venda.loja_id != usuario.loja_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "Este QR Code pertence a outro bar/casa noturna. "
                "Retirada não permitida! Feche esta tela, verifique "
                "o estabelecimento correto e tente novamente."
            ),
        )

    entregue = (
        (item.identregaitvenda or "NAO")
        .strip()
        .upper()
        == "SIM"
    )

    return {
        "itvenda_id": item.itvenda_id,
        "produto_id": item.produto_id,
        "idtipoproduto": item.idtipoproduto,
        "loja_id": loja.loja_id,

        "nmproduto": (
            produto.nmproduto
            if produto
            else (item.dsobsitvenda or "Ingresso")
        ),
        "urlfotoproduto": (
            produto.urlfotoproduto
            if produto
            else ""
        ),

        "nmloja": loja.nmloja or "",
        "nmcliente": cliente.nmcliente or "",

        "qtitvenda": item.qtitvenda or 1,
        "dsobsitvenda": item.dsobsitvenda or "",
        "nmparticipante": item.nmparticipante or "",
        "cpfparticipante": item.cpfparticipante or "",

        "identregaitvenda": item.identregaitvenda or "NAO",
        "dtentregaitvenda": (
            item.dtentregaitvenda.isoformat()
            if item.dtentregaitvenda
            else None
        ),
        "disponivel": not entregue,
    }

@router.post("/entregar-por-token/{token}")
def entregar_produto_por_token(
    token: str,
    usuario_id: int,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    token = token.strip()
    if str(payload.get("sub", "")) != str(usuario_id):
        raise HTTPException(status_code=403, detail="Usuário autenticado inválido.")

    if not token:
        raise HTTPException(
            status_code=400,
            detail="Token não informado.",
        )

    usuario = (
        db.query(Usuario)
        .filter(Usuario.usuario_id == usuario_id)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Usuário responsável não encontrado.",
        )

    if not usuario.loja_id:
        raise HTTPException(
            status_code=403,
            detail="O usuário não está vinculado a uma loja.",
        )

    resultado = (
        db.query(
            ItVenda,
            Produto,
            Venda,
            Loja,
            Cliente,
        )
        .outerjoin(
            Produto,
            Produto.produto_id == ItVenda.produto_id,
        )
        .join(
            Venda,
            Venda.venda_id == ItVenda.venda_id,
        )
        .join(
            Loja,
            Loja.loja_id == Venda.loja_id,
        )
        .join(
            Cliente,
            Cliente.cliente_id == Venda.cliente_id,
        )
        .filter(ItVenda.qrtokenitvenda == token)
        .first()
    )

    if not resultado:
        raise HTTPException(
            status_code=404,
            detail="Item não encontrado ou QR Code inválido.",
        )

    item, produto, venda, loja, cliente = resultado

    if item.sititvenda != "ATIVO":
        raise HTTPException(status_code=409, detail="Este ingresso foi cancelado.")

    # Segurança obrigatória antes da baixa
    if venda.loja_id != usuario.loja_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "Este QR Code pertence a outro bar/casa noturna. "
                "Retirada não permitida! Feche esta tela, verifique "
                "o estabelecimento correto e tente novamente."
            ),
        )

    quantidade_atualizada = (
        db.query(ItVenda)
        .filter(ItVenda.itvenda_id == item.itvenda_id)
        .filter(ItVenda.sititvenda == "ATIVO")
        .filter(
            (ItVenda.identregaitvenda.is_(None))
            | (ItVenda.identregaitvenda != "SIM")
        )
        .update(
            {
                ItVenda.identregaitvenda: "SIM",
                ItVenda.dtentregaitvenda: datetime.now(),
                ItVenda.userentregaitvenda: usuario.usuario_id,
                ItVenda.nmuserentregaitvenda: usuario.nmusuario,
            },
            synchronize_session=False,
        )
    )

    if quantidade_atualizada == 0:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Este produto já foi utilizado.",
        )

    db.commit()
    db.refresh(item)

    return {
        "ok": True,
        "msg": "Produto entregue com sucesso.",

        "itvenda_id": item.itvenda_id,
        "produto_id": item.produto_id,
        "idtipoproduto": item.idtipoproduto,
        "loja_id": loja.loja_id,

        "nmproduto": (
            produto.nmproduto
            if produto
            else (item.dsobsitvenda or "Ingresso")
        ),
        "urlfotoproduto": (
            produto.urlfotoproduto
            if produto
            else ""
        ),
        "nmloja": loja.nmloja or "",
        "nmcliente": cliente.nmcliente or "",
        "dsobsitvenda": item.dsobsitvenda or "",

        "dtentregaitvenda": (
            item.dtentregaitvenda.isoformat()
            if item.dtentregaitvenda
            else None
        ),
        "nmuserentregaitvenda": item.nmuserentregaitvenda or "",
    }
