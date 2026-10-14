from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Request
from sqlalchemy.orm import Session
from sqlalchemy import exists, func
import os
import uuid
import shutil
import traceback

from app.database import get_db
from app.models.categoria import Categoria
from app.models.cardapio_padrao import ProdutoCategoriaOrg
from app.models.cardapio import Cardapio, CardapioItem, CardapioLoja, CardapioProgramacao, CardapioVersao, CardapioVersaoCategoria
from app.models.produto import Produto
from app.models.itvenda import ItVenda
from app.models.itcarrinho import ItCarrinho
from app.models.loja import Loja
from app.models.organizacao import Organizacao
from app.models.venda import Venda
from app.core.config import UPLOAD_PRODUTOS
from app.core.security import get_usuario_logado
from app.core.permissoes_loja import validar_gerenciamento_organizacao, validar_mutacao_loja
from app.utils.datetime_utils import FUSO_BRASIL

router = APIRouter(tags=["Produtos"])

os.makedirs(UPLOAD_PRODUTOS, exist_ok=True)


def _categoria_catalogo(db: Session, produto_id: int):
    return db.query(ProdutoCategoriaOrg.categoria_id, Categoria.nmcategoria).join(
        Categoria, Categoria.categoria_id == ProdutoCategoriaOrg.categoria_id
    ).filter(ProdutoCategoriaOrg.produto_id == produto_id).order_by(ProdutoCategoriaOrg.categoria_id).first()


def _definir_categoria_catalogo(db: Session, produto_id: int, categoria_id: int):
    db.query(ProdutoCategoriaOrg).filter(ProdutoCategoriaOrg.produto_id == produto_id).delete(synchronize_session=False)
    db.add(ProdutoCategoriaOrg(produto_id=produto_id, categoria_id=categoria_id))


def _parse_datetime(valor: str | None):
    if not valor:
        return None
    valor = valor.strip()
    if not valor:
        return None

    formatos = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formatos:
        try:
            return datetime.strptime(valor, fmt)
        except ValueError:
            pass

    raise HTTPException(
        status_code=400,
        detail=f"Data inválida: {valor}. Use formato YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS"
    )


def calcular_preco_final(
    preco_base,
    *,
    tipodesconto=None,
    vrdesconto=None,
    dtinidesconto=None,
    dtfimdesconto=None,
):
    agora = datetime.now(FUSO_BRASIL).replace(tzinfo=None)

    tipodesconto = (tipodesconto or "NENHUM").upper()
    vrdesconto = float(vrdesconto or 0)
    vrprecoprod = float(preco_base or 0)

    dtini = dtinidesconto
    dtfim = dtfimdesconto

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


def _programacao_vigente(programacao: CardapioProgramacao, agora: datetime) -> bool:
    if programacao.sitprogramacao != "ATIVA":
        return False
    if programacao.diasemana and programacao.diasemana != agora.isoweekday():
        return False
    if programacao.dtinicio and agora.date() < programacao.dtinicio:
        return False
    if programacao.dtfim and agora.date() > programacao.dtfim:
        return False
    if programacao.hrinicio and agora.time() < programacao.hrinicio:
        return False
    if programacao.hrfim and agora.time() > programacao.hrfim:
        return False
    return True


def _itens_cardapio_em_exibicao(db: Session, loja_id: int, agora: datetime) -> dict[int, CardapioItem]:
    cardapios = db.query(CardapioLoja, Cardapio).join(
        Cardapio, Cardapio.cardapio_id == CardapioLoja.cardapio_id,
    ).filter(
        CardapioLoja.loja_id == loja_id,
        CardapioLoja.sitassociacao == "ATIVA",
        Cardapio.sitcardapio == "ATIVO",
    ).order_by(CardapioLoja.prioridade.desc()).all()
    candidatos: list[tuple[CardapioLoja, Cardapio, CardapioVersao]] = []
    for associacao, cardapio in cardapios:
        programacoes = db.query(CardapioProgramacao).filter(
            CardapioProgramacao.cardapioloja_id == associacao.cardapioloja_id,
        ).all()
        if cardapio.tipocardapio != "PRINCIPAL" and not any(
            _programacao_vigente(programacao, agora)
            for programacao in programacoes
        ):
            continue
        versao = db.query(CardapioVersao).filter(
            CardapioVersao.cardapio_id == cardapio.cardapio_id,
            CardapioVersao.statusversao.in_(["PUBLICADA", "PROGRAMADA"]),
            func.coalesce(CardapioVersao.dtiniciovigencia, agora) <= agora,
            (CardapioVersao.dtfimvigencia.is_(None)) |
                (CardapioVersao.dtfimvigencia >= agora),
        ).order_by(CardapioVersao.nrversao.desc()).first()
        if versao:
            candidatos.append((associacao, cardapio, versao))

    if not candidatos:
        return {}
    sazonais = [item for item in candidatos if item[1].tipocardapio != "PRINCIPAL"]
    _, _, versao = max(sazonais or candidatos, key=lambda item: item[0].prioridade)
    itens = db.query(CardapioItem).filter(
        CardapioItem.cardapioversao_id == versao.cardapioversao_id,
        CardapioItem.sititem == "ATIVO",
    ).all()
    return {item.produto_id: item for item in itens}


