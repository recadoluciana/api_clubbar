from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cidade import Cidade
from app.models.estado import Estado
from app.models.leadparceiro import LeadParceiro
from app.schemas.leadparceiro import (
    LeadParceiroCreate,
    LeadParceiroOut,
    LeadParceiroUpdate,
)


router = APIRouter(
    prefix="/parceiros",
    tags=["Parceiros"],
)


def _dias_espera(dtcriacao: datetime) -> int:
    diferenca = datetime.now() - dtcriacao

    return max(diferenca.days, 0)


def _serializar_lead(
    lead: LeadParceiro,
    estado: Estado,
    cidade: Cidade,
) -> dict:
    status_lead = (
        lead.status.value
        if hasattr(lead.status, "value")
        else str(lead.status)
    )

    return {
        "leadparceiro_id": lead.leadparceiro_id,
        "nmresponsavel": lead.nmresponsavel,
        "nmestabelecimento": lead.nmestabelecimento,
        "tipo": lead.tipo,
        "telefone": lead.telefone,
        "email": lead.email,
        "estado_id": lead.estado_id,
        "cidade_id": lead.cidade_id,
        "nmestado": estado.nmestado,
        "sgestado": estado.sgestado,
        "nmcidade": cidade.nmcidade,
        "mensagem": lead.mensagem,
        "status": status_lead,
        "dtcriacao": lead.dtcriacao,
        "dtultatu": lead.dtultatu,
        "dias_espera": _dias_espera(
            lead.dtcriacao,
        ),
    }


def _buscar_lead_com_localidade(
    db: Session,
    leadparceiro_id: int,
):
    return (
        db.query(
            LeadParceiro,
            Estado,
            Cidade,
        )
        .join(
            Estado,
            Estado.estado_id
            == LeadParceiro.estado_id,
        )
        .join(
            Cidade,
            Cidade.cidade_id
            == LeadParceiro.cidade_id,
        )
        .filter(
            LeadParceiro.leadparceiro_id
            == leadparceiro_id,
        )
        .first()
    )


@router.post(
    "/interesse",
    response_model=LeadParceiroOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_interesse_parceiro(
    payload: LeadParceiroCreate,
    db: Session = Depends(get_db),
):
    estado = (
        db.query(Estado)
        .filter(
            Estado.estado_id == payload.estado_id,
        )
        .first()
    )

    if not estado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado não encontrado.",
        )

    cidade = (
        db.query(Cidade)
        .filter(
            Cidade.cidade_id == payload.cidade_id,
        )
        .first()
    )

    if not cidade:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cidade não encontrada.",
        )

    if cidade.estado_id != payload.estado_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A cidade informada não pertence "
                "ao estado selecionado."
            ),
        )

    lead = LeadParceiro(
        nmresponsavel=payload.nmresponsavel,
        nmestabelecimento=payload.nmestabelecimento,
        tipo=payload.tipo,
        telefone=payload.telefone,
        email=payload.email,
        estado_id=payload.estado_id,
        cidade_id=payload.cidade_id,
        mensagem=payload.mensagem,
    )

    db.add(lead)
    db.commit()
    db.refresh(lead)

    return _serializar_lead(
        lead,
        estado,
        cidade,
    )


@router.get(
    "",
    response_model=list[LeadParceiroOut],
)
def listar_interesses_parceiros(
    db: Session = Depends(get_db),
):
    prioridade_status = case(
        (LeadParceiro.status == "NOVO", 1),
        (LeadParceiro.status == "CONTATADO", 2),
        (LeadParceiro.status == "NEGOCIANDO", 3),
        (LeadParceiro.status == "CONVERTIDO", 4),
        (LeadParceiro.status == "PERDIDO", 5),
        else_=6,
    )

    resultados = (
        db.query(
            LeadParceiro,
            Estado,
            Cidade,
        )
        .join(
            Estado,
            Estado.estado_id
            == LeadParceiro.estado_id,
        )
        .join(
            Cidade,
            Cidade.cidade_id
            == LeadParceiro.cidade_id,
        )
        .order_by(
            prioridade_status.asc(),
            LeadParceiro.dtcriacao.asc(),
        )
        .all()
    )

    return [
        _serializar_lead(
            lead,
            estado,
            cidade,
        )
        for lead, estado, cidade in resultados
    ]


@router.get(
    "/{leadparceiro_id}",
    response_model=LeadParceiroOut,
)
def buscar_interesse_parceiro(
    leadparceiro_id: int,
    db: Session = Depends(get_db),
):
    resultado = _buscar_lead_com_localidade(
        db,
        leadparceiro_id,
    )

    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead não encontrado.",
        )

    lead, estado, cidade = resultado

    return _serializar_lead(
        lead,
        estado,
        cidade,
    )


@router.put(
    "/{leadparceiro_id}",
    response_model=LeadParceiroOut,
)
def atualizar_interesse_parceiro(
    leadparceiro_id: int,
    payload: LeadParceiroUpdate,
    db: Session = Depends(get_db),
):
    lead = (
        db.query(LeadParceiro)
        .filter(
            LeadParceiro.leadparceiro_id
            == leadparceiro_id,
        )
        .first()
    )

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead não encontrado.",
        )

    if payload.nmresponsavel is not None:
        lead.nmresponsavel = (
            payload.nmresponsavel
        )

    if payload.tipo is not None:
        lead.tipo = payload.tipo

    if payload.telefone is not None:
        lead.telefone = payload.telefone

    if payload.email is not None:
        lead.email = payload.email

    if payload.status is not None:
        lead.status = payload.status

    db.commit()
    db.refresh(lead)

    resultado = _buscar_lead_com_localidade(
        db,
        leadparceiro_id,
    )

    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead não encontrado após atualização.",
        )

    lead_atualizado, estado, cidade = resultado

    return _serializar_lead(
        lead_atualizado,
        estado,
        cidade,
    )