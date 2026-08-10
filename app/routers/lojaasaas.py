from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import APP_ENV
from app.core.credential_crypto import criptografar_credencial, hash_token_webhook
from app.core.security import get_usuario_logado
from app.core.permissoes_loja import validar_mutacao_loja
from app.database import get_db
from app.models.loja import Loja
from app.models.lojaasaas import LojaAsaas
from app.schemas.lojaasaas import LojaAsaasConfigIn, LojaAsaasConfigOut


router = APIRouter(prefix="/lojas", tags=["Integração Asaas das lojas"])


def _loja_autorizada(db: Session, loja_id: int, usuario: dict) -> Loja:
    if usuario.get("role") != "usuario":
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    try:
        organizacao_id = int(usuario.get("organizacao_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=403, detail="Token sem organização válida")
    loja = db.query(Loja).filter(
        Loja.loja_id == loja_id,
        Loja.organizacao_id == organizacao_id,
    ).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada na organização")
    validar_mutacao_loja(usuario, loja.organizacao_id, loja.loja_id)
    return loja


def _saida(config: LojaAsaas) -> dict:
    return {
        "loja_id": config.loja_id,
        "organizacao_id": config.organizacao_id,
        "ambiente": config.ambiente,
        "asaas_account_id": config.asaas_account_id,
        "asaas_wallet_id": config.asaas_wallet_id,
        "statusintegracao": config.statusintegracao,
        "configurada": True,
    }


@router.get("/{loja_id}/asaas", response_model=LojaAsaasConfigOut)
def consultar_configuracao_asaas(
    loja_id: int,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    _loja_autorizada(db, loja_id, usuario)
    config = db.query(LojaAsaas).filter(
        LojaAsaas.loja_id == loja_id,
        LojaAsaas.ambiente == APP_ENV,
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Integração Asaas não configurada")
    return _saida(config)


@router.put("/{loja_id}/asaas", response_model=LojaAsaasConfigOut)
def configurar_conta_asaas(
    loja_id: int,
    payload: LojaAsaasConfigIn,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    loja = _loja_autorizada(db, loja_id, usuario)
    try:
        config = db.query(LojaAsaas).filter(
            LojaAsaas.loja_id == loja_id,
            LojaAsaas.ambiente == APP_ENV,
        ).first()
        if not config:
            config = LojaAsaas(
                loja_id=loja_id,
                organizacao_id=loja.organizacao_id,
                ambiente=APP_ENV,
            )
            db.add(config)

        config.asaas_account_id = payload.asaas_account_id
        config.asaas_wallet_id = payload.asaas_wallet_id
        config.asaas_api_key_criptografada = criptografar_credencial(payload.asaas_api_key)
        config.webhook_token_hash = hash_token_webhook(payload.webhook_token)
        config.statusintegracao = payload.statusintegracao

        db.commit()
        db.refresh(config)
        return _saida(config)
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Token de webhook ou integração Asaas já cadastrada",
        ) from erro
    except HTTPException:
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao configurar integração Asaas") from erro
