from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import Query

from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models.carrinho import Carrinho
from app.models.itcarrinho import ItCarrinho
from app.models.produto import Produto
from app.models.loja import Loja
from app.models.eventolote import EventoLote
from app.models.evento import Evento

from app.schemas.carrinho import AddItemIn, AddItemOut, CarrinhoItemAgrupadoOut,LojaCarrinhoOut,AlterarParticipanteIn


router = APIRouter(prefix="/carrinho", tags=["Carrinho"])


@router.post("/adicionar", response_model=AddItemOut)
def adicionar_item(payload: AddItemIn, db: Session = Depends(get_db)):


    def get_or_create_produto_por_lote(organizacao_id: int, loja_id: int, lote_id: int) -> Produto:


        # valida lote
        lote = (
            db.query(EventoLote)
            .filter(
                EventoLote.lote_id == lote_id,
                EventoLote.organizacao_id == organizacao_id,
                EventoLote.loja_id == loja_id,
                EventoLote.statuslote == "ATIVO",
            )
            .first()
        )
        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado ou inativo")

        # procura produto “espelho” pelo lote_id
        produto = (
            db.query(Produto)
            .filter(
                Produto.organizacao_id == organizacao_id,
                Produto.loja_id == loja_id,
                Produto.lote_id == lote_id,
                Produto.sitproduto == "ATIVO",
            )
            .first()
        )
        if produto:
            print("entrei na funcao produto por loja", produto)
            return produto

        evento = (
            db.query(Evento)
            .filter(Evento.evento_id == lote.evento_id)
            .first()
        )

        nome_evento   = evento.nmtituloevento if evento else "Evento"
        banner_evento = evento.urlbannerevento if evento else None

        # cria produto “espelho”
        produto = Produto(
            organizacao_id=organizacao_id,
            loja_id=loja_id,
            lote_id=lote_id,
            idtipoproduto="I",
            nmproduto=f"{nome_evento} - {lote.nmlote}",
            dsproduto=f"Ingresso para {nome_evento}",
            vrprecoprod=lote.vrprecolote,
            urlfotoproduto=banner_evento,
            sitproduto="ATIVO",
        )
        db.add(produto)

        try:
            db.flush()  # garante produto_id aqui
        except IntegrityError:
            db.rollback()
            produto = (
                db.query(Produto)
                .filter(
                    Produto.organizacao_id == organizacao_id,
                    Produto.loja_id == loja_id,
                    Produto.lote_id == lote_id,
                )
                .first()
            )
            if not produto:
                raise
        return produto
    # ----------------------------------- fim da função 
        
    if payload.idtipoproduto == "P" and not payload.produto_id:
        raise HTTPException(status_code=400, detail="produto_id obrigatório")

    if payload.idtipoproduto == "I" and not payload.lote_id:
        raise HTTPException(status_code=400, detail="lote_id obrigatório")

    # 1) define produto_id_final dependendo do tipo
    if payload.idtipoproduto == "P":
        produto = (
            db.query(Produto)
            .filter(
                Produto.produto_id == payload.produto_id,
                Produto.organizacao_id == payload.organizacao_id,
                Produto.loja_id == payload.loja_id,
                Produto.sitproduto == "ATIVO",
                Produto.idtipoproduto == "P",
            )
            .first()
        )
        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado ou inativo")
        produto_id_final = int(produto.produto_id)
        lote_id_final = None

    else:  # "I"
        produto_ingresso = get_or_create_produto_por_lote(
            organizacao_id=payload.organizacao_id,
            loja_id=payload.loja_id,
            lote_id=payload.lote_id,
        )
        produto_id_final = int(produto_ingresso.produto_id)
        lote_id_final = int(payload.lote_id)

    # 2) carrinho aberto do cliente
    carr = (
        db.query(Carrinho)
        .filter(
            Carrinho.cliente_id == payload.cliente_id,
            Carrinho.organizacao_id == payload.organizacao_id,
            Carrinho.loja_id == payload.loja_id,
            Carrinho.sitcarrinho == "ABERTO",
        )
        .first()
    )
    if not carr:
        carr = Carrinho(
            organizacao_id=payload.organizacao_id,
            loja_id=payload.loja_id,
            cliente_id=payload.cliente_id,
        )
        db.add(carr)
        db.flush()

    # 3) cria item (produto_id NOT NULL garantido)
    item = ItCarrinho(
        carrinho_id=int(carr.carrinho_id),
        produto_id=produto_id_final,
        qtitcarrinho=int(payload.qt),
        dsobsitcar=(payload.obs or None),
        lote_id=lote_id_final,  # ✅ NUNCA "" (string)
        # NOVOS CAMPOS
        nmparticipante=payload.nmparticipante,
        cpfparticipante=payload.cpfparticipante,        
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return AddItemOut(
        carrinho_id=int(carr.carrinho_id),
        itcarrinho_id=int(item.itcarrinho_id),
        produto_id=int(item.produto_id),
        qt=int(item.qtitcarrinho),
        obs=item.dsobsitcar,
        nmparticipante=item.nmparticipante,
        cpfparticipante=item.cpfparticipante,        

    )

@router.get("/qt")
def get_qt_carrinho_loja(cliente_id: int, loja_id: int, db: Session = Depends(get_db)):
    # 1) encontra carrinho único
    carr = (
        db.query(Carrinho)
        .filter(
            Carrinho.cliente_id == cliente_id,
            Carrinho.loja_id == loja_id,
            Carrinho.sitcarrinho == "ABERTO",
        )
        .first()
    )

    if not carr:
        return {"carrinho_id": None, "qt": 0}

    row = (
        db.query(
            func.coalesce(func.sum(ItCarrinho.qtitcarrinho), 0).label("qt"),
            func.coalesce(func.sum(ItCarrinho.qtitcarrinho * Produto.vrprecoprod), 0).label("total"),
        )
        .join(Produto, Produto.produto_id == ItCarrinho.produto_id)
        .filter(ItCarrinho.carrinho_id    == carr.carrinho_id)
        .first()
    )

    qt = int(row.qt or 0)
    total = float(row.total or 0.0)

    return {"carrinho_id": int(carr.carrinho_id), "qt": qt, "total": total}


@router.get("/qtde_itens_geral")
def get_qt_itens_geral(cliente_id: int, db: Session = Depends(get_db)):
    # Soma a quantidade de itens em todos os carrinhos ABERTOS do cliente
    row = (
        db.query(
            func.coalesce(func.sum(ItCarrinho.qtitcarrinho), 0).label("qt")
        )
        .join(Carrinho, Carrinho.carrinho_id == ItCarrinho.carrinho_id)
        .filter(
            Carrinho.cliente_id == cliente_id,
            Carrinho.sitcarrinho == "ABERTO"
        )
        .first()
    )

    qt = int(row.qt or 0)

    return {"qt_total": qt}

from datetime import datetime

def calcular_preco_final(produto: Produto):
    agora = datetime.now()

    tipodesconto = (produto.tipodesconto or "NENHUM").upper()
    vrdesconto = float(produto.vrdesconto or 0)
    vrprecoprod = float(produto.vrprecoprod or 0)

    dtini = produto.dtinidesconto
    dtfim = produto.dtfimdesconto

    desconto_ativo = False

    if tipodesconto != "NENHUM":
        dentro_periodo = True

        if dtini and agora < dtini:
            dentro_periodo = False

        if dtfim and agora > dtfim:
            dentro_periodo = False

        desconto_ativo = dentro_periodo

    if not desconto_ativo:
        return vrprecoprod, False

    if tipodesconto == "VALOR":
        vrprecofinal = max(0, vrprecoprod - vrdesconto)
    elif tipodesconto == "PERCENTUAL":
        vrprecofinal = max(0, vrprecoprod - (vrprecoprod * vrdesconto / 100))
    else:
        vrprecofinal = vrprecoprod

    return round(vrprecofinal, 2), True

# busca os itens do carrinho que pode ser produto ou ingresso
# falta colocar join para trazer a foto do evento quando o produto for ingresso.
@router.get("/itens")
def obter_itens_carrinho(
    request: Request,
    cliente_id: int,
    organizacao_id: int,
    loja_id: int,
    db: Session = Depends(get_db),
):
    carrinho = (
        db.query(Carrinho)
        .filter(
            Carrinho.cliente_id == cliente_id,
            Carrinho.organizacao_id == organizacao_id,
            Carrinho.loja_id == loja_id,
            Carrinho.sitcarrinho == "ABERTO",
        )
        .first()
    )

    if not carrinho:
        return {
            "carrinho_id": 0,
            "qt_total": 0,
            "total": 0,
            "itens": [],
        }

    itens_db = (
        db.query(
            ItCarrinho.itcarrinho_id,
            ItCarrinho.produto_id,
            Produto.nmproduto,
            Produto.dsproduto,
            Produto.vrprecoprod,
            Produto.urlfotoproduto,
            Produto.tipodesconto,
            Produto.vrdesconto,
            Produto.dtinidesconto,
            Produto.dtfimdesconto,
            Produto.idtipoproduto,
            ItCarrinho.qtitcarrinho,
            ItCarrinho.dsobsitcar,
            ItCarrinho.nmparticipante,
            ItCarrinho.cpfparticipante,
        )
        .join(Produto, Produto.produto_id == ItCarrinho.produto_id)
        .filter(ItCarrinho.carrinho_id == carrinho.carrinho_id)
        .all()
    )

    itens = []
    total = 0.0
    qt_total = 0

    for i in itens_db:
        class ProdutoTmp:
            pass

        produto_tmp = ProdutoTmp()
        produto_tmp.vrprecoprod = i.vrprecoprod
        produto_tmp.tipodesconto = i.tipodesconto
        produto_tmp.vrdesconto = i.vrdesconto
        produto_tmp.dtinidesconto = i.dtinidesconto
        produto_tmp.dtfimdesconto = i.dtfimdesconto

        vrprecofinal, descontoativo = calcular_preco_final(produto_tmp)

        qt = int(i.qtitcarrinho or 0)
        subtotal = float(vrprecofinal) * qt

        total += subtotal
        qt_total += qt

        tipo_produto = (i.idtipoproduto or "P").strip().upper()

        itens.append(
            {
                "itcarrinho_id": i.itcarrinho_id,
                "produto_id": i.produto_id,
                "nmproduto": i.nmproduto,
                "dsproduto": i.dsproduto,
                "idtipoproduto": tipo_produto,
                "vrprecoprod": float(i.vrprecoprod or 0),
                "vrprecofinal": float(vrprecofinal),
                "descontoativo": descontoativo,
                "tipodesconto": i.tipodesconto or "NENHUM",
                "vrdesconto": float(i.vrdesconto or 0),
                "urlfotoproduto": f"{i.urlfotoproduto}" if i.urlfotoproduto else "",
                "qt": qt,
                "observacao": i.dsobsitcar or "",
                "subtotal": round(subtotal, 2),
                "nmparticipante": i.nmparticipante,
                "cpfparticipante": i.cpfparticipante,
            }
        )

    return {
        "carrinho_id": carrinho.carrinho_id,
        "qt_total": qt_total,
        "total": round(total, 2),
        "itens": itens,
    }


@router.delete("/{carrinho_id}/produto/{produto_id}/um")
def remover_uma_unidade(
    carrinho_id: int,
    produto_id: int,
    observacao: str = Query(""),
    db: Session = Depends(get_db),
):
    observacao = (observacao or "").strip()

    res = db.execute(
        text("""
            DELETE FROM itcarrinho
            WHERE carrinho_id = :cid
              AND produto_id = :pid
              AND COALESCE(dsobsitcar, '') = :observacao
            ORDER BY dtcriacao DESC, itcarrinho_id DESC
            LIMIT 1
        """),
        {
            "cid": carrinho_id,
            "pid": produto_id,
            "observacao": observacao,
        },
    )
    db.commit()

    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Produto não encontrado no carrinho")

    return {"ok": True, "msg": "Removida 1 unidade do produto do carrinho"}


@router.post("/itens/{itcarrinho_id}/adicionar-um")
def adicionar_um_item_carrinho(itcarrinho_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("""
            SELECT itcarrinho_id
            FROM itcarrinho
            WHERE itcarrinho_id = :itcarrinho_id
        """),
        {"itcarrinho_id": itcarrinho_id}
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Item do carrinho não encontrado")

    db.execute(
        text("""
            INSERT INTO itcarrinho (
                carrinho_id,
                produto_id,
                lote_id,
                qtitcarrinho,
                dsobsitcar
            )
            SELECT
                carrinho_id,
                produto_id,
                lote_id,
                1,
                dsobsitcar
            FROM itcarrinho
            WHERE itcarrinho_id = :itcarrinho_id
        """),
        {"itcarrinho_id": itcarrinho_id}
    )

    db.commit()

    return {
        "ok": True,
        "mensagem": "Uma unidade adicionada ao carrinho"
    }



@router.get("/itens/agrupados", response_model=list[CarrinhoItemAgrupadoOut])
def get_itens_carrinho(
    cliente_id: int,
    organizacao_id: int,
    loja_id: int,
    db: Session = Depends(get_db),
):
    # (opcional) normaliza observação: NULL e "" viram ""
    # obs_norm = func.coalesce(func.nullif(ItCarrinho.dsobsitcar, ""), "")
    obs_norm = ItCarrinho.dsobsitcar

    q = (
        db.query(
            Carrinho.organizacao_id.label("organizacao_id"),
            Carrinho.loja_id.label("loja_id"),
            Carrinho.cliente_id.label("cliente_id"),
            Carrinho.carrinho_id.label("carrinho_id"),

            ItCarrinho.produto_id.label("produto_id"),
            obs_norm.label("dsobsitcar"),
            func.sum(ItCarrinho.qtitcarrinho).label("qtitcarrinho"),

            Produto.nmproduto.label("nmproduto"),
            Produto.vrprecoprod.label("vrprecoprod"),
            Produto.img.label("img"),
        )
        .join(ItCarrinho, ItCarrinho.carrinho_id == Carrinho.carrinho_id)
        .join(
            Produto,
            (Produto.produto_id == ItCarrinho.produto_id)
            & (Produto.organizacao_id == Carrinho.organizacao_id)
            & (Produto.loja_id == Carrinho.loja_id),
        )
        .filter(Carrinho.cliente_id == int(cliente_id))
        .filter(Carrinho.organizacao_id == int(organizacao_id))
        .filter(Carrinho.loja_id == int(loja_id))
        .filter(Carrinho.sitcarrinho == 'ABERTO')
        .group_by(
            Carrinho.organizacao_id,
            Carrinho.loja_id,
            Carrinho.cliente_id,
            Carrinho.carrinho_id,

            ItCarrinho.produto_id,
            obs_norm,

            Produto.nmproduto,
            Produto.vrprecoprod,
            Produto.img,
        )
        .order_by(Produto.nmproduto.asc(), obs_norm.asc())
    )

    rows = q.all()

    return [
        {
            "organizacao_id": r.organizacao_id,
            "loja_id": r.loja_id,
            "cliente_id": r.cliente_id,
            "carrinho_id": r.carrinho_id,
            "produto_id": r.produto_id,
            "dsobsitcar": r.dsobsitcar,
            "qtitcarrinho": int(r.qtitcarrinho or 0),
            "nmproduto": r.nmproduto,
            "vrprecoprod": float(r.vrprecoprod) if r.vrprecoprod is not None else None,
            "img": r.img,
        }
        for r in rows
    ]


@router.get("/lojas", response_model=list[LojaCarrinhoOut])
def get_lojas_com_carrinho(
    cliente_id: int,
    db: Session = Depends(get_db)
):
    rows = (
        db.query(
            Loja.loja_id.label("loja_id"),
            Loja.organizacao_id.label("organizacao_id"),
            Loja.nmloja.label("nmloja"),
            Loja.dsbairroloja.label("dsbairroloja"),
            Loja.urllogoloja.label("urllogoloja"),
            func.coalesce(func.sum(ItCarrinho.qtitcarrinho), 0).label("qt_itens"),
        )
        .join(Carrinho, Carrinho.loja_id == Loja.loja_id)
        .join(ItCarrinho, ItCarrinho.carrinho_id == Carrinho.carrinho_id)
        .filter(Carrinho.cliente_id == cliente_id)
        .filter(Carrinho.sitcarrinho == "ABERTO")
        .group_by(
            Loja.loja_id,
            Loja.organizacao_id,
            Loja.nmloja,
            Loja.dsbairroloja,
            Loja.urllogoloja,
        )
        .order_by(Loja.nmloja.asc())
        .all()
    )

    return [
        LojaCarrinhoOut(
            loja_id=row.loja_id,
            organizacao_id=row.organizacao_id,
            nmloja=row.nmloja,
            dsbairroloja=row.dsbairroloja,
            urllogoloja=row.urllogoloja,
            total_itens=int(row.qt_itens or 0),
        )
        for row in rows
    ]

@router.put("/itcarrinho/{itcarrinho_id}/participante")
def alterar_participante_itcarrinho(
    itcarrinho_id: int,
    payload: AlterarParticipanteIn,
    db: Session = Depends(get_db),
):
    nome = payload.nmparticipante.strip()
    cpf = "".join(ch for ch in payload.cpfparticipante if ch.isdigit())

    if not nome:
        raise HTTPException(status_code=400, detail="Nome do participante obrigatório")

    if len(cpf) != 11:
        raise HTTPException(status_code=400, detail="CPF do participante inválido")

    item = db.query(ItCarrinho).filter(ItCarrinho.itcarrinho_id == itcarrinho_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item do carrinho não encontrado")

    item.nmparticipante = nome
    item.cpfparticipante = cpf

    db.commit()
    db.refresh(item)

    return {
        "ok": True,
        "tipo": "itcarrinho",
        "itcarrinho_id": item.itcarrinho_id,
        "nmparticipante": item.nmparticipante,
        "cpfparticipante": item.cpfparticipante,
    }