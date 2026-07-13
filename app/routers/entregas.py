# app/routers/entregas.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from datetime import datetime, date
from sqlalchemy import or_, case

from app.database import get_db
from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.produto import Produto
from app.models.loja import Loja
from app.models.cliente import Cliente
from app.models.usuario import Usuario

from app.schemas.entregas import LojaRetiradaOut,AlterarParticipanteIn
from datetime import datetime
    
router = APIRouter(prefix="/entregas", tags=["entregas"])


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

    hoje = date.today()

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
        .filter(Venda.cliente_id == cliente_id)
        .filter(Venda.sitvenda == "PAGA")
        .filter(ItVenda.identregaitvenda == "NAO")
        .filter(
            or_(
                ItVenda.dtexpiraitvenda.is_(None),
                ItVenda.dtexpiraitvenda >= date.today()
            )
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
            "dtcriacao": row.dtcriacao,
            "dtcriacao_fmt": row.dtcriacao.strftime("%d/%m/%Y") if row.dtcriacao else None,
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
            .filter(
                Venda.cliente_id == cliente_id,
                Venda.sitvenda == "PAGA",
                ItVenda.identregaitvenda == "NAO",
            )
            .filter(
                (ItVenda.dtexpiraitvenda == None)
                | (ItVenda.dtexpiraitvenda >= func.current_date())
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
        .filter(Venda.cliente_id == cliente_id)
        .filter(Venda.sitvenda == "PAGA")
        .filter(ItVenda.identregaitvenda == "NAO")
        .filter(
            (ItVenda.dtexpiraitvenda == None) |
            (ItVenda.dtexpiraitvenda >= func.current_date())
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
    db: Session = Depends(get_db),
):
    token = token.strip()

    item = (
        db.query(ItVenda)
        .filter(ItVenda.qrtokenitvenda == token)
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado ou QR Code inválido.",
        )

    return {
        "itvenda_id": item.itvenda_id,
        "nmproduto": item.nmproduto,
        "qtitvenda": item.qtitvenda,
        "dsobsitvenda": item.dsobsitvenda or "",
        "nmparticipante": item.nmparticipante or "",
        "cpfparticipante": item.cpfparticipante or "",
        "identregaitvenda": item.identregaitvenda or "NAO",
        "dtentregaitvenda": (
            item.dtentregaitvenda.isoformat()
            if item.dtentregaitvenda
            else None
        ),
        "disponivel": item.identregaitvenda != "SIM",
    }

@router.post("/entregar-por-token/{token}")
def entregar_produto_por_token(
    token: str,
    usuario_id: int,
    db: Session = Depends(get_db),
):
    token = token.strip()

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

    quantidade_atualizada = (
        db.query(ItVenda)
        .filter(ItVenda.qrtokenitvenda == token)
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

        item = (
            db.query(ItVenda)
            .filter(ItVenda.qrtokenitvenda == token)
            .first()
        )

        if not item:
            raise HTTPException(
                status_code=404,
                detail="Produto não encontrado ou QR Code inválido.",
            )

        raise HTTPException(
            status_code=409,
            detail="Este produto já foi utilizado.",
        )

    db.commit()

    item = (
        db.query(ItVenda)
        .filter(ItVenda.qrtokenitvenda == token)
        .first()
    )

    return {
        "ok": True,
        "msg": "Produto entregue com sucesso.",
        "itvenda_id": item.itvenda_id,
        "nmproduto": item.nmproduto,
        "dtentregaitvenda": (
            item.dtentregaitvenda.isoformat()
            if item.dtentregaitvenda
            else None
        ),
        "nmuserentregaitvenda": item.nmuserentregaitvenda,
    }