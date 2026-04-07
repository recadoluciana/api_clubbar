from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
import os
import uuid
import shutil
import traceback

from app.database import get_db
from app.models.loja import Loja
from app.models.cidade import Cidade
from app.models.organizacao import Organizacao
from app.models.produto import Produto
from app.core.config import UPLOAD_LOJAS

router = APIRouter(prefix="/lojas", tags=["Lojas"])


def salvar_logo_loja(arquivo: UploadFile | None) -> str | None:
    if not arquivo or not arquivo.filename:
        return None

    extensao = os.path.splitext(arquivo.filename)[1].lower()
    nome_arquivo = f"{uuid.uuid4().hex}{extensao}"
    caminho_fisico = os.path.join(UPLOAD_LOJAS, nome_arquivo)

    with open(caminho_fisico, "wb") as buffer:
        shutil.copyfileobj(arquivo.file, buffer)

    return f"/uploads/lojas/{nome_arquivo}"


@router.get("/listar_todas")
def listar_todas_lojas(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(
            Loja.loja_id,
            Loja.organizacao_id,
            Organizacao.nmorganizacao,
            Loja.nmloja,
            Loja.endloja,
            Loja.aberto24x7,
            Loja.dshorarioloja,
            Loja.nrtelloja,
            Loja.urllogoloja,
        )
        .join(Organizacao, Organizacao.organizacao_id == Loja.organizacao_id)
        .filter(Loja.sitloja == "ATIVA")
        .order_by(Loja.nmloja.asc())
        .all()
    )

    base_url = str(request.base_url).rstrip("/")

    return [
        {
            "loja_id": r.loja_id,
            "organizacao_id": r.organizacao_id,
            "nmorganizacao": r.nmorganizacao,
            "nmloja": r.nmloja,
            "endloja": r.endloja,
            "aberto24x7": r.aberto24x7,
            "dshorarioloja": r.dshorarioloja,
            "nrtelloja": r.nrtelloja,
            "urllogoloja": f"{r.urllogoloja}" if r.urllogoloja else None,
        }
        for r in rows
    ]


@router.get("/listar_todas_ativas")
def listar_todas_lojas_ativas(
    request: Request,
    cidade_id: int | None = None,
    db: Session = Depends(get_db)
):
    rows = (
        db.query(
            Loja.loja_id,
            Loja.organizacao_id,
            Organizacao.nmorganizacao,
            Loja.nmloja,
            Loja.endloja,
            Loja.aberto24x7,
            Loja.dshorarioloja,
            Loja.nrtelloja,
            Loja.urllogoloja,
        )
        .join(Organizacao, Organizacao.organizacao_id == Loja.organizacao_id)
        .filter(Loja.sitloja == "ATIVA")
    )

    if cidade_id is not None:
        rows = rows.filter(Loja.cidade_id == cidade_id)

    lojas = rows.order_by(Loja.nmloja.asc()).all()
    
    base_url = str(request.base_url).rstrip("/")

    return [
        {
            "loja_id": r.loja_id,
            "organizacao_id": r.organizacao_id,
            "nmorganizacao": r.nmorganizacao,
            "nmloja": r.nmloja,
            "endloja": r.endloja,
            "aberto24x7": r.aberto24x7,
            "dshorarioloja": r.dshorarioloja,
            "nrtelloja": r.nrtelloja,
            "urllogoloja": f"{r.urllogoloja}" if r.urllogoloja else None,
        }
        for r in lojas
    ]


