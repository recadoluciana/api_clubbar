from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
import os
import uuid
import shutil
import traceback

from app.database import get_db
from app.models.loja import Loja
from app.models.cidade import Cidade
from app.models.estado import Estado
from app.models.organizacao import Organizacao
from app.models.produto import Produto
from app.core.config import UPLOAD_LOJAS
from app.core.security import get_usuario_logado
from app.core.permissoes_loja import validar_gerenciamento_organizacao
from app.models.cashback_config import CashbackConfig
from app.services.cashback_service import obter_ou_criar_config

router = APIRouter(prefix="/lojas", tags=["Lojas"])


def validar_permissao_mutacao_loja(
    payload: dict,
    *,
    organizacao_id: int,
    loja_id: int | None = None,
    criando: bool = False,
) -> None:
    cargo = str(payload.get("dscargo") or "").strip().upper()
    organizacao_usuario = payload.get("organizacao_id")
    loja_usuario = payload.get("loja_id")
    if payload.get("role") != "usuario" or cargo not in {"SUPERADMIN", "ADMIN", "GERENTE"}:
        raise HTTPException(status_code=403, detail="Você não possui permissão para alterar lojas.")
    if int(organizacao_usuario or 0) != organizacao_id:
        raise HTTPException(status_code=403, detail="A loja não pertence à sua organização.")
    if loja_usuario is not None and (criando or int(loja_usuario) != loja_id):
        raise HTTPException(
            status_code=403,
            detail="Você não pode alterar esta loja. Seu acesso permite apenas consultá-la.",
        )


def validar_localidade(db: Session, estado_id: int, cidade_id: int) -> None:
    cidade = (
        db.query(Cidade)
        .filter(
            Cidade.cidade_id == cidade_id,
            Cidade.estado_id == estado_id,
        )
        .first()
    )
    if not cidade:
        raise HTTPException(
            status_code=422,
            detail="Cidade não encontrada ou não pertence ao estado informado.",
        )


def validar_aberto24x7(valor: str) -> str:
    valor_normalizado = valor.strip().upper()
    if valor_normalizado not in {"S", "N"}:
        raise HTTPException(
            status_code=422,
            detail="aberto24x7 deve possuir o valor 'S' ou 'N'.",
        )
    return valor_normalizado


def validar_configuracao_validade(
    idvalidadeprod: str,
    nrdiavalidade: int,
) -> tuple[str, int]:
    controle = idvalidadeprod.strip().upper()
    if controle not in {"S", "N"}:
        raise HTTPException(
            status_code=422,
            detail="idvalidadeprod deve possuir o valor 'S' ou 'N'.",
        )
    if nrdiavalidade < 0:
        raise HTTPException(
            status_code=422,
            detail="nrdiavalidade não pode ser negativo.",
        )
    if controle == "S" and nrdiavalidade == 0:
        raise HTTPException(
            status_code=422,
            detail="nrdiavalidade deve ser maior que zero quando a validade estiver ativa.",
        )
    return controle, nrdiavalidade


def validar_campo_endereco(
    valor: str | None,
    nome_campo: str,
    tamanho_maximo: int,
    obrigatorio: bool = False,
) -> str | None:
    if valor is None:
        if obrigatorio:
            raise HTTPException(
                status_code=422,
                detail=f"{nome_campo} é obrigatório.",
            )
        return None
    valor_normalizado = valor.strip()
    if obrigatorio and not valor_normalizado:
        raise HTTPException(
            status_code=422,
            detail=f"{nome_campo} é obrigatório.",
        )
    if len(valor_normalizado) > tamanho_maximo:
        raise HTTPException(
            status_code=422,
            detail=f"{nome_campo} deve possuir no máximo {tamanho_maximo} caracteres.",
        )
    return valor_normalizado or None


def salvar_logo_loja(arquivo: UploadFile | None) -> str | None:
    if not arquivo or not arquivo.filename:
        return None

    extensao = os.path.splitext(arquivo.filename)[1].lower()
    nome_arquivo = f"{uuid.uuid4().hex}{extensao}"
    caminho_fisico = UPLOAD_LOJAS / nome_arquivo

    with open(caminho_fisico, "wb") as buffer:
        shutil.copyfileobj(arquivo.file, buffer)

    return f"/uploads/lojas/{nome_arquivo}"


