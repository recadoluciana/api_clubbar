from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.campanha_promocional import CampanhaPromocional
from app.models.loja import Loja
from app.models.cliente import Cliente
from app.models.consentimento_promocao import ConsentimentoPromocao
from app.models.dispositivo_promocao import DispositivoPromocao
from app.models.envio_campanha_promocional import EnvioCampanhaPromocional
from app.database import SessionLocal
from app.services.envio_promocoes_service import enviar_email_promocional, enviar_push_promocional, verificar_configuracao_push, CanalIndisponivel
from app.routers.painel_gerencial import _extrair_escopo


router = APIRouter(prefix='/campanhas-promocionais', tags=['Campanhas promocionais'])


class CampanhaIn(BaseModel):
    loja_id: int = Field(gt=0)
    titulo: str = Field(min_length=1, max_length=100)
    mensagem: str = Field(min_length=1, max_length=1024)


class EnvioIn(BaseModel):
    push: bool = False
    email: bool = False


def _loja_permitida(loja_id: int, usuario: dict, db: Session) -> Loja:
    organizacao_id, loja_restrita = _extrair_escopo(usuario)
    if loja_restrita is not None and loja_restrita != loja_id:
        raise HTTPException(403, 'Acesso negado para este estabelecimento')
    loja = db.query(Loja).filter(Loja.loja_id == loja_id, Loja.organizacao_id == organizacao_id).first()
    if loja is None:
        raise HTTPException(404, 'Estabelecimento não encontrado')
    return loja


def _saida(c: CampanhaPromocional) -> dict:
    return {'id': c.id, 'loja_id': c.loja_id, 'titulo': c.titulo, 'mensagem': c.mensagem,
            'status': c.status, 'criado_em': c.criado_em}


def _processar_envios(campanha_id: int) -> None:
    """Marca cada tentativa antes do envio; falhas incertas não são repetidas automaticamente."""
    with SessionLocal() as db:
        ids = [r[0] for r in db.query(EnvioCampanhaPromocional.id).filter_by(campanha_id=campanha_id, status='PENDENTE').all()]
        for envio_id in ids:
            envio = db.query(EnvioCampanhaPromocional).filter_by(id=envio_id).with_for_update().first()
            if not envio or envio.status != 'PENDENTE':
                db.rollback()
                continue
            campanha = db.query(CampanhaPromocional).filter_by(id=campanha_id).first()
            consentimento = db.query(ConsentimentoPromocao).filter_by(cliente_id=envio.cliente_id, loja_id=campanha.loja_id).first()
            cliente = db.query(Cliente).filter_by(cliente_id=envio.cliente_id, sitcliente='ATIVO').first()
            dispositivo = db.query(DispositivoPromocao).filter_by(id=envio.dispositivo_id, cliente_id=envio.cliente_id).first() if envio.dispositivo_id else None
            permitido = bool(cliente and consentimento and getattr(consentimento, envio.canal, False))
            destinatario = (dispositivo.token if dispositivo else None) if envio.canal == 'push' else (cliente.emailcliente if cliente else None)
            if not permitido or not destinatario:
                envio.status = 'IGNORADO'
                db.commit()
                continue
            titulo, mensagem, canal = campanha.titulo, campanha.mensagem, envio.canal
            envio.status = 'PROCESSANDO'
            db.commit()
            try:
                if canal == 'push':
                    enviar_push_promocional(token_dispositivo=destinatario, titulo=titulo, mensagem=mensagem)
                else:
                    enviar_email_promocional(destinatario=destinatario, titulo=titulo, mensagem=mensagem)
                envio.status = 'ENVIADO'
            except Exception:
                envio.status = 'FALHA'
            db.commit()
        campanha = db.query(CampanhaPromocional).filter_by(id=campanha_id).with_for_update().first()
        if campanha:
            estados = [r[0] for r in db.query(EnvioCampanhaPromocional.status).filter_by(campanha_id=campanha_id).all()]
            campanha.status = 'EM_ENVIO' if any(s in {'PENDENTE', 'PROCESSANDO'} for s in estados) else ('CONCLUIDA' if all(s in {'ENVIADO', 'IGNORADO'} for s in estados) else 'CONCLUIDA_COM_FALHAS')
            db.commit()


