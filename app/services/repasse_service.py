from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.checkout_asaas import CheckoutAsaas
from app.models.lojacontabancaria import LojaContaBancaria
from app.models.repassefinanceiro import RepasseFinanceiro
from app.models.venda import Venda


def _valor(valor: object) -> Decimal:
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def criar_repasse_da_venda(
    db: Session,
    *,
    venda_id: int,
    checkout: CheckoutAsaas,
) -> RepasseFinanceiro:
    existente = db.query(RepasseFinanceiro).filter(
        RepasseFinanceiro.venda_id == venda_id
    ).first()
    if existente:
        return existente

    venda = db.query(Venda).filter(Venda.venda_id == venda_id).first()
    if not venda:
        raise ValueError("Venda não encontrada para criação do repasse")

    conta = db.query(LojaContaBancaria).filter(
        LojaContaBancaria.loja_id == venda.loja_id,
        LojaContaBancaria.status == "ATIVA",
    ).first()
    bruto = _valor(checkout.valor or venda.totalvenda)
    taxa = min(_valor(checkout.vrtaxaclubbar), bruto)

    repasse = RepasseFinanceiro(
        organizacao_id=venda.organizacao_id,
        loja_id=venda.loja_id,
        venda_id=venda.venda_id,
        checkout_asaas_id=checkout.checkout_asaas_id,
        vrbruto=bruto,
        vrtaxaclubbar=taxa,
        vrrepasse=bruto - taxa,
        status="PENDENTE" if conta else "BLOQUEADO",
    )
    if conta:
        for campo in ("codigobanco", "agencia", "nrconta", "digitoconta", "tipoconta", "nmtitular", "cpfcnpjtitular"):
            setattr(repasse, campo, getattr(conta, campo))
    db.add(repasse)
    db.flush()
    return repasse