@router.get("/cidades")
def listar_lojas_cidade(
    request: Request,
    cidade_id: int | None = None,
    db: Session = Depends(get_db)
):
    rows = (
        db.query(
            Loja.loja_id,
            Loja.organizacao_id,
            Organizacao.nmorganizacao,
            Loja.nmloja,
            Loja.endloja,
            Loja.aberto24x7,
            Loja.dshorarioloja,
            Loja.nrtelloja,
            Loja.urllogoloja,
        )
        .join(Organizacao, Organizacao.organizacao_id == Loja.organizacao_id)
        .filter(Loja.sitloja == "ATIVA")
    )

    if cidade_id is not None:
        rows = rows.filter(Loja.cidade_id == cidade_id)

    lojas = rows.order_by(Loja.nmloja.asc()).all()
    base_url = str(request.base_url).rstrip("/")

    return [
        {
            "loja_id": r.loja_id,
            "organizacao_id": r.organizacao_id,
            "nmorganizacao": r.nmorganizacao,
            "nmloja": r.nmloja,
            "endloja": r.endloja,
            "aberto24x7": r.aberto24x7,
            "dshorarioloja": r.dshorarioloja,
            "nrtelloja": r.nrtelloja,
            "urllogoloja": f"{r.urllogoloja}" if r.urllogoloja else None,
        }
        for r in lojas
    ]


