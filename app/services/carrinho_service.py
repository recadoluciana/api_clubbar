from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.carrinho import Carrinho
from app.models.itcarrinho import ItCarrinho
from app.models.produto import Produto
from app.models.loja import Loja
from app.models.cardapio import Cardapio, CardapioItem, CardapioVersao
from app.services.taxa_service import calcular_taxa_ingresso_unitaria
from decimal import Decimal

def _preco_final(base, tipo, desconto, inicio, fim, agora):
    valor = Decimal(str(base or 0))
    tipo = (tipo or "NENHUM").upper()
    desconto = Decimal(str(desconto or 0))
    ativo = tipo != "NENHUM" and (not inicio or inicio <= agora) and (not fim or fim >= agora)
    if not ativo:
        return valor.quantize(Decimal("0.01"))
    if tipo == "VALOR":
        valor = max(Decimal("0"), valor - desconto)
    elif tipo == "PERCENTUAL":
        valor = max(Decimal("0"), valor - valor * desconto / Decimal("100"))
    return valor.quantize(Decimal("0.01"))


def revalidar_precos_carrinho(db: Session, carrinho: Carrinho) -> list[dict]:
    """Atualiza snapshots vencidos sem retirar itens quando o cardápio muda."""
    agora = datetime.now()
    itens = db.query(ItCarrinho).filter(ItCarrinho.carrinho_id == carrinho.carrinho_id).all()
    alteracoes = []
    for item in itens:
        produto = db.query(Produto).filter(Produto.produto_id == item.produto_id).first()
        if not produto or (produto.sitproduto or "").upper() != "ATIVO":
            continue
        item_atual = (
            db.query(CardapioItem)
            .join(CardapioVersao, CardapioVersao.cardapioversao_id == CardapioItem.cardapioversao_id)
            .join(Cardapio, Cardapio.cardapio_id == CardapioVersao.cardapio_id)
            .filter(
                CardapioItem.produto_id == item.produto_id,
                CardapioItem.sititem == "ATIVO",
                Cardapio.loja_id == carrinho.loja_id,
                Cardapio.sitcardapio == "ATIVO",
                CardapioVersao.statusversao.in_(["PUBLICADA", "PROGRAMADA"]),
                (CardapioVersao.dtiniciovigencia.is_(None)) | (CardapioVersao.dtiniciovigencia <= agora),
                (CardapioVersao.dtfimvigencia.is_(None)) | (CardapioVersao.dtfimvigencia >= agora),
            )
            .order_by(Cardapio.prioridade.desc(), CardapioVersao.nrversao.desc())
            .first()
        )
        origem = item_atual or produto
        novo = _preco_final(
            getattr(origem, "vrpreco", None) if item_atual else produto.vrprecoprod,
            getattr(origem, "tipodesconto", None),
            getattr(origem, "vrdesconto", None),
            getattr(origem, "dtinidesconto", None),
            getattr(origem, "dtfimdesconto", None),
            agora,
        )
        anterior = Decimal(str(item.vrunitario or 0)).quantize(Decimal("0.01"))
        item.vrunitario = novo
        if item_atual:
            item.cardapioitem_id = item_atual.cardapioitem_id
        if anterior != novo:
            alteracoes.append({
                "produto_id": int(item.produto_id),
                "nmproduto": produto.nmproduto,
                "preco_anterior": float(anterior),
                "preco_atual": float(novo),
            })
    if itens:
        db.flush()
    unicas = {}
    for alteracao in alteracoes:
        unicas[alteracao["produto_id"]] = alteracao
    return list(unicas.values())


def limpar_itens_indisponiveis(
    db: Session,
    carrinho_id: int,
    loja_id: int,
) -> int:
    """Mantido por compatibilidade; mudanças de cardápio não apagam o carrinho."""
    return 0


def limpar_carrinhos_abertos_cliente(db: Session, cliente_id: int) -> int:
    carrinhos = (
        db.query(Carrinho)
        .filter(
            Carrinho.cliente_id == cliente_id,
            Carrinho.sitcarrinho == "ABERTO",
        )
        .all()
    )
    total_removidos = sum(
        limpar_itens_indisponiveis(
            db,
            int(carrinho.carrinho_id),
            int(carrinho.loja_id),
        )
        for carrinho in carrinhos
    )
    if total_removidos:
        db.commit()
    return total_removidos

