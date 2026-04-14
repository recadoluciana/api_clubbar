from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Request
from sqlalchemy.orm import Session
from sqlalchemy import exists
import os
import uuid
import shutil

from app.database import get_db
from app.models.categoria import Categoria
from app.models.produto import Produto
from app.models.itvenda import ItVenda
from app.models.itcarrinho import ItCarrinho

from app.core.config import UPLOAD_PRODUTOS

router = APIRouter(tags=["Produtos"])

os.makedirs(UPLOAD_PRODUTOS, exist_ok=True)


@router.delete("/produtos/{produto_id}")
def excluir_produto(produto_id: int, db: Session = Depends(get_db)):
    produto = db.query(Produto).filter(
        Produto.produto_id == produto_id
    ).first()

    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    usado_itcarrinho = db.query(
        exists().where(ItCarrinho.produto_id == produto_id)
    ).scalar()

    usado_itvenda = db.query(
        exists().where(ItVenda.produto_id == produto_id)
    ).scalar()

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
    vrprecoprod: float | None = Form(None),
    sitproduto: str | None = Form(None),
    urlfotoproduto: UploadFile | None = File(None),  # 🔥 PADRONIZADO
    db: Session = Depends(get_db),
    tipodesconto=(data.tipodesconto or "NENHUM").upper(),
    vrdesconto=data.vrdesconto or 0,
    dtinidesconto=data.dtinidesconto,
    dtfimdesconto=data.dtfimdesconto,
):
    try:
        produto = db.query(Produto).filter(
            Produto.produto_id == produto_id
        ).first()

        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado")

        print("arquivo recebido:", urlfotoproduto.filename if urlfotoproduto else None)

        # 🔥 FOTO
        if urlfotoproduto is not None and urlfotoproduto.filename:
            if not urlfotoproduto.content_type or not urlfotoproduto.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Arquivo deve ser imagem")

            extensao = os.path.splitext(urlfotoproduto.filename)[1].lower()
            nome_arquivo = f"{uuid.uuid4().hex}{extensao}"
            caminho_arquivo = os.path.join(UPLOAD_PRODUTOS, nome_arquivo)

            with open(caminho_arquivo, "wb") as buffer:
                shutil.copyfileobj(urlfotoproduto.file, buffer)  # ✅ CORRIGIDO

            produto.urlfotoproduto = f"/uploads/produtos/{nome_arquivo}"

            print("nova url foto:", produto.urlfotoproduto)

        # 🔥 CAMPOS
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


        if (produto.tipodesconto or "NENHUM") == "NENHUM":
            produto.vrdesconto = 0
            produto.dtinidesconto = None
            produto.dtfimdesconto = None

        db.commit()
        db.refresh(produto)

        return {
            "mensagem": "Produto atualizado com sucesso",
            "produto_id": produto.produto_id,
            "urlfotoproduto": produto.urlfotoproduto
        }

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar produto: {str(e)}")


@router.get("/lojas/{loja_id}/produtos", response_model=list[ProdutoOut])
def listar_produtos_por_loja(loja_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(Produto, Categoria.nmcategoria)
        .outerjoin(Categoria, Categoria.categoria_id == Produto.categoria_id)
        .filter(Produto.loja_id == loja_id, Produto.sitproduto == "ATIVO")
        .all()
    )

    saida = []

    for produto, nmcategoria in rows:
        vrprecofinal, descontoativo = calcular_preco_final(produto)

        saida.append(
            {
                "produto_id": produto.produto_id,
                "organizacao_id": produto.organizacao_id,
                "loja_id": produto.loja_id,
                "categoria_id": produto.categoria_id,
                "nmproduto": produto.nmproduto,
                "dsproduto": produto.dsproduto,
                "vrprecoprod": produto.vrprecoprod,
                "sitproduto": produto.sitproduto,
                "nmcategoria": nmcategoria,
                "urlfotoproduto": produto.urlfotoproduto,
                "tipodesconto": produto.tipodesconto or "NENHUM",
                "vrdesconto": produto.vrdesconto or 0,
                "dtinidesconto": produto.dtinidesconto,
                "dtfimdesconto": produto.dtfimdesconto,
                "vrprecofinal": vrprecofinal,
                "descontoativo": descontoativo,
            }
        )

    return saida

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
    idtipoproduto: str = Form(...),
    lote_id: int | None = Form(None),
    urlfotoproduto: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    tipodesconto=(data.tipodesconto or "NENHUM").upper(),
    vrdesconto=data.vrdesconto or 0,
    dtinidesconto=data.dtinidesconto,
    dtfimdesconto=data.dtfimdesconto,
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

    if urlfotoproduto:
        extensao = os.path.splitext(urlfotoproduto.filename)[1].lower()
        nome_arquivo_foto = f"{uuid.uuid4().hex}{extensao}"

        caminho = os.path.join(UPLOAD_PRODUTOS, nome_arquivo_foto)

        conteudo = await urlfotoproduto.read()
        with open(caminho, "wb") as f:
            f.write(conteudo)

        url_foto = f"/uploads/produtos/{nome_arquivo_foto}"
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
        idtipoproduto=idtipoproduto,
        lote_id=lote_id,
        urlfotoproduto=url_foto,
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
        "idtipoproduto": novo_produto.idtipoproduto,
        "lote_id": novo_produto.lote_id,
        "foto": nome_arquivo_foto,
        "urlfotoproduto": novo_produto.urlfotoproduto,
    }