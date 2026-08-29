import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado
from app.core.config import UPLOAD_MATERIAIS_LEAD
from app.database import get_db
from app.models.leadagendamento import LeadAgendamento
from app.models.leadmaterial import LeadMaterial
from app.models.leadmensagem import LeadMensagem
from app.models.leadparceiro import LeadParceiro
from app.models.leadestabelecimento import LeadEstabelecimento
from app.services.email_service import enviar_acesso_portal_lead
from app.services.portal_acesso_service import criar_acesso_portal


router = APIRouter(prefix='/lead-atendimento', tags=['Atendimento de leads'])
public_router = APIRouter(prefix='/portal-parceiro', tags=['Portal do parceiro'])


class MensagemIn(BaseModel):
    mensagem: str = Field(min_length=1, max_length=3000)


class AgendamentoIn(BaseModel):
    tipo: Literal['DEMONSTRACAO', 'LIGACAO', 'REUNIAO_ONLINE', 'VISITA']
    dtagendamento: datetime
    observacao: str | None = Field(default=None, max_length=500)


class StatusAgendamentoIn(BaseModel):
    status: Literal['PENDENTE', 'CONFIRMADO', 'RECUSADO', 'REALIZADO', 'CANCELADO']


class MaterialIn(BaseModel):
    titulo: str = Field(min_length=2, max_length=160)
    descricao: str | None = Field(default=None, max_length=500)
    tipo: Literal['APRESENTACAO', 'PROPOSTA', 'CONTRATO', 'VIDEO', 'OUTRO']
    urlarquivo: str = Field(min_length=5, max_length=500)


class SolicitarAcessoIn(BaseModel):
    email: EmailStr


def _lead(db: Session, lead_id: int) -> LeadParceiro:
    item = db.query(LeadParceiro).filter(LeadParceiro.leadparceiro_id == lead_id).first()
    if not item:
        raise HTTPException(status_code=404, detail='Lead nao encontrado')
    return item


