from datetime import datetime
import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado, get_usuario_logado
from app.database import get_db
from app.models.beneficioingresso import BeneficioIngresso
from app.models.eventolotepreco import EventoLotePreco
from app.models.modalidadebeneficio import ModalidadeBeneficio
from app.models.modalidadeingresso import ModalidadeIngresso


router = APIRouter(prefix="/ingressos-catalogo", tags=["Catálogo de ingressos"])


class ModalidadeIn(BaseModel):
    cdmodalidade: str | None = Field(default=None, max_length=40)
    nmmodalidade: str = Field(min_length=2, max_length=100)
    organizacao_id: int | None = None
    tipomodalidade: str = Field(pattern="^(PADRAO|LEGAL|COMERCIAL)$")
    aplicacotalegal: bool = False
    exigebeneficio: bool = False
    exigecomprovante: bool = False
    permitepersonalizarnome: bool = True
    situacao: str = Field(default="ATIVO", pattern="^(ATIVO|INATIVO)$")
    nrordem: int = Field(default=1, ge=1)
    beneficios_ids: list[int] = Field(default_factory=list)


class BeneficioIn(BaseModel):
    cdbeneficio: str | None = Field(default=None, max_length=40)
    nmbeneficio: str = Field(min_length=2, max_length=100)
    exigecomprovante: bool = True
    situacao: str = Field(default="ATIVO", pattern="^(ATIVO|INATIVO)$")
    nrordem: int = Field(default=1, ge=1)
    dtiniciovigencia: datetime | None = None
    dtfimvigencia: datetime | None = None


def _beneficio_out(item: BeneficioIngresso) -> dict:
    return {
        "beneficio_id": item.beneficio_id,
        "organizacao_id": item.organizacao_id,
        "cdbeneficio": item.cdbeneficio,
        "nmbeneficio": item.nmbeneficio,
        "exigecomprovante": bool(item.exigecomprovante),
        "situacao": item.situacao,
        "nrordem": int(item.nrordem),
        "dtiniciovigencia": item.dtiniciovigencia,
        "dtfimvigencia": item.dtfimvigencia,
    }


def _modalidade_out(db: Session, item: ModalidadeIngresso) -> dict:
    beneficios = (
        db.query(BeneficioIngresso)
        .join(ModalidadeBeneficio, ModalidadeBeneficio.beneficio_id == BeneficioIngresso.beneficio_id)
        .filter(ModalidadeBeneficio.modalidade_id == item.modalidade_id)
        .order_by(BeneficioIngresso.nrordem, BeneficioIngresso.nmbeneficio)
        .all()
    )
    return {
        "modalidade_id": item.modalidade_id,
        "organizacao_id": item.organizacao_id,
        "cdmodalidade": item.cdmodalidade,
        "nmmodalidade": item.nmmodalidade,
        "tipomodalidade": item.tipomodalidade,
        "aplicacotalegal": bool(item.aplicacotalegal),
        "exigebeneficio": bool(item.exigebeneficio),
        "exigecomprovante": bool(item.exigecomprovante),
        "permitepersonalizarnome": bool(item.permitepersonalizarnome),
        "situacao": item.situacao,
        "nrordem": int(item.nrordem),
        "beneficios": [_beneficio_out(i) for i in beneficios],
    }


def _sincronizar_beneficios(
    db: Session,
    modalidade: ModalidadeIngresso,
    ids: list[int],
    organizacao_id: int | None = None,
) -> None:
    ids_unicos = sorted(set(ids)) if modalidade.exigebeneficio else []
    if ids_unicos:
        query = db.query(BeneficioIngresso.beneficio_id).filter(
            BeneficioIngresso.beneficio_id.in_(ids_unicos)
        )
        if organizacao_id is None:
            query = query.filter(BeneficioIngresso.organizacao_id.is_(None))
        else:
            query = query.filter(
                or_(
                    BeneficioIngresso.organizacao_id.is_(None),
                    BeneficioIngresso.organizacao_id == organizacao_id,
                )
            )
        encontrados = query.all()
        if len(encontrados) != len(ids_unicos):
            raise HTTPException(422, "Há benefícios inexistentes na seleção")
    db.query(ModalidadeBeneficio).filter(ModalidadeBeneficio.modalidade_id == modalidade.modalidade_id).delete()
    db.add_all(ModalidadeBeneficio(modalidade_id=modalidade.modalidade_id, beneficio_id=i) for i in ids_unicos)