@router.get("/listar_todas")
def listar_todas_lojas(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(
            Loja.loja_id,
            Loja.organizacao_id,
            Loja.estado_id,
            Organizacao.nmorganizacao,
            Loja.nmloja,
            Loja.endloja,
            Loja.nrceploja,
            Loja.nrendeloja,
            Loja.aberto24x7,
            Loja.idvalidadeprod,
            Loja.dshorarioloja,
            Loja.nrtelloja,
            Loja.urllogoloja,
            Loja.urlfachadaloja,
            Loja.dsinstaloja,
            Loja.vrtaxaprod,
            Loja.vrtaxaing,
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
            "estado_id": r.estado_id,
            "nmorganizacao": r.nmorganizacao,
            "nmloja": r.nmloja,
            "endloja": r.endloja,
            "nrceploja": r.nrceploja,
            "nrendeloja": r.nrendeloja,
            "aberto24x7": r.aberto24x7,
            "idvalidadeprod": r.idvalidadeprod,
            "dshorarioloja": r.dshorarioloja,
            "nrtelloja": r.nrtelloja,
            "urllogoloja": f"{r.urllogoloja}" if r.urllogoloja else None,
            "urlfachadaloja": r.urlfachadaloja,
            "dsinstaloja": r.dsinstaloja,
            "vrtaxaprod": float(r.vrtaxaprod or 0),
            "vrtaxaing": float(r.vrtaxaing or 0),            
        }
        for r in rows
    ]


from sqlalchemy.orm import aliased

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
            Loja.estado_id,
            Organizacao.nmorganizacao,
            Loja.nmloja,
            Loja.endloja,
            Loja.nrceploja,
            Loja.nrendeloja,
            Loja.dsbairroloja,
            Cidade.nmcidade,
            Loja.aberto24x7,
            Loja.idvalidadeprod,
            Loja.dshorarioloja,
            Loja.nrtelloja,
            Loja.urllogoloja,
            Loja.urlfachadaloja,
            Loja.dsinstaloja,
            Loja.vrtaxaprod,
            Loja.vrtaxaing,
            Loja.dsestiloloja,
            Estado.sgestado,
            Loja.dtcriacao,
        )
        .join(Organizacao, Organizacao.organizacao_id == Loja.organizacao_id)
        .outerjoin(Cidade, Cidade.cidade_id == Loja.cidade_id)
        .outerjoin(Estado, Estado.estado_id == Loja.estado_id)
        .filter(Loja.sitloja == "ATIVA")
    )

    if cidade_id is not None:
        rows = rows.filter(Loja.cidade_id == cidade_id)

    lojas = rows.order_by(Loja.nmloja.asc()).all()

    return [
        {
            "loja_id": r.loja_id,
            "organizacao_id": r.organizacao_id,
            "estado_id": r.estado_id,
            "nmorganizacao": r.nmorganizacao,
            "nmloja": r.nmloja,
            "endloja": r.endloja,
            "nrceploja": r.nrceploja,
            "nrendeloja": r.nrendeloja,
            "dsbairroloja": r.dsbairroloja or "",
            "nmcidade": r.nmcidade or "",
            "aberto24x7": r.aberto24x7,
            "idvalidadeprod": r.idvalidadeprod,
            "dshorarioloja": r.dshorarioloja,
            "nrtelloja": r.nrtelloja,
            "urllogoloja": f"{r.urllogoloja}" if r.urllogoloja else None,
            "urlfachadaloja": r.urlfachadaloja,
            "dsinstaloja": r.dsinstaloja,
            "vrtaxaprod": float(r.vrtaxaprod or 0),
            "vrtaxaing": float(r.vrtaxaing or 0),
            "dsestiloloja": r.dsestiloloja,
            "sgestado": r.sgestado or "",
            "dtcriacao": r.dtcriacao,
        }
        for r in lojas
    ]

