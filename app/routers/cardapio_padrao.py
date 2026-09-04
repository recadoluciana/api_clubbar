from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.permissoes_loja import validar_gerenciamento_organizacao, validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.cardapio_padrao import CardapioPadraoCategoria, CardapioPadraoProduto
from app.models.categoria import Categoria
from app.models.loja import Loja
from app.models.produto import Produto


router = APIRouter(tags=["Cardápio padrão"])


def _validar_organizacao(usuario: dict, organizacao_id: int, *, exige_acesso_geral: bool = False):
    validar_gerenciamento_organizacao(usuario, organizacao_id)
    if int(usuario.get("organizacao_id") or 0) != int(organizacao_id):
        raise HTTPException(403, "O cadastro não pertence à sua organização.")
    if exige_acesso_geral and usuario.get("loja_id") is not None:
        raise HTTPException(403, "Somente administradores com acesso geral podem definir o cardápio padrão.")


@router.get("/organizacoes/{organizacao_id}/cardapio-padrao")
def consultar_cardapio_padrao(
    organizacao_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    _validar_organizacao(usuario, organizacao_id)
    categorias = (
        db.query(CardapioPadraoCategoria)
        .filter(CardapioPadraoCategoria.organizacao_id == organizacao_id)
        .order_by(CardapioPadraoCategoria.idordcategoria, CardapioPadraoCategoria.nmcategoria)
        .all()
    )
    produtos = (
        db.query(CardapioPadraoProduto)
        .filter(CardapioPadraoProduto.organizacao_id == organizacao_id)
        .order_by(CardapioPadraoProduto.nmproduto)
        .all()
    )
    nomes_categorias = {c.cardapio_padrao_categoria_id: c.nmcategoria for c in categorias}
    return {
        "organizacao_id": organizacao_id,
        "quantidade_categorias": len(categorias),
        "quantidade_produtos": len(produtos),
        "categorias": [
            {
                "cardapio_padrao_categoria_id": c.cardapio_padrao_categoria_id,
                "nmcategoria": c.nmcategoria,
                "sitcategoria": c.sitcategoria,
                "idordcategoria": c.idordcategoria,
            }
            for c in categorias
        ],
        "produtos": [
            {
                "cardapio_padrao_produto_id": p.cardapio_padrao_produto_id,
                "cardapio_padrao_categoria_id": p.cardapio_padrao_categoria_id,
                "nmcategoria": nomes_categorias.get(p.cardapio_padrao_categoria_id),
                "nmproduto": p.nmproduto,
                "dsproduto": p.dsproduto,
                "vrprecoprod": float(p.vrprecoprod),
                "sitproduto": p.sitproduto,
                "urlfotoproduto": p.urlfotoproduto,
            }
            for p in produtos
        ],
    }


@router.post("/organizacoes/{organizacao_id}/cardapio-padrao/copiar-da-loja/{loja_id}")
def copiar_loja_para_cardapio_padrao(
    organizacao_id: int,
    loja_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    _validar_organizacao(usuario, organizacao_id, exige_acesso_geral=True)
    loja = db.query(Loja).filter(Loja.loja_id == loja_id, Loja.organizacao_id == organizacao_id).first()
    if not loja:
        raise HTTPException(404, "Estabelecimento não encontrado nesta organização.")

    categorias_origem = (
        db.query(Categoria)
        .filter(Categoria.organizacao_id == organizacao_id, Categoria.loja_id == loja_id)
        .order_by(Categoria.idordcategoria, Categoria.nmcategoria)
        .all()
    )
    produtos_origem = (
        db.query(Produto)
        .filter(Produto.organizacao_id == organizacao_id, Produto.loja_id == loja_id, Produto.idtipoproduto == "P")
        .all()
    )
    if not categorias_origem and not produtos_origem:
        raise HTTPException(422, "O estabelecimento escolhido ainda não possui um cardápio para copiar.")

    try:
        db.query(CardapioPadraoProduto).filter(CardapioPadraoProduto.organizacao_id == organizacao_id).delete()
        db.query(CardapioPadraoCategoria).filter(CardapioPadraoCategoria.organizacao_id == organizacao_id).delete()
        db.flush()

        categorias_destino = {}
        for categoria in categorias_origem:
            nova = CardapioPadraoCategoria(
                organizacao_id=organizacao_id,
                nmcategoria=categoria.nmcategoria,
                sitcategoria=categoria.sitcategoria,
                idordcategoria=categoria.idordcategoria,
            )
            db.add(nova)
            db.flush()
            categorias_destino[categoria.categoria_id] = nova.cardapio_padrao_categoria_id

        for produto in produtos_origem:
            db.add(CardapioPadraoProduto(
                organizacao_id=organizacao_id,
                cardapio_padrao_categoria_id=categorias_destino.get(produto.categoria_id),
                nmproduto=produto.nmproduto,
                dsproduto=produto.dsproduto,
                vrprecoprod=produto.vrprecoprod,
                sitproduto=produto.sitproduto,
                urlfotoproduto=produto.urlfotoproduto,
                tipodesconto=produto.tipodesconto or "NENHUM",
                vrdesconto=produto.vrdesconto or 0,
                pccashback=produto.pccashback,
                dtinidesconto=produto.dtinidesconto,
                dtfimdesconto=produto.dtfimdesconto,
            ))
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "mensagem": f'Cardápio de "{loja.nmloja}" definido como padrão da organização.',
        "quantidade_categorias": len(categorias_origem),
        "quantidade_produtos": len(produtos_origem),
    }


@router.post("/lojas/{loja_id}/cardapio-padrao/importar")
def importar_cardapio_padrao(
    loja_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(404, "Estabelecimento não encontrado.")
    validar_mutacao_loja(usuario, loja.organizacao_id, loja_id)

    categorias_padrao = db.query(CardapioPadraoCategoria).filter(
        CardapioPadraoCategoria.organizacao_id == loja.organizacao_id
    ).all()
    produtos_padrao = db.query(CardapioPadraoProduto).filter(
        CardapioPadraoProduto.organizacao_id == loja.organizacao_id
    ).all()
    if not categorias_padrao and not produtos_padrao:
        raise HTTPException(422, "A organização ainda não possui um cardápio padrão.")

    categorias_loja = db.query(Categoria).filter(Categoria.loja_id == loja_id).all()
    categorias_por_nome = {c.nmcategoria.strip().casefold(): c for c in categorias_loja}
    mapa_categorias = {}
    categorias_criadas = 0
    produtos_criados = 0
    produtos_ignorados = 0

    try:
        for padrao in categorias_padrao:
            chave = padrao.nmcategoria.strip().casefold()
            destino = categorias_por_nome.get(chave)
            if destino is None:
                destino = Categoria(
                    organizacao_id=loja.organizacao_id,
                    loja_id=loja_id,
                    nmcategoria=padrao.nmcategoria,
                    sitcategoria=padrao.sitcategoria,
                    idordcategoria=padrao.idordcategoria,
                )
                db.add(destino)
                db.flush()
                categorias_por_nome[chave] = destino
                categorias_criadas += 1
            mapa_categorias[padrao.cardapio_padrao_categoria_id] = destino.categoria_id

        nomes_existentes = {
            p.nmproduto.strip().casefold()
            for p in db.query(Produto).filter(Produto.loja_id == loja_id, Produto.idtipoproduto == "P").all()
        }
        for padrao in produtos_padrao:
            chave = padrao.nmproduto.strip().casefold()
            if chave in nomes_existentes:
                produtos_ignorados += 1
                continue
            db.add(Produto(
                organizacao_id=loja.organizacao_id,
                loja_id=loja_id,
                categoria_id=mapa_categorias.get(padrao.cardapio_padrao_categoria_id),
                nmproduto=padrao.nmproduto,
                dsproduto=padrao.dsproduto,
                vrprecoprod=padrao.vrprecoprod,
                sitproduto=padrao.sitproduto,
                idtipoproduto="P",
                lote_id=None,
                urlfotoproduto=padrao.urlfotoproduto,
                tipodesconto=padrao.tipodesconto or "NENHUM",
                vrdesconto=padrao.vrdesconto or 0,
                pccashback=padrao.pccashback,
                dtinidesconto=padrao.dtinidesconto,
                dtfimdesconto=padrao.dtfimdesconto,
            ))
            nomes_existentes.add(chave)
            produtos_criados += 1
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "mensagem": "Cardápio padrão importado. Os itens desta loja já podem ser alterados independentemente.",
        "categorias_criadas": categorias_criadas,
        "produtos_criados": produtos_criados,
        "produtos_ignorados": produtos_ignorados,
    }