@router.get("/produtos/mais-vendidos")
def listar_produtos_mais_vendidos(
    limite: int = 10,
    db: Session = Depends(get_db),
):
    limite = max(1, min(limite, 50))
    quantidade = func.count(ItVenda.itvenda_id).label("quantidade_vendida")

    rows = (
        db.query(Produto, Loja.loja_id, Loja.nmloja, quantidade)
        .join(ItVenda, ItVenda.produto_id == Produto.produto_id)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(Loja, Loja.loja_id == Venda.loja_id)
        .join(
            Organizacao,
            Organizacao.organizacao_id == Produto.organizacao_id,
        )
        .filter(
            Venda.sitvenda == "PAGA",
            ItVenda.sititvenda == "ATIVO",
            Produto.sitproduto == "ATIVO",
            Loja.sitloja == "ATIVA",
            Organizacao.sitorganizacao == "ATIVA",
        )
        .group_by(Produto.produto_id, Loja.loja_id, Loja.nmloja)
        .order_by(quantidade.desc(), Produto.nmproduto.asc())
        .all()
    )

    agora = datetime.now(FUSO_BRASIL).replace(tzinfo=None)
    cardapios_por_loja: dict[int, dict[int, CardapioItem]] = {}
    resultado = []
    for produto, loja_id, nmloja, quantidade_vendida in rows:
        loja_id = int(loja_id)
        itens_exibidos = cardapios_por_loja.get(loja_id)
        if itens_exibidos is None:
            itens_exibidos = _itens_cardapio_em_exibicao(db, loja_id, agora)
            cardapios_por_loja[loja_id] = itens_exibidos
        item_cardapio = itens_exibidos.get(produto.produto_id)
        if item_cardapio is None:
            continue
        vrprecofinal, descontoativo = calcular_preco_final(
            item_cardapio.vrpreco,
            tipodesconto=item_cardapio.tipodesconto,
            vrdesconto=item_cardapio.vrdesconto,
            dtinidesconto=item_cardapio.dtinidesconto,
            dtfimdesconto=item_cardapio.dtfimdesconto,
        )
        resultado.append(
            {
                "produto_id": produto.produto_id,
                "organizacao_id": produto.organizacao_id,
                "loja_id": loja_id,
                "nmloja": nmloja,
                "nmproduto": produto.nmproduto,
                "dsproduto": produto.dsproduto or "",
                "vrprecoprod": float(item_cardapio.vrpreco),
                "vrprecofinal": vrprecofinal,
                "descontoativo": descontoativo,
                "urlfotoproduto": produto.urlfotoproduto,
                "quantidade_vendida": int(quantidade_vendida or 0),
            }
        )

    return resultado[:limite]


@router.delete("/produtos/{produto_id}")
def excluir_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    produto = db.query(Produto).filter(
        Produto.produto_id == produto_id
    ).first()

    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    validar_gerenciamento_organizacao(usuario, produto.organizacao_id)

    usado_itcarrinho = db.query(
        exists().where(ItCarrinho.produto_id == produto_id)
    ).scalar()

    usado_itvenda = db.query(
        exists().where(ItVenda.produto_id == produto_id)
    ).scalar()

    usado_cardapio = db.query(CardapioItem).filter(
        CardapioItem.produto_id == produto_id
    ).first()

    if usado_cardapio:
        raise HTTPException(status_code=409, detail="Remova o produto dos cardápios antes de excluí-lo. Como alternativa, inative-o.")

    if usado_itcarrinho or usado_itvenda:
        raise HTTPException(
            status_code=400,
            detail="Este produto já foi utilizado em vendas/carrinhos e não pode ser excluído"
        )

    db.delete(produto)
    db.commit()

    return {"message": "Produto excluído com sucesso. Consulte seu cadastro."}