@router.get("/com_retirada")
def listar_lojas_com_retirada_pendente(
    request: Request,
    cliente_id: int | None = None,
    db: Session = Depends(get_db)
):
    rows = (
        db.query(
            Loja.loja_id,
            Loja.organizacao_id,
            Loja.estado_id,
            Organizacao.nmorganizacao,
            Loja.nmloja,
            Loja.endloja,
            Loja.nrceploja,
            Loja.nrendeloja,
            Loja.aberto24x7,
            Loja.idvalidadeprod,
            Loja.dshorarioloja,
            Loja.nrtelloja,
            Loja.urllogoloja,
            Loja.urlfachadaloja,
            Loja.vrtaxaprod,
            Loja.vrtaxaing,            
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
            "estado_id": r.estado_id,
            "nmorganizacao": r.nmorganizacao,
            "nmloja": r.nmloja,
            "endloja": r.endloja,
            "nrceploja": r.nrceploja,
            "nrendeloja": r.nrendeloja,
            "aberto24x7": r.aberto24x7,
            "idvalidadeprod": r.idvalidadeprod,
            "dshorarioloja": r.dshorarioloja,
            "nrtelloja": r.nrtelloja,
            "urllogoloja": f"{r.urllogoloja}" if r.urllogoloja else None,
            "urlfachadaloja": r.urlfachadaloja,
            "vrtaxaprod": float(r.vrtaxaprod or 0),
            "vrtaxaing": float(r.vrtaxaing or 0),

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
            Loja.estado_id,
            Organizacao.nmorganizacao,
            Loja.nmloja,
            Loja.endloja,
            Loja.nrceploja,
            Loja.nrendeloja,
            Loja.aberto24x7,
            Loja.idvalidadeprod,
            Loja.dshorarioloja,
            Loja.nrtelloja,
            Loja.urllogoloja,
            Loja.urlfachadaloja,
            Loja.vrtaxaprod,
            Loja.vrtaxaing,            

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
            "estado_id": r.estado_id,
            "nmorganizacao": r.nmorganizacao,
            "nmloja": r.nmloja,
            "endloja": r.endloja,
            "nrceploja": r.nrceploja,
            "nrendeloja": r.nrendeloja,
            "aberto24x7": r.aberto24x7,
            "idvalidadeprod": r.idvalidadeprod,
            "dshorarioloja": r.dshorarioloja,
            "nrtelloja": r.nrtelloja,
            "urllogoloja": f"{r.urllogoloja}" if r.urllogoloja else None,
            "urlfachadaloja": r.urlfachadaloja,
            "vrtaxaprod": float(r.vrtaxaprod or 0),
            "vrtaxaing": float(r.vrtaxaing or 0),

        }
        for r in lojas
    ]