@router.get('/{lead_id}')
def consultar(lead_id: int, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    lead = _lead(db, lead_id)
    mensagens = db.query(LeadMensagem).filter(LeadMensagem.leadparceiro_id == lead_id).order_by(LeadMensagem.dtcriacao).all()
    for item in mensagens:
        if item.origem == 'LEAD' and item.lida == 'N':
            item.lida = 'S'
    db.commit()
    agendamentos = db.query(LeadAgendamento).filter(LeadAgendamento.leadparceiro_id == lead_id).order_by(LeadAgendamento.dtagendamento.desc()).all()
    materiais = db.query(LeadMaterial).filter(LeadMaterial.leadparceiro_id == lead_id).order_by(LeadMaterial.dtcriacao.desc()).all()
    primeiro_estabelecimento = db.query(LeadEstabelecimento).filter(
        LeadEstabelecimento.leadparceiro_id == lead_id
    ).order_by(LeadEstabelecimento.leadestabelecimento_id.asc()).first()
    return {
        'decisao': primeiro_estabelecimento.decisao if primeiro_estabelecimento else 'PENDENTE',
        'mensagens': [{'leadmensagem_id': x.leadmensagem_id, 'origem': x.origem, 'mensagem': x.mensagem, 'lida': x.lida, 'dtcriacao': x.dtcriacao} for x in mensagens],
        'agendamentos': [{'leadagendamento_id': x.leadagendamento_id, 'tipo': x.tipo, 'dtagendamento': x.dtagendamento, 'observacao': x.observacao, 'status': x.status} for x in agendamentos],
        'materiais': [{'leadmaterial_id': x.leadmaterial_id, 'titulo': x.titulo, 'descricao': x.descricao, 'tipo': x.tipo, 'urlarquivo': x.urlarquivo, 'dtcriacao': x.dtcriacao} for x in materiais],
    }


@router.post('/{lead_id}/mensagens', status_code=201)
def enviar_mensagem(lead_id: int, dados: MensagemIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    lead = _lead(db, lead_id)
    if lead.status == 'NOVO':
        lead.status = 'CONTATADO'
    item = LeadMensagem(leadparceiro_id=lead_id, origem='CLUBBAR', mensagem=dados.mensagem.strip(), lida='N')
    db.add(item)
    db.commit()
    return {'ok': True}


@router.post('/{lead_id}/agendamentos', status_code=201)
def criar_agendamento(lead_id: int, dados: AgendamentoIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    lead = _lead(db, lead_id)
    if lead.status in {'NOVO', 'CONTATADO'}:
        lead.status = 'NEGOCIANDO'
    item = LeadAgendamento(leadparceiro_id=lead_id, **dados.model_dump())
    db.add(item)
    db.commit()
    return {'ok': True}


@router.patch('/{lead_id}/agendamentos/{item_id}')
def alterar_agendamento(lead_id: int, item_id: int, dados: StatusAgendamentoIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(LeadAgendamento).filter(LeadAgendamento.leadparceiro_id == lead_id, LeadAgendamento.leadagendamento_id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail='Agendamento nao encontrado')
    item.status = dados.status
    db.commit()
    return {'ok': True}


@router.post('/{lead_id}/materiais', status_code=201)
def criar_material(lead_id: int, dados: MaterialIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    _lead(db, lead_id)
    item = LeadMaterial(leadparceiro_id=lead_id, **dados.model_dump())
    db.add(item)
    db.commit()
    return {'ok': True}


@router.post('/{lead_id}/materiais-upload', status_code=201)
def upload_material(
    lead_id: int,
    titulo: str = Form(...),
    descricao: str | None = Form(None),
    tipo: Literal['APRESENTACAO', 'PROPOSTA', 'CONTRATO', 'VIDEO', 'OUTRO'] = Form('OUTRO'),
    arquivo: UploadFile = File(...),
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    _lead(db, lead_id)
    extensao = Path(arquivo.filename or '').suffix.lower()
    permitidas = {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx'}
    if extensao not in permitidas:
        raise HTTPException(status_code=400, detail='Formato nao permitido. Envie PDF, imagem ou documento Office.')
    nome = f'{uuid.uuid4().hex}{extensao}'
    destino = UPLOAD_MATERIAIS_LEAD / nome
    try:
        with destino.open('wb') as saida:
            shutil.copyfileobj(arquivo.file, saida)
        if destino.stat().st_size > 20 * 1024 * 1024:
            destino.unlink(missing_ok=True)
            raise HTTPException(status_code=413, detail='O arquivo deve ter no maximo 20 MB.')
        item = LeadMaterial(
            leadparceiro_id=lead_id,
            titulo=titulo.strip(),
            descricao=descricao.strip() if descricao else None,
            tipo=tipo,
            urlarquivo=f'/uploads/materiais-lead/{nome}',
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return {'ok': True, 'leadmaterial_id': item.leadmaterial_id, 'urlarquivo': item.urlarquivo}
    except HTTPException:
        raise
    except Exception:
        destino.unlink(missing_ok=True)
        db.rollback()
        raise


@router.delete('/{lead_id}/materiais/{item_id}')
def excluir_material(lead_id: int, item_id: int, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(LeadMaterial).filter(LeadMaterial.leadparceiro_id == lead_id, LeadMaterial.leadmaterial_id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail='Material nao encontrado')
    db.delete(item)
    db.commit()
    return {'ok': True}


def _enviar_novo_acesso(db: Session, lead: LeadParceiro) -> None:
    token = criar_acesso_portal(db, leadparceiro_id=lead.leadparceiro_id)
    enviar_acesso_portal_lead(lead.email, lead.nmresponsavel, token)
    db.commit()


@router.post('/{lead_id}/reenviar-acesso')
def reenviar_acesso(lead_id: int, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    _enviar_novo_acesso(db, _lead(db, lead_id))
    return {'ok': True, 'mensagem': 'Novo acesso enviado por e-mail'}


@public_router.post('/solicitar-acesso', status_code=status.HTTP_202_ACCEPTED)
def solicitar_acesso(dados: SolicitarAcessoIn, db: Session = Depends(get_db)):
    lead = db.query(LeadParceiro).filter(LeadParceiro.email == dados.email.lower()).order_by(LeadParceiro.leadparceiro_id.desc()).first()
    if lead and lead.status != 'CONVERTIDO':
        _enviar_novo_acesso(db, lead)
    return {'mensagem': 'Se o e-mail estiver cadastrado, enviaremos um novo link de acesso.'}