def get_carrinho(
    db: Session,
    cliente_id: int,
    loja_id: int,
    usuario_id: int | None = None,
) -> dict:
    # 1) acha carrinho ABERTO do cliente (trava o registro)
    carrinho_selec = (
        db.query(Carrinho)
        .filter(
            Carrinho.loja_id == loja_id,
            Carrinho.cliente_id == cliente_id,
            Carrinho.usuario_id == usuario_id,
            Carrinho.sitcarrinho == "ABERTO",
        )
        .with_for_update()
        .first()
    )
    if not carrinho_selec:
        raise HTTPException(status_code=404, detail="Carrinho não encontrado (ABERTO)")

    revalidar_precos_carrinho(db, carrinho_selec)
    db.commit()

    # 2) busca itens do carrinho
    itens_car = (
        db.query(ItCarrinho)
        .filter(
            ItCarrinho.carrinho_id == carrinho_selec.carrinho_id,
            ItCarrinho.carrinho_id == Carrinho.carrinho_id
        )
        .all()
    )
    if not itens_car:
        raise HTTPException(status_code=400, detail="Carrinho sem itens")

    # 3) buscar na loja a taxa de ingresso e taxa de produto para armazenar como histórico
    loja_car = (
        db.query(Loja)
        .filter(
            Loja.loja_id == loja_id
        )
        .first()
    )
    if not loja_car:
        raise HTTPException(status_code=400, detail="Loja não encontrada")

    # 4) pega todos os produtos de uma vez (evita N+1 queries)
    produto_ids = list({it.produto_id for it in itens_car if it.produto_id is not None})
    produtos = (
        db.query(Produto)
        .filter(Produto.produto_id.in_(produto_ids))
        .all()
    )
    map_prod = {p.produto_id: p for p in produtos}

    itens_agrupados = {}
    qt_total = 0
    total = 0.0
    percentual_taxa = 0.0
    valor_taxa = 0.0

    for it in itens_car:
        qt_aux = int(getattr(it, "qtitcarrinho", 1) or 1)

        prod = map_prod.get(it.produto_id)
        if not prod:
            raise HTTPException(
                status_code=400,
                detail=f"Produto {it.produto_id} não encontrado para item do carrinho",
            )

        nmproduto     = getattr(prod, "nmproduto", "Produto")
        vrprecoprod   = float(it.vrunitario or 0)
        idtipoproduto = (getattr(prod, "idtipoproduto", "P") or "P").upper()

        subtotal = round(vrprecoprod * qt_aux, 2)
        qt_total += qt_aux
        total    += subtotal

        if idtipoproduto == "I":
            percentual_taxa = round(float(getattr(loja_car, "vrtaxaing", 0) or 0), 2)
            taxa_unitaria = calcular_taxa_ingresso_unitaria(
                Decimal(str(vrprecoprod)), Decimal(str(percentual_taxa)),
                Decimal(str(getattr(loja_car, "vrtaxaminimaingresso", 0) or 0)),
            )
            valor_taxa = float(taxa_unitaria * qt_aux)
        else:
            percentual_taxa = round(float(getattr(loja_car, "vrtaxaprod", 0) or 0), 2)
            valor_taxa = round(subtotal * (percentual_taxa / 100), 2)

        observacao = (getattr(it, "dsobsitcar", None) or "").strip()
        cardapioitem_id = getattr(it, "cardapioitem_id", None)
        chave = (int(it.produto_id), cardapioitem_id, observacao, vrprecoprod)
        if chave not in itens_agrupados:
            itens_agrupados[chave] = {
                "itcarrinho_id": it.itcarrinho_id,
                "produto_id": it.produto_id,
                "cardapioitem_id": cardapioitem_id,
                "nmproduto": nmproduto,
                "vrprecoprod": vrprecoprod,
                "qtitcarrinho": qt_aux,
                "dsobsitcar": observacao or None,
                "nmparticipante": it.nmparticipante,
                "cpfparticipante": it.cpfparticipante,
                "subtotal": subtotal,
                "idtipoproduto": idtipoproduto,
                "lote_id": getattr(it, "lote_id", None),
                "pctaxaitvenda": percentual_taxa,
                "vrtaxaitvenda": valor_taxa,
            }
        else:
            agrupado = itens_agrupados[chave]
            agrupado["qtitcarrinho"] += qt_aux
            agrupado["subtotal"] = round(agrupado["subtotal"] + subtotal, 2)
            agrupado["vrtaxaitvenda"] = round(
                agrupado["vrtaxaitvenda"] + valor_taxa, 2
            )

    itens_out = list(itens_agrupados.values())

    return {
        "carrinho_id": carrinho_selec.carrinho_id,
        "organizacao_id": carrinho_selec.organizacao_id,
        "usuario_id": carrinho_selec.usuario_id,
        "qt_total": qt_total,
        "total": total,
        "itens": itens_out,
    }