def _codigo_obrigatorio(codigo: str | None, descricao: str) -> str:
    valor = (codigo or "").strip().upper()
    if len(valor) < 2:
        raise HTTPException(422, f"Informe o código da {descricao}.")
    return valor


def _codigo_automatico(db: Session, modelo, atributo: str, prefixo: str, organizacao_id: int, nome: str) -> str:
    """Gera um código interno estável e único, sem expor esse detalhe ao parceiro."""
    normalizado = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    sufixo = re.sub(r"[^A-Z0-9]+", "_", normalizado.upper()).strip("_") or "ITEM"
    base = f"{prefixo}_{organizacao_id}_{sufixo}"[:40].rstrip("_")
    codigo = base
    indice = 2
    coluna = getattr(modelo, atributo)
    while db.query(modelo).filter(coluna == codigo).first():
        complemento = f"_{indice}"
        codigo = f"{base[: 40 - len(complemento)]}{complemento}"
        indice += 1
    return codigo


@router.get("/beneficios")
def listar_beneficios(incluir_inativos: bool = False, db: Session = Depends(get_db)):
    query = db.query(BeneficioIngresso).filter(BeneficioIngresso.organizacao_id.is_(None))
    if not incluir_inativos:
        query = query.filter(BeneficioIngresso.situacao == "ATIVO")
    return [_beneficio_out(i) for i in query.order_by(BeneficioIngresso.nrordem, BeneficioIngresso.nmbeneficio).all()]


@router.get("/modalidades")
def listar_modalidades(organizacao_id: int | None = None, incluir_inativos: bool = False, db: Session = Depends(get_db)):
    query = db.query(ModalidadeIngresso)
    if organizacao_id is None:
        query = query.filter(ModalidadeIngresso.organizacao_id.is_(None))
    else:
        query = query.filter(or_(ModalidadeIngresso.organizacao_id.is_(None), ModalidadeIngresso.organizacao_id == organizacao_id))
    if not incluir_inativos:
        query = query.filter(ModalidadeIngresso.situacao == "ATIVO")
    return [_modalidade_out(db, i) for i in query.order_by(ModalidadeIngresso.nrordem, ModalidadeIngresso.nmmodalidade).all()]


