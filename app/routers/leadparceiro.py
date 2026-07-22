# app/routers/parceiros.py

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cidade import Cidade
from app.models.estado import Estado
from app.models.lead_parceiro import LeadParceiro
from app.schemas.lead_parceiro import (
    LeadParceiroCreate,
    LeadParceiroOut,
)


router = APIRouter(
    prefix="/parceiros",
    tags=["Parceiros"],
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

    return lead


@router.get(
    "",
    response_model=list[LeadParceiroOut],
)
def listar_interesses_parceiros(
    db: Session = Depends(get_db),
):
    return (
        db.query(LeadParceiro)
        .order_by(
            LeadParceiro.leadparceiro_id.desc(),
        )
        .all()
    )