import hashlib
import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.dispositivo_promocao import DispositivoPromocao
from app.models.envio_campanha_promocional import EnvioCampanhaPromocional
from app.models.campanha_promocional import CampanhaPromocional
from app.models.loja import Loja
from app.routers.consentimento_promocao import _cliente
from app.services.envio_promocoes_service import enviar_push_promocional, CanalIndisponivel, FalhaEnvio

router = APIRouter(prefix="/clientes/me/dispositivos-promocao", tags=["Dispositivos de promoções"])
logger = logging.getLogger(__name__)


class DispositivoIn(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    plataforma: Literal["android", "ios"]


def _hash(token: str) -> str:
    if not token or token != token.strip():
        raise HTTPException(422, "Token de dispositivo inválido")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.get('/notificacoes')
def listar_notificacoes(usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    cliente = _cliente(usuario, db)
    campanhas = (db.query(CampanhaPromocional, Loja.nmloja)
                 .join(EnvioCampanhaPromocional, EnvioCampanhaPromocional.campanha_id == CampanhaPromocional.id)
                 .join(Loja, Loja.loja_id == CampanhaPromocional.loja_id)
                 .filter(EnvioCampanhaPromocional.cliente_id == cliente.cliente_id,
                         EnvioCampanhaPromocional.canal == 'push',
                         EnvioCampanhaPromocional.status == 'ENVIADO')
                 .distinct().order_by(CampanhaPromocional.id.desc()).limit(100).all())
    return [{'id': campanha.id, 'titulo': campanha.titulo, 'mensagem': campanha.mensagem,
             'estabelecimento': nome, 'criado_em': campanha.criado_em}
            for campanha, nome in campanhas]


@router.put('/notificacoes/{envio_id}/clique')
def registrar_clique(envio_id: int, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    cliente = _cliente(usuario, db)
    envio = db.query(EnvioCampanhaPromocional).filter_by(id=envio_id, cliente_id=cliente.cliente_id, canal='push').first()
    if not envio:
        raise HTTPException(404, 'Notificação não encontrada')
    if envio.clicado_em is None:
        envio.clicado_em = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    return {'registrado': True}


@router.put("")
def registrar(dados: DispositivoIn, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    cliente = _cliente(usuario, db)
    digest = _hash(dados.token)
    registro = db.query(DispositivoPromocao).filter_by(token_hash=digest).first()
    if registro is None:
        registro = DispositivoPromocao(token_hash=digest)
        db.add(registro)
    registro.cliente_id = cliente.cliente_id
    registro.token = dados.token
    registro.plataforma = dados.plataforma
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Não foi possível registrar o dispositivo. Tente novamente.")
    return {"registrado": True}


@router.post("/remover")
def remover(dados: DispositivoIn, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    cliente = _cliente(usuario, db)
    digest = _hash(dados.token)
    db.query(DispositivoPromocao).filter_by(cliente_id=cliente.cliente_id, token_hash=digest).delete(synchronize_session=False)
    db.commit()
    return {"removido": True}


@router.post('/teste')
def testar(dados: DispositivoIn, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    cliente = _cliente(usuario, db)
    dispositivo = db.query(DispositivoPromocao).filter_by(cliente_id=cliente.cliente_id, token_hash=_hash(dados.token)).first()
    if not dispositivo:
        raise HTTPException(404, 'Este aparelho ainda não foi registrado para receber notificações.')
    logger.warning('Teste de notificação solicitado: dispositivo_id=%s plataforma=%s', dispositivo.id, dispositivo.plataforma)
    try:
        enviar_push_promocional(token_dispositivo=dispositivo.token, titulo='Teste Clubbar', mensagem='Suas notificações estão funcionando!', plataforma=dispositivo.plataforma)
    except (CanalIndisponivel, FalhaEnvio) as exc:
        raise HTTPException(503, 'Não foi possível enviar a notificação de teste agora.') from exc
    return {'aceito': True}
