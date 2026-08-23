from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cashback_config import CashbackConfig
from app.models.cashback_movimento import CashbackMovimento
from app.models.cashback_saldo import CashbackSaldo
from app.models.loja import Loja
from app.services.cashback_service import atualizar_estados, dinheiro
from app.utils.datetime_utils import formatar_data_br

router = APIRouter(prefix="/cashback", tags=["Cashback"])


@router.get("/carteira")
def carteira(cliente_id: int, db: Session = Depends(get_db)):
    saldos = db.query(CashbackSaldo).filter(CashbackSaldo.cliente_id == cliente_id).all()
    for saldo in saldos:
        atualizar_estados(db, cliente_id, saldo.loja_id)
    db.commit()

    saldos = db.query(CashbackSaldo, Loja.nmloja).join(Loja, Loja.loja_id == CashbackSaldo.loja_id).filter(CashbackSaldo.cliente_id == cliente_id).all()
    movimentos = db.query(CashbackMovimento, Loja.nmloja).join(Loja, Loja.loja_id == CashbackMovimento.loja_id).filter(CashbackMovimento.cliente_id == cliente_id).order_by(CashbackMovimento.dtmovimento.desc()).limit(200).all()
    return {
        "saldo_disponivel": float(sum((dinheiro(s.vrdisponivel) for s, _ in saldos), dinheiro(0))),
        "saldo_pendente": float(sum((dinheiro(s.vrpendente) for s, _ in saldos), dinheiro(0))),
        "saldos_por_loja": [{"loja_id": s.loja_id, "nome_loja": nome, "saldo_disponivel": float(s.vrdisponivel or 0), "saldo_pendente": float(s.vrpendente or 0)} for s, nome in saldos],
        "movimentos": [{"cashback_movimento_id": m.cashback_movimento_id, "loja_id": m.loja_id, "nome_loja": nome, "tipo": m.tipomovimento, "status": m.sitcashback, "valor": float(m.vrcashback or 0), "descricao": m.descricao, "observacao": m.observacao, "data": formatar_data_br(m.dtmovimento), "liberacao": formatar_data_br(m.dtliberacao), "validade": formatar_data_br(m.dtvalidade)} for m, nome in movimentos],
    }


@router.get("/resumo")
def resumo(cliente_id: int, loja_id: int, db: Session = Depends(get_db)):
    config = db.query(CashbackConfig).filter(CashbackConfig.loja_id == loja_id).first()
    saldo = atualizar_estados(db, cliente_id, loja_id)
    if saldo:
        db.commit(); db.refresh(saldo)
    movimentos = db.query(CashbackMovimento).filter(CashbackMovimento.cliente_id == cliente_id, CashbackMovimento.loja_id == loja_id).order_by(CashbackMovimento.dtmovimento.desc()).limit(100).all()
    return {
        "ativo": bool(config and config.sitcashback == "ATIVO"),
        "percentual": float(config.pccashback or 0) if config else 0,
        "percentual_maximo_uso": float(config.pcmaxusocompra or 30) if config else 30,
        "saldo_disponivel": float(saldo.vrdisponivel or 0) if saldo else 0,
        "saldo_pendente": float(saldo.vrpendente or 0) if saldo else 0,
        "movimentos": [{"cashback_movimento_id": m.cashback_movimento_id, "tipo": m.tipomovimento, "status": m.sitcashback, "valor": float(m.vrcashback or 0), "descricao": m.descricao, "data": formatar_data_br(m.dtmovimento), "validade": formatar_data_br(m.dtvalidade)} for m in movimentos],
    }


@router.get("/disponivel")
def disponivel(cliente_id: int, loja_id: int, total_compra: float, db: Session = Depends(get_db)):
    config = db.query(CashbackConfig).filter(CashbackConfig.loja_id == loja_id, CashbackConfig.sitcashback == "ATIVO").first()
    saldo = atualizar_estados(db, cliente_id, loja_id)
    if saldo: db.commit(); db.refresh(saldo)
    percentual_limite = dinheiro(config.pcmaxusocompra or 30) if config else dinheiro(30)
    limite = dinheiro(total_compra) * percentual_limite / 100
    valor = min(dinheiro(saldo.vrdisponivel if saldo else 0), dinheiro(limite)) if config else dinheiro(0)
    return {"ativo": bool(config), "saldo_disponivel": float(saldo.vrdisponivel or 0) if saldo else 0, "limite_compra": float(dinheiro(limite)), "valor_utilizavel": float(valor), "percentual_maximo_uso": float(percentual_limite)}
