from typing import Literal
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado
from app.database import get_db
from app.models.manual import Manual, ManualVersao
from app.services.manual_pdf import gerar_pdf

router = APIRouter(prefix="/manuais", tags=["Manuais do ecossistema"])
Publico = Literal["CLUBBAR", "LEAD", "PARCEIRO"]


class Etapa(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    titulo: str = Field(min_length=3, max_length=140)
    responsavel: Publico
    ambiente: Literal["SITE", "ADMIN", "PARTNER", "CLIENT"]
    caminho: str = Field(min_length=3, max_length=400)
    orientacoes: str = Field(min_length=10, max_length=12000)
    resultado: str = Field(min_length=3, max_length=1200)
    aviso: str = Field(default="", max_length=2000)


class PublicarManual(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    versao_base: int = Field(ge=1)
    titulo: str = Field(min_length=3, max_length=160)
    descricao: str = Field(min_length=10, max_length=3000)
    resumo_alteracao: str = Field(min_length=5, max_length=500)
    etapas: list[Etapa] = Field(min_length=1, max_length=80)


class VersaoBackup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    versao: int = Field(ge=1)
    titulo: str = Field(min_length=3, max_length=160)
    descricao: str = Field(min_length=10, max_length=3000)
    etapas: list[Etapa] = Field(min_length=1, max_length=80)
    resumo_alteracao: str = Field(min_length=5, max_length=500)
    operador_id: int | None = Field(default=None, ge=1)
    criado_em: datetime


class GuiaBackup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: Literal["negociacao-venda", "roteiro-implantacao", "manual-parceiro"]
    ordem: int = Field(ge=0, le=100)
    versoes: list[VersaoBackup] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validar_historico(self):
        numeros = sorted(v.versao for v in self.versoes)
        if numeros != list(range(1, len(numeros) + 1)):
            raise ValueError("O histórico deve conter versões únicas e completas, começando em 1.")
        publicos = {"negociacao-venda": {"CLUBBAR", "LEAD"},
                    "roteiro-implantacao": {"CLUBBAR"}, "manual-parceiro": {"PARCEIRO"}}
        if any(e.responsavel not in publicos[self.slug] for v in self.versoes for e in v.etapas):
            raise ValueError("Há etapas com público incorreto para este guia.")
        return self


class BackupManuais(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["clubbar.manuais"]
    formato: Literal[1]
    exportado_em: datetime
    manuais: list[GuiaBackup] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validar_guias(self):
        if len({m.slug for m in self.manuais}) != 3:
            raise ValueError("O backup deve conter os três guias, sem duplicação.")
        return self


@router.get("/backup/exportar")
def exportar_backup(_: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    manuais = db.query(Manual).order_by(Manual.manual_id).with_for_update().all()
    if len(manuais) != 3:
        raise HTTPException(409, "Cadastre os três manuais antes de exportar o backup.")
    dados = {"tipo": "clubbar.manuais", "formato": 1,
             "exportado_em": datetime.now(timezone.utc), "manuais": []}
    for m in manuais:
        versoes = db.query(ManualVersao).filter_by(manual_id=m.manual_id).order_by(ManualVersao.versao).all()
        dados["manuais"].append({"slug": m.slug, "ordem": m.ordem, "versoes": [
            {"versao": v.versao, "titulo": v.titulo, "descricao": v.descricao,
             "etapas": v.etapas, "resumo_alteracao": v.resumo_alteracao,
             "operador_id": v.operador_id, "criado_em": v.criado_em} for v in versoes]})
    backup = BackupManuais.model_validate(dados)
    conteudo = json.dumps(backup.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return Response(conteudo, media_type="application/json", headers={
        "Content-Disposition": 'attachment; filename="clubbar-manuais-backup.json"',
        "Cache-Control": "private, no-store",
    })


@router.post("/backup/importar")
def importar_backup(dados: BackupManuais, _: dict = Depends(get_operador_logado),
                    db: Session = Depends(get_db)):
    # Validate the complete payload before touching data; DML remains atomic.
    try:
        db.query(Manual).order_by(Manual.manual_id).with_for_update().all()
        db.query(ManualVersao).delete(synchronize_session=False)
        db.query(Manual).delete(synchronize_session=False)
        for guia in dados.manuais:
            manual = Manual(slug=guia.slug, ordem=guia.ordem)
            db.add(manual)
            db.flush()
            for versao in guia.versoes:
                campos = versao.model_dump(exclude={"criado_em"})
                data = versao.criado_em
                if data.tzinfo is not None:
                    data = data.astimezone(timezone.utc).replace(tzinfo=None)
                db.add(ManualVersao(manual_id=manual.manual_id, criado_em=data, **campos))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"manuais": len(dados.manuais), "versoes": sum(len(g.versoes) for g in dados.manuais)}


def _manual(db, slug):
    item = db.query(Manual).filter(Manual.slug == slug).first()
    if not item:
        raise HTTPException(404, "Manual não encontrado")
    return item


def _versao(db, manual_id, versao=None):
    q = db.query(ManualVersao).filter(ManualVersao.manual_id == manual_id)
    if versao is not None:
        q = q.filter(ManualVersao.versao == versao)
    item = q.order_by(ManualVersao.versao.desc()).first()
    if not item:
        raise HTTPException(404, "Versão não encontrada")
    return item


def _out(manual, item):
    return {"slug": manual.slug, "versao": item.versao, "titulo": item.titulo,
            "descricao": item.descricao, "etapas": item.etapas,
            "resumo_alteracao": item.resumo_alteracao, "criado_em": item.criado_em,
            "operador_id": item.operador_id}


@router.get("")
def listar(_: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    resultado = []
    for manual in db.query(Manual).order_by(Manual.ordem).all():
        item = _versao(db, manual.manual_id)
        resultado.append({**_out(manual, item), "total_etapas": len(item.etapas)})
    return resultado


@router.get("/{slug}")
def consultar(slug: str, versao: int | None = Query(default=None, ge=1),
              _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    manual = _manual(db, slug)
    item = _versao(db, manual.manual_id, versao)
    historico = db.query(ManualVersao).filter(ManualVersao.manual_id == manual.manual_id).order_by(ManualVersao.versao.desc()).all()
    return {**_out(manual, item), "versao_atual": historico[0].versao,
            "historico": [{"versao": v.versao, "criado_em": v.criado_em,
                           "resumo_alteracao": v.resumo_alteracao} for v in historico]}


@router.post("/{slug}/versoes", status_code=201)
def publicar(slug: str, dados: PublicarManual,
             operador: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    manual = db.query(Manual).filter(Manual.slug == slug).with_for_update().first()
    if not manual:
        raise HTTPException(404, "Manual não encontrado")
    atual = db.query(func.max(ManualVersao.versao)).filter(ManualVersao.manual_id == manual.manual_id).scalar()
    if atual != dados.versao_base:
        raise HTTPException(409, "Este manual foi atualizado. Recarregue a versão atual antes de publicar.")
    permitidos = {"negociacao-venda": {"CLUBBAR", "LEAD"},
                  "roteiro-implantacao": {"CLUBBAR"}, "manual-parceiro": {"PARCEIRO"}}
    if any(e.responsavel not in permitidos.get(slug, set()) for e in dados.etapas):
        raise HTTPException(422, "O responsável não corresponde ao público deste manual.")
    item = ManualVersao(manual_id=manual.manual_id, versao=atual + 1,
                        titulo=dados.titulo, descricao=dados.descricao,
                        etapas=[e.model_dump() for e in dados.etapas],
                        resumo_alteracao=dados.resumo_alteracao,
                        operador_id=int(operador["sub"]))
    db.add(item)
    db.commit()
    db.refresh(item)
    return _out(manual, item)


@router.get("/{slug}/pdf")
def pdf(slug: str, versao: int | None = Query(default=None, ge=1),
        publico: Publico | None = None, _: dict = Depends(get_operador_logado),
        db: Session = Depends(get_db)):
    manual = _manual(db, slug)
    dados = _out(manual, _versao(db, manual.manual_id, versao))
    if publico:
        dados["etapas"] = [e for e in dados["etapas"] if e["responsavel"] == publico]
        if not dados["etapas"]:
            raise HTTPException(404, "Não há etapas para este público")
    dados["publico_exportado"] = publico
    return Response(gerar_pdf(dados), media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{slug}-v{dados["versao"]}{"-" + publico.lower() if publico else ""}.pdf"',
        "Cache-Control": "private, no-store",
    })
