import re
import unicodedata
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

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.leadparceiro import LeadParceiro
from app.models.loja import Loja
from app.models.organizacao import Organizacao

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

def _somente_numeros(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _normalizar_texto(valor: str) -> str:
    texto = unicodedata.normalize(
        "NFD",
        valor.strip().lower(),
    )

    return "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )


def _nome_loja_por_tipo(tipo: str) -> str:
    tipo_normalizado = (
        _normalizar_texto(tipo)
        .replace("-", " ")
        .replace("_", " ")
    )

    if tipo_normalizado == "bar":
        return "Meu Bar"

    if tipo_normalizado in {
        "casa noturna",
        "casanoturna",
        "boate",
    }:
        return "Minha Casa Noturna"

    if tipo_normalizado in {
        "eventos",
        "evento",
        "empresa de eventos",
    }:
        return "Empresa de Eventos"

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            f'Tipo de estabelecimento não reconhecido: "{tipo}".'
        ),
    )
    
@router.post(
    "/{leadparceiro_id}/converter-em-parceiro",
    status_code=status.HTTP_201_CREATED,
)
def converter_lead_em_parceiro(
    leadparceiro_id: int,
    dados: ConverterLeadParceiroIn,
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
            detail="Lead parceiro não encontrado.",
        )

    if lead.status == "CONVERTIDO":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este lead já foi convertido em parceiro.",
        )

    if lead.status == "PERDIDO":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Um lead marcado como perdido não pode "
                "ser convertido."
            ),
        )

    cnpj = _somente_numeros(dados.cnpj)

    if len(cnpj) != 14:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O CNPJ deve possuir 14 números.",
        )

    organizacao_existente = (
        db.query(Organizacao)
        .filter(
            Organizacao.cnpjorganizacao == cnpj,
        )
        .first()
    )

    if organizacao_existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma organização com este CNPJ.",
        )

    nome_loja = _nome_loja_por_tipo(lead.tipo)

    endereco_loja = (
        f"{dados.endereco.strip()}, "
        f"{dados.numero.strip()}"
    )

    try:
        nova_organizacao = Organizacao(
            nmorganizacao=lead.nmestabelecimento.strip(),
            rzsocialorganizacao=dados.razao_social.strip(),
            cnpjorganizacao=cnpj,
            emailorganizacao=lead.email.strip().lower(),
            telorganizacao=lead.telefone.strip(),
            ceporganizacao=(
                dados.cep.strip()
                if dados.cep
                else None
            ),
            endorganizacao=dados.endereco.strip(),
            nrendorganizacao=dados.numero.strip(),
            complorganizacao=(
                dados.complemento.strip()
                if dados.complemento
                else None
            ),
            cidade_id=lead.cidade_id,
            nmbairro=(
                dados.bairro.strip()
                if dados.bairro
                else None
            ),
            sitorganizacao="ATIVA",
        )

        db.add(nova_organizacao)

        # Obtém o organizacao_id sem finalizar a transação.
        db.flush()

        nova_loja = Loja(
            organizacao_id=nova_organizacao.organizacao_id,
            nmloja=nome_loja,
            endloja=endereco_loja,
            dsbairroloja=(
                dados.bairro.strip()
                if dados.bairro
                else None
            ),
            sitloja="ATIVA",
            aberto24x7="N",
            nrtelloja=lead.telefone.strip(),
            nrdiavalidade=90,
            cidade_id=lead.cidade_id,
            vrtaxaprod=5.00,
            vrtaxaing=5.00,
        )

        db.add(nova_loja)

        # Obtém o loja_id antes do commit.
        db.flush()

        lead.status = "CONVERTIDO"

        db.commit()

        db.refresh(nova_organizacao)
        db.refresh(nova_loja)
        db.refresh(lead)

        return {
            "ok": True,
            "mensagem": (
                "Lead convertido em parceiro com sucesso."
            ),
            "leadparceiro_id": lead.leadparceiro_id,
            "status_lead": lead.status,
            "tipo": lead.tipo,
            "organizacao": {
                "organizacao_id": (
                    nova_organizacao.organizacao_id
                ),
                "nome": nova_organizacao.nmorganizacao,
            },
            "loja": {
                "loja_id": nova_loja.loja_id,
                "nome": nova_loja.nmloja,
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as erro:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não foi possível converter o lead. "
                "Verifique se o CNPJ ou outro dado "
                "já está cadastrado."
            ),
        ) from erro

    except Exception as erro:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao converter o lead em parceiro.",
        ) from erro