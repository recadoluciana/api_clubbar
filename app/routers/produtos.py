from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.categoria import Categoria
from app.models.produto import Produto
from app.models.itvenda import ItVenda
from app.models.itcarrinho import ItCarrinho

from app.schemas.produto import ProdutoUpdate

from sqlalchemy import exists

from fastapi import Request

import os
import uuid

router = APIRouter(tags=["Produtos"])

UPLOAD_DIR = "uploads/produtos"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.delete("/produtos/{produto_id}")
def excluir_produto(produto_id: int, db: Session = Depends(get_db)):

    # 1. verifica se produto existe
    produto = db.query(Produto).filter(
        Produto.produto_id == produto_id
    ).first()

    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # 2. verifica se já foi usado em carrinho
    usado_itcarrinho = db.query(
        exists().where(ItCarrinho.produto_id == produto_id)
    ).scalar()

    # 2. verifica se já foi usado em vendas
    usado_itvenda = db.query(
        exists().where(ItVenda.produto_id == produto_id)
    ).scalar()

    if usado_itcarrinho or usado_itvenda:
        raise HTTPException(
            status_code=400,
            detail="Este produto já foi utilizado em vendas/carrinhos e não pode ser excluído"
        )

    # 3. pode excluir
    db.delete(produto)
    db.commit()

    return {"message": "Produto excluído com sucesso"}


from fastapi import UploadFile, File, Form
import os
import shutil
from uuid import uuid4