@router.get("/dados_loja/{loja_id}")
def dados_loja(loja_id: int, request: Request, db: Session = Depends(get_db)):
    row = (
        db.query(
            Loja.loja_id,
            Loja.organizacao_id,
            Organizacao.nmorganizacao,
            Cidade.nmcidade,
            Loja.nmloja,
            Loja.endloja,
            Loja.dsbairroloja,
            Loja.aberto24x7,
            Loja.dshorarioloja,
            Loja.nrtelloja,
            Loja.dsinstaloja,
            Loja.dsrefeloja,
            Loja.cidade_id,
            Loja.urllogoloja,
        )
        .join(Organizacao, Organizacao.organizacao_id == Loja.organizacao_id)
        .outerjoin(Cidade, Cidade.cidade_id == Loja.cidade_id)
        .filter(Loja.loja_id == loja_id)
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    base_url = str(request.base_url).rstrip("/")

    return {
        "loja_id": row.loja_id,
        "organizacao_id": row.organizacao_id,
        "nmorganizacao": row.nmorganizacao,
        "nmloja": row.nmloja,
        "endloja": row.endloja,
        "dsbairroloja": row.dsbairroloja,
        "aberto24x7": row.aberto24x7,
        "dshorarioloja": row.dshorarioloja,
        "nrtelloja": row.nrtelloja,
        "dsinstaloja": row.dsinstaloja,
        "dsrefeloja": row.dsrefeloja,
        "cidade_id": row.cidade_id,
        "nmcidade": row.nmcidade,
        "urllogoloja": f"{row.urllogoloja}" if row.urllogoloja else None,
    }


@router.post("")
def criar_loja(
    organizacao_id: int = Form(...),
    cidade_id: int = Form(...),
    nmloja: str = Form(...),
    dsbairroloja: str | None = Form(None),
    nrtelloja: str | None = Form(None),
    dshorarioloja: str | None = Form(None),
    nrdiavalidade: int | None = Form(None),
    urllogoloja: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    try:
        urllogoloja_aux = salvar_logo_loja(urllogoloja)

        nova = Loja(
            organizacao_id=organizacao_id,
            cidade_id=cidade_id,
            nmloja=nmloja,
            dsbairroloja=dsbairroloja,
            nrtelloja=nrtelloja,
            dshorarioloja=dshorarioloja,
            nrdiavalidade=nrdiavalidade,
            urllogoloja=urllogoloja_aux,
            sitloja="ATIVA",
        )

        db.add(nova)
        db.commit()
        db.refresh(nova)

        return {
            "mensagem": "Loja cadastrada com sucesso",
            "loja_id": nova.loja_id,
            "urllogoloja": nova.urllogoloja,
        }

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao criar loja: {str(e)}")


@router.get("/organizacoes/{organizacao_id}/lojas_todas")
def listar_lojas_por_organizacao_todas(
    organizacao_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    lojas = (
        db.query(Loja)
        .filter(Loja.organizacao_id == organizacao_id)
        .order_by(Loja.nmloja.asc())
        .all()
    )

    base_url = str(request.base_url).rstrip("/")

    return [
        {
            "loja_id": loja.loja_id,
            "organizacao_id": loja.organizacao_id,
            "nmloja": loja.nmloja,
            "dsbairroloja": loja.dsbairroloja,
            "nrtelloja": loja.nrtelloja,
            "dshorarioloja": loja.dshorarioloja,
            "nrdiavalidade": loja.nrdiavalidade,
            "sitloja": loja.sitloja,
            "urllogoloja": f"{loja.urllogoloja}" if loja.urllogoloja else None,
        }
        for loja in lojas
    ]


@router.put("/{loja_id}")
def atualizar_loja(
    loja_id: int,
    organizacao_id: int | None = Form(None),
    cidade_id: int | None = Form(None),
    nmloja: str | None = Form(None),
    dsbairroloja: str | None = Form(None),
    nrtelloja: str | None = Form(None),
    dshorarioloja: str | None = Form(None),
    nrdiavalidade: int | None = Form(None),
    urllogoloja: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    try:
        print("=== UPDATE LOJA ===")
        print("loja_id:", loja_id)
        print("organizacao_id:", organizacao_id)
        print("cidade_id:", cidade_id)
        print("nmloja:", nmloja)
        print("arquivo recebido:", urllogoloja.filename if urllogoloja else None)

        loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()

        if not loja:
            raise HTTPException(status_code=404, detail="Loja não encontrada")

        if organizacao_id is not None:
            loja.organizacao_id = organizacao_id

        if cidade_id is not None:
            loja.cidade_id = cidade_id

        if nmloja is not None:
            loja.nmloja = nmloja

        if dsbairroloja is not None:
            loja.dsbairroloja = dsbairroloja

        if nrtelloja is not None:
            loja.nrtelloja = nrtelloja

        if dshorarioloja is not None:
            loja.dshorarioloja = dshorarioloja

        if nrdiavalidade is not None:
            loja.nrdiavalidade = nrdiavalidade

        if urllogoloja is not None and urllogoloja.filename:
            nova_url_logo = salvar_logo_loja(urllogoloja)
            loja.urllogoloja = nova_url_logo
            print("nova_url_logo:", nova_url_logo)

        db.commit()
        db.refresh(loja)

        print("url final no banco:", loja.urllogoloja)

        return {
            "mensagem": "Loja atualizada com sucesso",
            "loja": {
                "loja_id": loja.loja_id,
                "organizacao_id": loja.organizacao_id,
                "cidade_id": loja.cidade_id,
                "nmloja": loja.nmloja,
                "dsbairroloja": loja.dsbairroloja,
                "nrtelloja": loja.nrtelloja,
                "dshorarioloja": loja.dshorarioloja,
                "nrdiavalidade": loja.nrdiavalidade,
                "sitloja": loja.sitloja,
                "urllogoloja": loja.urllogoloja,
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar loja: {str(e)}")


@router.delete("/{loja_id}")
def deletar_loja(loja_id: int, db: Session = Depends(get_db)):
    try:
        loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()

        if not loja:
            raise HTTPException(status_code=404, detail="Loja não encontrada")

        existe_produto = db.query(Produto).filter(Produto.loja_id == loja_id).first()

        if existe_produto:
            raise HTTPException(
                status_code=400,
                detail="Não é possível deletar a loja, pois existem produtos vinculados"
            )

        db.delete(loja)
        db.commit()

        return {"mensagem": "Loja deletada com sucesso"}

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao deletar loja: {str(e)}"
        )


@router.patch("/{loja_id}/inativar")
def inativar_loja(loja_id: int, db: Session = Depends(get_db)):
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()

    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    loja.sitloja = "INATIVA"
    db.commit()
    db.refresh(loja)

    return {"mensagem": "Loja inativada com sucesso"}


@router.patch("/{loja_id}/reativar")
def reativar_loja(loja_id: int, db: Session = Depends(get_db)):
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()

    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    loja.sitloja = "ATIVA"
    db.commit()
    db.refresh(loja)

    return {"mensagem": "Loja reativada com sucesso"}