@router.get("/dados_loja/{loja_id}")
def dados_loja(loja_id: int, request: Request, db: Session = Depends(get_db)):
    row = (
        db.query(
            Loja.loja_id,
            Loja.organizacao_id,
            Loja.estado_id,
            Organizacao.nmorganizacao,
            Cidade.nmcidade,
            Loja.nmloja,
            Loja.endloja,
            Loja.nrceploja,
            Loja.nrendeloja,
            Loja.dsbairroloja,
            Loja.aberto24x7,
            Loja.idvalidadeprod,
            Loja.dshorarioloja,
            Loja.nrtelloja,
            Loja.dsinstaloja,
            Loja.dsrefeloja,
            Loja.dsestiloloja,
            Loja.cidade_id,
            Loja.urllogoloja,
            Loja.urlfachadaloja,
            Loja.vrtaxaprod,
            Loja.vrtaxaing,
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
        "estado_id": row.estado_id,
        "nmorganizacao": row.nmorganizacao,
        "nmloja": row.nmloja,
        "endloja": row.endloja,
        "nrceploja": row.nrceploja,
        "nrendeloja": row.nrendeloja,
        "dsbairroloja": row.dsbairroloja,
        "aberto24x7": row.aberto24x7,
        "idvalidadeprod": row.idvalidadeprod,
        "dshorarioloja": row.dshorarioloja,
        "nrtelloja": row.nrtelloja,
        "dsinstaloja": row.dsinstaloja,
        "dsrefeloja": row.dsrefeloja,
        "dsestiloloja": row.dsestiloloja,
        "cidade_id": row.cidade_id,
        "nmcidade": row.nmcidade,
        "urllogoloja": f"{row.urllogoloja}" if row.urllogoloja else None,
        "urlfachadaloja": row.urlfachadaloja,
        "vrtaxaprod": float(row.vrtaxaprod or 0),
        "vrtaxaing": float(row.vrtaxaing or 0),

    }


@router.post("")
def criar_loja(
    organizacao_id: int = Form(...),
    estado_id: int = Form(...),
    cidade_id: int = Form(...),
    nmloja: str = Form(...),
    dsbairroloja: str | None = Form(None),
    endloja: str | None = Form(None),
    nrceploja: str = Form(...),
    nrendeloja: str = Form(...),
    dsinstaloja: str | None = Form(None),
    nrtelloja: str | None = Form(None),
    dshorarioloja: str | None = Form(None),
    aberto24x7: str = Form("N"),
    dsestiloloja: str | None = Form(None),
    nrdiavalidade: int | None = Form(None),
    idvalidadeprod: str = Form("S"),
    vrtaxaprod: float | None = Form(0),
    vrtaxaing: float | None = Form(0),
    urllogoloja: UploadFile | None = File(None),
    urlfachadaloja: UploadFile | None = File(None),
    qtcpdloja: int | None = Form(None),
    usacashback: str = Form("N"),
    pccashback: float = Form(0),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    try:
        validar_permissao_mutacao_loja(
            payload, organizacao_id=organizacao_id, criando=True
        )
        if qtcpdloja is not None and qtcpdloja <= 0:
            raise HTTPException(status_code=422, detail="A capacidade da loja deve ser maior que zero")
        validar_localidade(db, estado_id, cidade_id)
        aberto24x7 = validar_aberto24x7(aberto24x7)
        nrdiavalidade = nrdiavalidade if nrdiavalidade is not None else 90
        idvalidadeprod, nrdiavalidade = validar_configuracao_validade(
            idvalidadeprod,
            nrdiavalidade,
        )
        nrceploja = validar_campo_endereco(
            nrceploja,
            "nrceploja",
            9,
            obrigatorio=True,
        )
        nrendeloja = validar_campo_endereco(
            nrendeloja,
            "nrendeloja",
            20,
            obrigatorio=True,
        )
        urllogoloja_aux = salvar_logo_loja(urllogoloja)
        urlfachadaloja_aux = salvar_logo_loja(urlfachadaloja)

        nova = Loja(
            organizacao_id=organizacao_id,
            estado_id=estado_id,
            cidade_id=cidade_id,
            nmloja=nmloja,
            dsbairroloja=dsbairroloja,
            endloja=endloja,
            nrceploja=nrceploja,
            nrendeloja=nrendeloja,
            dsinstaloja=dsinstaloja,
            nrtelloja=nrtelloja,
            dshorarioloja=dshorarioloja,
            aberto24x7=aberto24x7,
            dsestiloloja=dsestiloloja,
            nrdiavalidade=nrdiavalidade,
            idvalidadeprod=idvalidadeprod,
            vrtaxaprod=vrtaxaprod,
            vrtaxaing=vrtaxaing,
            urllogoloja=urllogoloja_aux,
            urlfachadaloja=urlfachadaloja_aux,
            qtcpdloja=qtcpdloja,
            sitloja="ATIVA",
        )

        db.add(nova)
        db.flush()
        usar = usacashback.strip().upper() == "S"
        if pccashback < 0 or pccashback > 100 or (usar and pccashback <= 0):
            raise HTTPException(422, "Informe um percentual de cashback entre 0,01% e 100%")
        obter_ou_criar_config(db, nova.organizacao_id, nova.loja_id, ativo=usar, percentual=pccashback)
        db.commit()
        db.refresh(nova)

        return {
            "mensagem": "Loja cadastrada com sucesso",
            "loja_id": nova.loja_id,
            "estado_id": nova.estado_id,
            "urllogoloja": nova.urllogoloja,
            "urlfachadaloja": nova.urlfachadaloja,
            "endloja": nova.endloja,
            "nrceploja": nova.nrceploja,
            "nrendeloja": nova.nrendeloja,
            "dsinstaloja": nova.dsinstaloja,
            "aberto24x7": nova.aberto24x7,
            "idvalidadeprod": nova.idvalidadeprod,
            "dsestiloloja": nova.dsestiloloja,
            "qtcpdloja": nova.qtcpdloja,
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao criar loja: {str(e)}")


@router.get("/organizacoes/{organizacao_id}/lojas_todas")
def listar_lojas_por_organizacao_todas(
    organizacao_id: int,
    request: Request,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    validar_gerenciamento_organizacao(payload, organizacao_id)
    consulta = db.query(Loja).filter(Loja.organizacao_id == organizacao_id)
    loja_usuario = payload.get("loja_id")
    if loja_usuario is not None:
        consulta = consulta.filter(Loja.loja_id == int(loja_usuario))
    lojas = (
        consulta
        .order_by(Loja.nmloja.asc())
        .all()
    )
    configs = {c.loja_id: c for c in db.query(CashbackConfig).filter(CashbackConfig.organizacao_id == organizacao_id).all()}

    base_url = str(request.base_url).rstrip("/")

    return [
        {
            "loja_id": loja.loja_id,
            "organizacao_id": loja.organizacao_id,
            "estado_id": loja.estado_id,
            "cidade_id": loja.cidade_id,
            "nmloja": loja.nmloja,
            "dsbairroloja": loja.dsbairroloja,
            "endloja": loja.endloja,
            "nrceploja": loja.nrceploja,
            "nrendeloja": loja.nrendeloja,
            "dsinstaloja": loja.dsinstaloja,
            "nrtelloja": loja.nrtelloja,
            "dshorarioloja": loja.dshorarioloja,
            "aberto24x7": loja.aberto24x7,
            "dsestiloloja": loja.dsestiloloja,
            "nrdiavalidade": loja.nrdiavalidade,
            "idvalidadeprod": loja.idvalidadeprod,
            "sitloja": loja.sitloja,
            "urllogoloja": f"{loja.urllogoloja}" if loja.urllogoloja else None,
            "urlfachadaloja": loja.urlfachadaloja,
            "vrtaxaprod": float(loja.vrtaxaprod or 0),
            "vrtaxaing": float(loja.vrtaxaing or 0),
            "qtcpdloja": loja.qtcpdloja,
            "usacashback": "S" if configs.get(loja.loja_id) and configs[loja.loja_id].sitcashback == "ATIVO" else "N",
            "pccashback": float(configs[loja.loja_id].pccashback) if configs.get(loja.loja_id) else 0.0,

        }
        for loja in lojas
    ]


@router.put("/{loja_id}")
def atualizar_loja(
    loja_id: int,
    organizacao_id: int | None = Form(None),
    estado_id: int | None = Form(None),
    cidade_id: int | None = Form(None),
    nmloja: str | None = Form(None),
    dsbairroloja: str | None = Form(None),
    endloja: str | None = Form(None),
    nrceploja: str | None = Form(None),
    nrendeloja: str | None = Form(None),
    dsinstaloja: str | None = Form(None),
    nrtelloja: str | None = Form(None),
    dshorarioloja: str | None = Form(None),
    aberto24x7: str | None = Form(None),
    dsestiloloja: str | None = Form(None),
    nrdiavalidade: int | None = Form(None),
    idvalidadeprod: str | None = Form(None),
    vrtaxaprod: float | None = Form(None),
    vrtaxaing: float | None = Form(None),
    urllogoloja: UploadFile | None = File(None),
    urlfachadaloja: UploadFile | None = File(None),
    qtcpdloja: int | None = Form(None),
    usacashback: str | None = Form(None),
    pccashback: float | None = Form(None),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    try:

        loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()

        if not loja:
            raise HTTPException(status_code=404, detail="Loja não encontrada")

        validar_permissao_mutacao_loja(
            payload, organizacao_id=loja.organizacao_id, loja_id=loja_id
        )

        if organizacao_id is not None and organizacao_id != loja.organizacao_id:
            raise HTTPException(
                status_code=403,
                detail="Não é permitido transferir a loja para outra organização.",
            )

        if organizacao_id is not None:
            loja.organizacao_id = organizacao_id

        estado_id_final = estado_id if estado_id is not None else loja.estado_id
        cidade_id_final = cidade_id if cidade_id is not None else loja.cidade_id
        validar_localidade(db, estado_id_final, cidade_id_final)

        if estado_id is not None:
            loja.estado_id = estado_id

        if cidade_id is not None:
            loja.cidade_id = cidade_id

        if nmloja is not None:
            loja.nmloja = nmloja

        if dsbairroloja is not None:
            loja.dsbairroloja = dsbairroloja

        if endloja is not None:
            loja.endloja = endloja

        if nrceploja is not None:
            loja.nrceploja = validar_campo_endereco(
                nrceploja,
                "nrceploja",
                9,
                obrigatorio=True,
            )

        if nrendeloja is not None:
            loja.nrendeloja = validar_campo_endereco(
                nrendeloja,
                "nrendeloja",
                20,
                obrigatorio=True,
            )

        if dsinstaloja is not None:
            loja.dsinstaloja = dsinstaloja

        if nrtelloja is not None:
            loja.nrtelloja = nrtelloja

        if dshorarioloja is not None:
            loja.dshorarioloja = dshorarioloja

        if aberto24x7 is not None:
            loja.aberto24x7 = validar_aberto24x7(aberto24x7)

        if dsestiloloja is not None:
            loja.dsestiloloja = dsestiloloja

        controle_validade = (
            idvalidadeprod
            if idvalidadeprod is not None
            else loja.idvalidadeprod
        )
        dias_validade = (
            nrdiavalidade
            if nrdiavalidade is not None
            else loja.nrdiavalidade
        )
        controle_validade, dias_validade = validar_configuracao_validade(
            controle_validade,
            dias_validade,
        )
        loja.idvalidadeprod = controle_validade

        if nrdiavalidade is not None:
            loja.nrdiavalidade = dias_validade
        
        if vrtaxaprod is not None:
            loja.vrtaxaprod = vrtaxaprod

        if vrtaxaing is not None:
            loja.vrtaxaing = vrtaxaing
        if qtcpdloja is not None:
            if qtcpdloja <= 0:
                raise HTTPException(status_code=422, detail="A capacidade da loja deve ser maior que zero")
            loja.qtcpdloja = qtcpdloja

        if urllogoloja is not None and urllogoloja.filename:
            nova_url_logo = salvar_logo_loja(urllogoloja)
            loja.urllogoloja = nova_url_logo
            print("nova_url_logo:", nova_url_logo)

        if urlfachadaloja is not None and urlfachadaloja.filename:
            loja.urlfachadaloja = salvar_logo_loja(urlfachadaloja)

        config = obter_ou_criar_config(db, loja.organizacao_id, loja.loja_id)
        if usacashback is not None:
            config.sitcashback = "ATIVO" if usacashback.strip().upper() == "S" else "INATIVO"
        if pccashback is not None:
            if pccashback < 0 or pccashback > 100:
                raise HTTPException(422, "Percentual de cashback inválido")
            config.pccashback = pccashback
        if config.sitcashback == "ATIVO" and float(config.pccashback or 0) <= 0:
            raise HTTPException(422, "Cashback ativo exige percentual maior que zero")

        db.commit()
        db.refresh(loja)

        print("url final no banco:", loja.urllogoloja)

        return {
            "mensagem": "Loja atualizada com sucesso",
            "loja": {
                "loja_id": loja.loja_id,
                "organizacao_id": loja.organizacao_id,
                "estado_id": loja.estado_id,
                "cidade_id": loja.cidade_id,
                "nmloja": loja.nmloja,
                "dsbairroloja": loja.dsbairroloja,
                "endloja": loja.endloja,
                "nrceploja": loja.nrceploja,
                "nrendeloja": loja.nrendeloja,
                "dsinstaloja": loja.dsinstaloja,
                "nrtelloja": loja.nrtelloja,
                "dshorarioloja": loja.dshorarioloja,
                "aberto24x7": loja.aberto24x7,
                "dsestiloloja": loja.dsestiloloja,
                "nrdiavalidade": loja.nrdiavalidade,
                "idvalidadeprod": loja.idvalidadeprod,
                "sitloja": loja.sitloja,
                "usacashback": "S" if config.sitcashback == "ATIVO" else "N",
                "pccashback": float(config.pccashback or 0),
                "urllogoloja": loja.urllogoloja,
                "urlfachadaloja": loja.urlfachadaloja,
                "qtcpdloja": loja.qtcpdloja,
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar loja: {str(e)}")


@router.delete("/{loja_id}")
def deletar_loja(loja_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_usuario_logado)):
    try:
        loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()

        if not loja:
            raise HTTPException(status_code=404, detail="Loja não encontrada")

        validar_permissao_mutacao_loja(
            payload, organizacao_id=loja.organizacao_id, loja_id=loja_id
        )

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
def inativar_loja(loja_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_usuario_logado)):
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()

    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    validar_permissao_mutacao_loja(
        payload, organizacao_id=loja.organizacao_id, loja_id=loja_id
    )

    loja.sitloja = "INATIVA"
    db.commit()
    db.refresh(loja)

    return {"mensagem": "Loja inativada com sucesso"}


@router.patch("/{loja_id}/reativar")
def reativar_loja(loja_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_usuario_logado)):
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()

    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    validar_permissao_mutacao_loja(
        payload, organizacao_id=loja.organizacao_id, loja_id=loja_id
    )

    loja.sitloja = "ATIVA"
    db.commit()
    db.refresh(loja)

    return {"mensagem": "Loja reativada com sucesso"}
