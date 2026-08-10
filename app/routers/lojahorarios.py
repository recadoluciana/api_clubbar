from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.core.permissoes_loja import validar_mutacao_loja
from app.database import get_db
from app.models.loja import Loja
from app.models.lojahorario import LojaHorario
from app.schemas.lojahorario import (
    LojaHorarioListaUpdate,
    LojaHorarioOut,
)


router = APIRouter(prefix="/lojas", tags=["Horários das lojas"])


def _buscar_loja(db: Session, loja_id: int) -> Loja:
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if loja is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loja não encontrada.",
        )
    return loja


def _validar_organizacao(usuario: dict, loja: Loja) -> None:
    if usuario.get("role") != "usuario":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas usuários autenticados podem atualizar horários.",
        )

    try:
        organizacao_id = int(usuario.get("organizacao_id"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token sem organização válida.",
        )

    if organizacao_id != loja.organizacao_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A loja não pertence à organização do usuário autenticado.",
        )


def _indexar_horarios(
    horarios: list[LojaHorario],
) -> dict[int, LojaHorario]:
    por_dia: dict[int, LojaHorario] = {}

    for horario in horarios:
        if horario.diasemana not in range(1, 8):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Existe horário cadastrado com dia da semana inválido.",
            )
        if horario.diasemana in por_dia:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Existem horários duplicados para a loja e o dia informado.",
            )
        por_dia[horario.diasemana] = horario

    return por_dia


@router.get(
    "/{loja_id}/horarios",
    response_model=list[LojaHorarioOut],
)
def listar_horarios(
    loja_id: int,
    db: Session = Depends(get_db),
):
    _buscar_loja(db, loja_id)

    horarios = (
        db.query(LojaHorario)
        .filter(LojaHorario.loja_id == loja_id)
        .order_by(LojaHorario.diasemana.asc())
        .all()
    )
    horarios_por_dia = _indexar_horarios(horarios)

    return [
        horarios_por_dia.get(dia)
        or LojaHorarioOut(
            loja_id=loja_id,
            diasemana=dia,
            fechado=True,
            horaabertura=None,
            horafechamento=None,
            fechadiaseguinte=False,
        )
        for dia in range(1, 8)
    ]


@router.put(
    "/{loja_id}/horarios",
    response_model=list[LojaHorarioOut],
)
def atualizar_horarios(
    loja_id: int,
    payload: LojaHorarioListaUpdate,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    loja = _buscar_loja(db, loja_id)
    _validar_organizacao(usuario, loja)
    validar_mutacao_loja(usuario, loja.organizacao_id, loja.loja_id)

    try:
        existentes = (
            db.query(LojaHorario)
            .filter(LojaHorario.loja_id == loja_id)
            .all()
        )
        por_dia = _indexar_horarios(existentes)

        for dados in payload.root:
            horario = por_dia.get(dados.diasemana)
            if horario is None:
                horario = LojaHorario(
                    loja_id=loja_id,
                    diasemana=dados.diasemana,
                )
                db.add(horario)
                por_dia[dados.diasemana] = horario

            horario.fechado = dados.fechado
            horario.horaabertura = dados.horaabertura
            horario.horafechamento = dados.horafechamento
            horario.fechadiaseguinte = dados.fechadiaseguinte

        db.flush()

        atualizados = (
            db.query(LojaHorario)
            .filter(LojaHorario.loja_id == loja_id)
            .order_by(LojaHorario.diasemana.asc())
            .all()
        )
        resposta = [LojaHorarioOut.model_validate(item) for item in atualizados]

        db.commit()
        return resposta

    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflito ao gravar os horários da loja.",
        ) from erro

    except Exception:
        db.rollback()
        raise