@router.get('/{campanha_id}/resultado')
def resultado(campanha_id: int, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    campanha = db.query(CampanhaPromocional).filter_by(id=campanha_id).first()
    if not campanha:
        raise HTTPException(404, 'Campanha não encontrada')
    _loja_permitida(campanha.loja_id, usuario, db)
    contagem = {}
    for envio in db.query(EnvioCampanhaPromocional).filter_by(campanha_id=campanha_id).all():
        chave = f'{envio.canal}_{envio.status.lower()}'
        contagem[chave] = contagem.get(chave, 0) + 1
    return {**_saida(campanha), 'entregas': contagem}


@router.post('/{campanha_id}/enviar')
def enviar(campanha_id: int, dados: EnvioIn, background: BackgroundTasks, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    campanha = db.query(CampanhaPromocional).filter_by(id=campanha_id).with_for_update().first()
    if not campanha:
        raise HTTPException(404, 'Campanha não encontrada')
    _loja_permitida(campanha.loja_id, usuario, db)
    if campanha.status != 'RASCUNHO':
        raise HTTPException(409, 'Esta campanha já foi enviada ou está em processamento.')
    if not dados.push and not dados.email:
        raise HTTPException(422, 'Selecione ao menos um canal.')
    if dados.push:
        try:
            verificar_configuracao_push()
        except CanalIndisponivel as exc:
            raise HTTPException(503, str(exc)) from exc
    total = 0
    if dados.push:
        dispositivos = (db.query(DispositivoPromocao).join(ConsentimentoPromocao, ConsentimentoPromocao.cliente_id == DispositivoPromocao.cliente_id)
                        .join(Cliente, Cliente.cliente_id == DispositivoPromocao.cliente_id)
                        .filter(ConsentimentoPromocao.loja_id == campanha.loja_id, ConsentimentoPromocao.push.is_(True), Cliente.sitcliente == 'ATIVO').all())
        for dispositivo in dispositivos:
            db.add(EnvioCampanhaPromocional(campanha_id=campanha.id, cliente_id=dispositivo.cliente_id, dispositivo_id=dispositivo.id, destinatario_chave=f'p:{dispositivo.id}', canal='push'))
            total += 1
    if dados.email:
        clientes = (db.query(Cliente).join(ConsentimentoPromocao, ConsentimentoPromocao.cliente_id == Cliente.cliente_id)
                    .filter(ConsentimentoPromocao.loja_id == campanha.loja_id, ConsentimentoPromocao.email.is_(True), Cliente.sitcliente == 'ATIVO', Cliente.emailcliente.isnot(None), Cliente.emailcliente != '').all())
        for cliente in clientes:
            db.add(EnvioCampanhaPromocional(campanha_id=campanha.id, cliente_id=cliente.cliente_id, destinatario_chave=f'e:{cliente.cliente_id}', canal='email'))
            total += 1
    if not total:
        raise HTTPException(409, 'Não há clientes autorizados com e-mail ou dispositivo cadastrado para os canais selecionados.')
    campanha.status = 'EM_ENVIO'
    db.commit()
    background.add_task(_processar_envios, campanha.id)
    return {'status': campanha.status, 'destinatarios': total}


@router.post('/{campanha_id}/retomar')
def retomar(campanha_id: int, background: BackgroundTasks, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    campanha = db.query(CampanhaPromocional).filter_by(id=campanha_id).first()
    if not campanha:
        raise HTTPException(404, 'Campanha não encontrada')
    _loja_permitida(campanha.loja_id, usuario, db)
    if campanha.status != 'EM_ENVIO':
        raise HTTPException(409, 'Esta campanha não está em envio.')
    background.add_task(_processar_envios, campanha.id)
    return {'status': campanha.status}


@router.get('/lojas/{loja_id}')
def listar(loja_id: int, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    _loja_permitida(loja_id, usuario, db)
    campanhas = db.query(CampanhaPromocional).filter_by(loja_id=loja_id).order_by(CampanhaPromocional.id.desc()).limit(100).all()
    return [_saida(c) for c in campanhas]


@router.post('', status_code=201)
def criar(dados: CampanhaIn, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    _loja_permitida(dados.loja_id, usuario, db)
    titulo, mensagem = dados.titulo.strip(), dados.mensagem.strip()
    if not titulo or not mensagem:
        raise HTTPException(422, 'Informe título e mensagem.')
    try:
        usuario_id = int(usuario.get('sub'))
    except (TypeError, ValueError):
        raise HTTPException(401, 'Sessão inválida')
    campanha = CampanhaPromocional(loja_id=dados.loja_id, titulo=titulo, mensagem=mensagem, status='RASCUNHO', criado_por=usuario_id)
    db.add(campanha)
    db.commit()
    db.refresh(campanha)
    return _saida(campanha)