UPLOAD_DIR = "uploads/produtos"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.put("/produtos/{produto_id}")
def atualizar_produto(
    produto_id: int,

    # 👇 substitui o ProdutoUpdate por Form
    categoria_id: int = Form(None),
    nmproduto: str = Form(None),
    dsproduto: str = Form(None),
    vrprecoprod: float = Form(None),
    sitproduto: str = Form(None),
    skuproduto: str = Form(None),

    # 👇 NOVO campo de upload
    file: UploadFile = File(None),

    db: Session = Depends(get_db)
):
    produto = db.query(Produto).filter(
        Produto.produto_id == produto_id
    ).first()

    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # -------------------------
    # 📸 UPLOAD DA IMAGEM
    # -------------------------
    if file:
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Arquivo deve ser imagem")

        extensao = file.filename.split(".")[-1]
        nome_arquivo = f"{uuid4()}.{extensao}"

        caminho_arquivo = os.path.join(UPLOAD_DIR, nome_arquivo)

        with open(caminho_arquivo, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 👇 salva no banco
        produto.urlfotoproduto = f"/uploads/produtos/{nome_arquivo}"

    # -------------------------
    # 🔄 SUA LÓGICA ORIGINAL
    # -------------------------
    if categoria_id is not None:
        produto.categoria_id = categoria_id

    if nmproduto is not None:
        produto.nmproduto = nmproduto

    if dsproduto is not None:
        produto.dsproduto = dsproduto

    if vrprecoprod is not None:
        produto.vrprecoprod = vrprecoprod

    if sitproduto is not None:
        produto.sitproduto = sitproduto

    if skuproduto is not None:
        produto.skuproduto = skuproduto

    db.commit()
    db.refresh(produto)

    return {
        "mensagem"   : "Produto atualizado com sucesso",
        "produto_id" : produto.produto_id,
        "urlfoto"    : produto.urlfotoproduto
    }

@router.get("/lojas/{loja_id}/produtos")
def listar_produtos_por_loja(loja_id: int, db: Session = Depends(get_db)):

    rows = (
        db.query(
            Produto.organizacao_id,
            Produto.loja_id,
            Produto.produto_id,
            Produto.categoria_id,
            Produto.nmproduto,
            Produto.dsproduto,
            Produto.vrprecoprod,
            Produto.sitproduto,
            Produto.skuproduto,
            Produto.idtipoproduto,
            Produto.lote_id,
            Produto.urlfotoproduto,
            Categoria.nmcategoria
        )
        .outerjoin(Categoria, Categoria.categoria_id == Produto.categoria_id)
        .filter(
            Produto.loja_id == loja_id,
            Produto.sitproduto == "ATIVO",
            Produto.idtipoproduto == "P",
        )
        .order_by(
            Categoria.nmcategoria,
            Produto.nmproduto
        )
        .all()
    )

    return [
        {
            "organizacao_id": r.organizacao_id,
            "loja_id": r.loja_id,
            "produto_id": r.produto_id,
            "categoria_id": r.categoria_id,
            "nmcategoria": r.nmcategoria,
            "nmproduto": r.nmproduto,
            "dsproduto": r.dsproduto,
            "vrprecoprod": float(r.vrprecoprod) if r.vrprecoprod is not None else 0.0,
            "sitproduto": r.sitproduto,
            "skuproduto": r.skuproduto,
            "nmcategoria": r.nmcategoria,
            "idtipoproduto": r.idtipoproduto,
            "lote_id": r.lote_id,
            "urlfotoproduto": r.urlfotoproduto,
        }
        for r in rows
    ]


@router.post("/produtos")
async def criar_produto(
    request: Request,
    organizacao_id: int = Form(...),
    loja_id: int = Form(...),
    categoria_id: int | None = Form(None),
    nmproduto: str = Form(...),
    dsproduto: str = Form(""),
    vrprecoprod: float = Form(...),
    sitproduto: str = Form(...),
    skuproduto: str = Form(""),
    idtipoproduto: str = Form(...),
    lote_id: int | None = Form(None),
    foto: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    nmproduto = nmproduto.strip()

    if not nmproduto:
        raise HTTPException(status_code=400, detail="Nome do produto é obrigatório.")

    if vrprecoprod <= 0:
        raise HTTPException(status_code=400, detail="Preço do produto deve ser maior que zero.")

    if idtipoproduto == "I" and not lote_id:
        raise HTTPException(
            status_code=400,
            detail="Para produto do tipo 'I', o campo lote_id é obrigatório."
        )

    if categoria_id:
        categoria = db.query(Categoria).filter(
            Categoria.categoria_id == categoria_id
        ).first()

        if not categoria:
            raise HTTPException(status_code=404, detail="Categoria não encontrada.")

    if idtipoproduto == "P":
        lote_id = None

    produto_existente = (
        db.query(Produto)
        .filter(
            Produto.loja_id == loja_id,
            Produto.nmproduto == nmproduto
        )
        .first()
    )

    if produto_existente:
        raise HTTPException(
            status_code=400,
            detail="Já existe um produto com esse nome nesta loja."
        )

    nome_arquivo_foto = None
    
    base_url = str(request.base_url).rstrip("/")

    if foto:
        extensao = os.path.splitext(foto.filename)[1].lower()
        nome_arquivo = f"{uuid.uuid4().hex}{extensao}"

        caminho = os.path.join("uploads/produtos", nome_arquivo)

        conteudo = await foto.read()
        with open(caminho, "wb") as f:
            f.write(conteudo)

        url_foto = f"{base_url}/uploads/produtos/{nome_arquivo}"

        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>url_foto",url_foto)

    else:
        url_foto = None

    novo_produto = Produto(
        organizacao_id=organizacao_id,
        loja_id=loja_id,
        categoria_id=categoria_id,
        nmproduto=nmproduto,
        dsproduto=dsproduto,
        vrprecoprod=vrprecoprod,
        sitproduto=sitproduto,
        skuproduto=skuproduto,
        idtipoproduto=idtipoproduto,
        lote_id=lote_id,
        urlfotoproduto=url_foto,  # descomente se existir esse campo no model
    )

    db.add(novo_produto)
    db.commit()
    db.refresh(novo_produto)

    return {
        "message": "Produto cadastrado com sucesso.",
        "produto_id": novo_produto.produto_id,
        "organizacao_id": novo_produto.organizacao_id,
        "loja_id": novo_produto.loja_id,
        "categoria_id": novo_produto.categoria_id,
        "nmproduto": novo_produto.nmproduto,
        "dsproduto": novo_produto.dsproduto,
        "vrprecoprod": float(novo_produto.vrprecoprod),
        "sitproduto": novo_produto.sitproduto,
        "skuproduto": novo_produto.skuproduto,
        "idtipoproduto": novo_produto.idtipoproduto,
        "lote_id": novo_produto.lote_id,
        "foto": nome_arquivo_foto,
    }