@router.put("/produtos/{produto_id}")
def atualizar_produto(
    produto_id: int,
    categoria_id: int | None = Form(None),
    nmproduto: str | None = Form(None),
    dsproduto: str | None = Form(None),
    sitproduto: str | None = Form(None),
    urlfotoproduto: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    try:
        produto = db.query(Produto).filter(
            Produto.produto_id == produto_id
        ).first()

        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        validar_gerenciamento_organizacao(usuario, produto.organizacao_id)

        if urlfotoproduto is not None and urlfotoproduto.filename:
            if not urlfotoproduto.content_type or not urlfotoproduto.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Arquivo deve ser imagem")

            extensao = os.path.splitext(urlfotoproduto.filename)[1].lower()
            nome_arquivo = f"{uuid.uuid4().hex}{extensao}"
            caminho_arquivo = UPLOAD_PRODUTOS / nome_arquivo

            with open(caminho_arquivo, "wb") as buffer:
                shutil.copyfileobj(urlfotoproduto.file, buffer)

            produto.urlfotoproduto = f"/uploads/produtos/{nome_arquivo}"

        if categoria_id is not None:
            categoria = db.query(Categoria).filter(
                Categoria.categoria_id == categoria_id,
                Categoria.organizacao_id == produto.organizacao_id,
            ).first()
            if not categoria:
                raise HTTPException(status_code=404, detail="Categoria não encontrada para esta organização.")
            _definir_categoria_catalogo(db, produto.produto_id, categoria_id)

        if nmproduto is not None:
            nmproduto = nmproduto.strip()
            if not nmproduto:
                raise HTTPException(status_code=400, detail="Nome do produto é obrigatório.")
            produto.nmproduto = nmproduto

        if dsproduto is not None:
            produto.dsproduto = dsproduto

        if sitproduto is not None:
            produto.sitproduto = sitproduto

        db.commit()
        db.refresh(produto)

        categoria_atual = _categoria_catalogo(db, produto.produto_id)
        return {
            "mensagem": "Produto atualizado com sucesso",
            "produto_id": produto.produto_id,
            "organizacao_id": produto.organizacao_id,
            "categoria_id": categoria_atual.categoria_id if categoria_atual else None,
            "nmproduto": produto.nmproduto,
            "dsproduto": produto.dsproduto,
            "sitproduto": produto.sitproduto,
            "urlfotoproduto": produto.urlfotoproduto,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar produto: {str(e)}")


# Produtos vinculados à versão mais recente dos cardápios desta loja.
@router.get("/lojas/{loja_id}/produtos")
def listar_produtos_por_loja(
    loja_id: int,
    incluir_inativos: bool = False,
    db: Session = Depends(get_db),
):
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    ultima_versao = (
        db.query(
            CardapioVersao.cardapio_id.label("cardapio_id"),
            func.max(CardapioVersao.nrversao).label("nrversao"),
        )
        .group_by(CardapioVersao.cardapio_id)
        .subquery()
    )
    query = (
        db.query(Produto, Categoria, CardapioItem)
        .join(CardapioItem, CardapioItem.produto_id == Produto.produto_id)
        .join(CardapioVersao, CardapioVersao.cardapioversao_id == CardapioItem.cardapioversao_id)
        .join(ultima_versao, (ultima_versao.c.cardapio_id == CardapioVersao.cardapio_id) & (ultima_versao.c.nrversao == CardapioVersao.nrversao))
        .join(Cardapio, Cardapio.cardapio_id == CardapioVersao.cardapio_id)
        .join(CardapioLoja, CardapioLoja.cardapio_id == Cardapio.cardapio_id)
        .join(CardapioVersaoCategoria, CardapioVersaoCategoria.cardapioversaocategoria_id == CardapioItem.cardapioversaocategoria_id)
        .join(Categoria, Categoria.categoria_id == CardapioVersaoCategoria.categoria_id)
        .filter(CardapioLoja.loja_id == loja_id, CardapioLoja.sitassociacao == "ATIVA", Cardapio.organizacao_id == loja.organizacao_id, Produto.organizacao_id == loja.organizacao_id, Categoria.organizacao_id == loja.organizacao_id)
    )

    if not incluir_inativos:
        query = query.filter(Produto.sitproduto == "ATIVO")

    rows = query.order_by(Produto.nmproduto.asc(), Categoria.nmcategoria.asc()).all()

    saida = []
    produtos_listados = {}

    for produto, categoria, item in rows:
        if produto.produto_id in produtos_listados:
            existente = produtos_listados[produto.produto_id]
            if categoria.categoria_id not in existente["categoria_ids"]:
                existente["categoria_ids"].append(categoria.categoria_id)
                existente["categorias"].append(categoria.nmcategoria)
                existente["nmcategoria"] = ", ".join(existente["categorias"])
            continue
        vrprecofinal, descontoativo = calcular_preco_final(
            item.vrpreco,
            tipodesconto=item.tipodesconto,
            vrdesconto=item.vrdesconto,
            dtinidesconto=item.dtinidesconto,
            dtfimdesconto=item.dtfimdesconto,
        )

        registro = {
                "produto_id": produto.produto_id,
                "organizacao_id": produto.organizacao_id,
                "loja_id": loja_id,
                "categoria_id": categoria.categoria_id,
                "categoria_ids": [categoria.categoria_id],
                "categorias": [categoria.nmcategoria],
                "nmproduto": produto.nmproduto,
                "dsproduto": produto.dsproduto,
                "vrprecoprod": float(item.vrpreco),
                "sitproduto": produto.sitproduto,
                "nmcategoria": categoria.nmcategoria,
                "urlfotoproduto": produto.urlfotoproduto,
                "tipodesconto": item.tipodesconto or "NENHUM",
                "vrdesconto": float(item.vrdesconto or 0),
                "dtinidesconto": item.dtinidesconto,
                "dtfimdesconto": item.dtfimdesconto,
                "vrprecofinal": vrprecofinal,
                "descontoativo": descontoativo,
                "pccashback": float(item.pccashback) if item.pccashback is not None else None,
            }
        produtos_listados[produto.produto_id] = registro
        saida.append(registro)

    return saida


@router.post("/produtos")
async def criar_produto(
    request: Request,
    organizacao_id: int = Form(...),
    loja_id: int = Form(...),
    categoria_id: int | None = Form(None),
    nmproduto: str = Form(...),
    dsproduto: str = Form(""),
    sitproduto: str = Form(...),
    idtipoproduto: str = Form(...),
    lote_id: int | None = Form(None),
    urlfotoproduto: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    validar_mutacao_loja(usuario, organizacao_id, loja_id)
    nmproduto = nmproduto.strip()

    if not nmproduto:
        raise HTTPException(status_code=400, detail="Nome do produto é obrigatório.")

    if categoria_id:
        categoria = db.query(Categoria).filter(
            Categoria.categoria_id == categoria_id,
            Categoria.organizacao_id == organizacao_id,
        ).first()

        if not categoria:
            raise HTTPException(status_code=404, detail="Categoria não encontrada para esta organização.")

    produto_existente = (
        db.query(Produto)
        .filter(
            Produto.organizacao_id == organizacao_id,
            func.lower(Produto.nmproduto) == nmproduto.lower()
        )
        .first()
    )

    if produto_existente:
        raise HTTPException(
            status_code=400,
            detail="Já existe um produto com esse nome nesta organização."
        )

    nome_arquivo_foto = None
    url_foto = None

    if urlfotoproduto and urlfotoproduto.filename:
        if not urlfotoproduto.content_type or not urlfotoproduto.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Arquivo deve ser imagem")

        extensao = os.path.splitext(urlfotoproduto.filename)[1].lower()
        nome_arquivo_foto = f"{uuid.uuid4().hex}{extensao}"
        caminho = UPLOAD_PRODUTOS / nome_arquivo_foto

        conteudo = await urlfotoproduto.read()
        with open(caminho, "wb") as f:
            f.write(conteudo)

        url_foto = f"/uploads/produtos/{nome_arquivo_foto}"

    novo_produto = Produto(
        organizacao_id=organizacao_id,
        nmproduto=nmproduto,
        dsproduto=dsproduto,
        sitproduto=sitproduto,
        urlfotoproduto=url_foto,
    )

    db.add(novo_produto)
    db.flush()
    if categoria_id:
        db.add(ProdutoCategoriaOrg(produto_id=novo_produto.produto_id, categoria_id=categoria_id))
    db.commit()
    db.refresh(novo_produto)

    return {
        "message": "Produto cadastrado com sucesso.",
        "produto_id": novo_produto.produto_id,
        "organizacao_id": novo_produto.organizacao_id,
        "categoria_id": categoria_id,
        "nmproduto": novo_produto.nmproduto,
        "dsproduto": novo_produto.dsproduto,
        "sitproduto": novo_produto.sitproduto,
        "foto": nome_arquivo_foto,
        "urlfotoproduto": novo_produto.urlfotoproduto,
    }

# >>>>> dados de apenas 1 prouduto >>>>>>>>>
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

@router.get("/buscar_produto/{produto_id}")
def buscar_produto(produto_id: int, db: Session = Depends(get_db)):
    produto = (
        db.query(Produto)
        .filter(Produto.produto_id == produto_id)
        .first()
    )

    if not produto:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado."
        )

    categoria_catalogo = _categoria_catalogo(db, produto.produto_id)

    return {
        "produto_id": produto.produto_id,
        "organizacao_id": produto.organizacao_id,
        "categoria_id": categoria_catalogo.categoria_id if categoria_catalogo else None,
        "nmproduto": produto.nmproduto,
        "dsproduto": produto.dsproduto,
        "sitproduto": produto.sitproduto,
        "urlfotoproduto": produto.urlfotoproduto,
    }