@router.post("/beneficios", status_code=status.HTTP_201_CREATED)
def criar_beneficio(dados: BeneficioIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    codigo = _codigo_obrigatorio(dados.cdbeneficio, "benefício")
    if db.query(BeneficioIngresso).filter(BeneficioIngresso.cdbeneficio == codigo).first():
        raise HTTPException(409, "Já existe um benefício com este código")
    item = BeneficioIngresso(**dados.model_dump(exclude={"cdbeneficio"}), cdbeneficio=codigo)
    db.add(item); db.commit(); db.refresh(item)
    return _beneficio_out(item)


@router.put("/beneficios/{beneficio_id}")
def alterar_beneficio(beneficio_id: int, dados: BeneficioIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(BeneficioIngresso).filter(BeneficioIngresso.beneficio_id == beneficio_id).first()
    if not item: raise HTTPException(404, "Benefício não encontrado")
    codigo = _codigo_obrigatorio(dados.cdbeneficio, "benefício")
    duplicado = db.query(BeneficioIngresso).filter(BeneficioIngresso.cdbeneficio == codigo, BeneficioIngresso.beneficio_id != beneficio_id).first()
    if duplicado: raise HTTPException(409, "Já existe um benefício com este código")
    for campo, valor in dados.model_dump().items(): setattr(item, campo, codigo if campo == "cdbeneficio" else valor)
    db.commit(); db.refresh(item)
    return _beneficio_out(item)


@router.post("/modalidades", status_code=status.HTTP_201_CREATED)
def criar_modalidade(dados: ModalidadeIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    codigo = _codigo_obrigatorio(dados.cdmodalidade, "modalidade")
    if db.query(ModalidadeIngresso).filter(ModalidadeIngresso.cdmodalidade == codigo).first():
        raise HTTPException(409, "Já existe uma modalidade com este código")
    item = ModalidadeIngresso(**dados.model_dump(exclude={"cdmodalidade", "beneficios_ids"}), cdmodalidade=codigo)
    db.add(item); db.flush(); _sincronizar_beneficios(db, item, dados.beneficios_ids)
    db.commit(); db.refresh(item)
    return _modalidade_out(db, item)


@router.put("/modalidades/{modalidade_id}")
def alterar_modalidade(modalidade_id: int, dados: ModalidadeIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(ModalidadeIngresso).filter(ModalidadeIngresso.modalidade_id == modalidade_id).first()
    if not item: raise HTTPException(404, "Modalidade não encontrada")
    codigo = _codigo_obrigatorio(dados.cdmodalidade, "modalidade")
    duplicado = db.query(ModalidadeIngresso).filter(ModalidadeIngresso.cdmodalidade == codigo, ModalidadeIngresso.modalidade_id != modalidade_id).first()
    if duplicado: raise HTTPException(409, "Já existe uma modalidade com este código")
    for campo, valor in dados.model_dump(exclude={"beneficios_ids"}).items(): setattr(item, campo, codigo if campo == "cdmodalidade" else valor)
    _sincronizar_beneficios(db, item, dados.beneficios_ids)
    db.commit(); db.refresh(item)
    return _modalidade_out(db, item)


@router.delete("/modalidades/{modalidade_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_modalidade(modalidade_id: int, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(ModalidadeIngresso).filter(ModalidadeIngresso.modalidade_id == modalidade_id).first()
    if not item: raise HTTPException(404, "Modalidade não encontrada")
    if db.query(EventoLotePreco.lotepreco_id).filter(EventoLotePreco.modalidade_id == modalidade_id).first():
        raise HTTPException(409, "Esta modalidade já foi utilizada. Inative-a em vez de excluir.")
    db.delete(item); db.commit()


@router.delete("/beneficios/{beneficio_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_beneficio(beneficio_id: int, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(BeneficioIngresso).filter(BeneficioIngresso.beneficio_id == beneficio_id).first()
    if not item: raise HTTPException(404, "Benefício não encontrado")
    if db.query(ModalidadeBeneficio).filter(ModalidadeBeneficio.beneficio_id == beneficio_id).first():
        raise HTTPException(409, "Este benefício está vinculado a uma modalidade. Remova o vínculo ou inative-o.")
    db.delete(item); db.commit()


# Catálogo da empresa parceira. Os itens padrão continuam disponíveis para
# seleção, mas somente itens criados pela própria organização podem ser
# alterados ou excluídos aqui.
def _organizacao_do_usuario(payload: dict) -> int:
    try:
        return int(payload["organizacao_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(403, "Organização não identificada.") from exc


def _item_da_organizacao(db: Session, modelo, item_id: int, organizacao_id: int, nome: str):
    item = db.query(modelo).filter(getattr(modelo, f"{nome}_id") == item_id).first()
    if not item:
        raise HTTPException(404, f"{nome.capitalize()} não encontrado.")
    if item.organizacao_id != organizacao_id:
        raise HTTPException(403, f"Somente {nome}s cadastrados pela sua empresa podem ser alterados.")
    return item


@router.get("/parceiro/beneficios")
def listar_beneficios_parceiro(
    incluir_inativos: bool = False,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    organizacao_id = _organizacao_do_usuario(payload)
    query = db.query(BeneficioIngresso).filter(
        or_(
            BeneficioIngresso.organizacao_id.is_(None),
            BeneficioIngresso.organizacao_id == organizacao_id,
        )
    )
    if not incluir_inativos:
        query = query.filter(BeneficioIngresso.situacao == "ATIVO")
    return [_beneficio_out(i) for i in query.order_by(BeneficioIngresso.nrordem, BeneficioIngresso.nmbeneficio).all()]


@router.get("/parceiro/modalidades")
def listar_modalidades_parceiro(
    incluir_inativos: bool = False,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    organizacao_id = _organizacao_do_usuario(payload)
    query = db.query(ModalidadeIngresso).filter(
        or_(
            ModalidadeIngresso.organizacao_id.is_(None),
            ModalidadeIngresso.organizacao_id == organizacao_id,
        )
    )
    if not incluir_inativos:
        query = query.filter(ModalidadeIngresso.situacao == "ATIVO")
    return [_modalidade_out(db, i) for i in query.order_by(ModalidadeIngresso.nrordem, ModalidadeIngresso.nmmodalidade).all()]


@router.post("/parceiro/beneficios", status_code=status.HTTP_201_CREATED)
def criar_beneficio_parceiro(
    dados: BeneficioIn,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    organizacao_id = _organizacao_do_usuario(payload)
    codigo = _codigo_automatico(
        db,
        BeneficioIngresso,
        "cdbeneficio",
        "BEN",
        organizacao_id,
        dados.nmbeneficio,
    )
    item = BeneficioIngresso(
        **dados.model_dump(exclude={"cdbeneficio"}),
        organizacao_id=organizacao_id,
        cdbeneficio=codigo,
    )
    db.add(item); db.commit(); db.refresh(item)
    return _beneficio_out(item)


@router.put("/parceiro/beneficios/{beneficio_id}")
def alterar_beneficio_parceiro(
    beneficio_id: int,
    dados: BeneficioIn,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    item = _item_da_organizacao(db, BeneficioIngresso, beneficio_id, _organizacao_do_usuario(payload), "beneficio")
    for campo, valor in dados.model_dump(exclude={"cdbeneficio"}).items():
        setattr(item, campo, valor)
    db.commit(); db.refresh(item)
    return _beneficio_out(item)


@router.delete("/parceiro/beneficios/{beneficio_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_beneficio_parceiro(
    beneficio_id: int,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    item = _item_da_organizacao(db, BeneficioIngresso, beneficio_id, _organizacao_do_usuario(payload), "beneficio")
    if db.query(ModalidadeBeneficio).filter(ModalidadeBeneficio.beneficio_id == beneficio_id).first():
        raise HTTPException(409, "Este benefício está vinculado a uma modalidade. Inative-o em vez de excluir.")
    db.delete(item); db.commit()


@router.post("/parceiro/modalidades", status_code=status.HTTP_201_CREATED)
def criar_modalidade_parceiro(
    dados: ModalidadeIn,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    organizacao_id = _organizacao_do_usuario(payload)
    codigo = _codigo_automatico(
        db,
        ModalidadeIngresso,
        "cdmodalidade",
        "MOD",
        organizacao_id,
        dados.nmmodalidade,
    )
    item = ModalidadeIngresso(
        **dados.model_dump(exclude={"cdmodalidade", "beneficios_ids", "organizacao_id"}),
        organizacao_id=organizacao_id,
        cdmodalidade=codigo,
    )
    db.add(item); db.flush(); _sincronizar_beneficios(db, item, dados.beneficios_ids, organizacao_id)
    db.commit(); db.refresh(item)
    return _modalidade_out(db, item)


@router.put("/parceiro/modalidades/{modalidade_id}")
def alterar_modalidade_parceiro(
    modalidade_id: int,
    dados: ModalidadeIn,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    organizacao_id = _organizacao_do_usuario(payload)
    item = _item_da_organizacao(db, ModalidadeIngresso, modalidade_id, organizacao_id, "modalidade")
    for campo, valor in dados.model_dump(exclude={"beneficios_ids", "organizacao_id", "cdmodalidade"}).items():
        setattr(item, campo, valor)
    _sincronizar_beneficios(db, item, dados.beneficios_ids, organizacao_id)
    db.commit(); db.refresh(item)
    return _modalidade_out(db, item)


@router.delete("/parceiro/modalidades/{modalidade_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_modalidade_parceiro(
    modalidade_id: int,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    item = _item_da_organizacao(db, ModalidadeIngresso, modalidade_id, _organizacao_do_usuario(payload), "modalidade")
    if db.query(EventoLotePreco.lotepreco_id).filter(EventoLotePreco.modalidade_id == modalidade_id).first():
        raise HTTPException(409, "Esta modalidade já foi utilizada. Inative-a em vez de excluir.")
    db.delete(item); db.commit()
