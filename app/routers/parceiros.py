#parceiros.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.lead_parceiro import LeadParceiro
from app.schemas.lead_parceiro import LeadParceiroCreate, LeadParceiroOut


router = APIRouter(prefix="/parceiros", tags=["Parceiros"])


@router.post(
    "/interesse",
    response_model=LeadParceiroOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_interesse_parceiro(
    payload: LeadParceiroCreate,
    db: Session = Depends(get_db),
):
    tipo = payload.tipo.strip().upper()

    tipos_validos = {"BAR", "CASA_NOTURNA", "EVENTO"}

    if tipo not in tipos_validos:
        raise HTTPException(
            status_code=400,
            detail="Tipo inválido. Use BAR, CASA_NOTURNA ou EVENTO.",
        )

    lead = LeadParceiro(
        nome_responsavel=payload.nome_responsavel.strip(),
        nome_estabelecimento=payload.nome_estabelecimento.strip(),
        tipo=tipo,
        telefone=payload.telefone.strip(),
        email=payload.email.strip().lower(),
        cidade=payload.cidade.strip(),
        mensagem=payload.mensagem.strip() if payload.mensagem else None,
        status="NOVO",
    )

    db.add(lead)
    db.commit()
    db.refresh(lead)

    return lead


@router.get("", response_model=list[LeadParceiroOut])
def listar_interesses_parceiros(
    db: Session = Depends(get_db),
):
    return (
        db.query(LeadParceiro)
        .order_by(LeadParceiro.lead_parceiro_id.desc())
        .all()
    )