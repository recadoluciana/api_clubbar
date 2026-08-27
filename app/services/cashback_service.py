from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cashback_config import CashbackConfig
from app.models.cashback_movimento import CashbackMovimento
from app.models.cashback_saldo import CashbackSaldo
from app.models.checkout_asaas import CheckoutAsaas
from app.models.itvenda import ItVenda
from app.models.produto import Produto
from app.models.venda import Venda


CENTAVOS = Decimal("0.01")


def dinheiro(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def obter_ou_criar_config(db: Session, organizacao_id: int, loja_id: int, *, ativo: bool = False, percentual=0) -> CashbackConfig:
    config = db.query(CashbackConfig).filter(CashbackConfig.loja_id == loja_id).first()
    if not config:
        config = CashbackConfig(organizacao_id=organizacao_id, loja_id=loja_id, sitcashback="ATIVO" if ativo else "INATIVO", pccashback=dinheiro(percentual), nrdiapliberacao=7, nrdiavalidade=90, permiteusoparcial="S", pcmaxusocompra=Decimal("30.00"))
        db.add(config)
        db.flush()
    return config


def obter_ou_criar_saldo(db: Session, cliente_id: int, organizacao_id: int, loja_id: int, *, bloquear=False) -> CashbackSaldo:
    query = db.query(CashbackSaldo).filter(CashbackSaldo.cliente_id == cliente_id, CashbackSaldo.loja_id == loja_id)
    if bloquear:
        query = query.with_for_update()
    saldo = query.first()
    if not saldo:
        saldo = CashbackSaldo(cliente_id=cliente_id, organizacao_id=organizacao_id, loja_id=loja_id, vrdisponivel=0, vrpendente=0)
        db.add(saldo); db.flush()
    return saldo


def atualizar_estados(db: Session, cliente_id: int, loja_id: int) -> CashbackSaldo | None:
    agora = datetime.now()
    saldo = db.query(CashbackSaldo).filter(CashbackSaldo.cliente_id == cliente_id, CashbackSaldo.loja_id == loja_id).with_for_update().first()
    if not saldo:
        return None
    debitos_expirados = db.query(CashbackMovimento, CheckoutAsaas).join(CheckoutAsaas, CheckoutAsaas.checkout_asaas_id == CashbackMovimento.checkout_asaas_id).filter(CashbackMovimento.cliente_id == cliente_id, CashbackMovimento.loja_id == loja_id, CashbackMovimento.tipomovimento == "DEBITO", CashbackMovimento.sitcashback == "PENDENTE", CheckoutAsaas.venda_id.is_(None), ((CheckoutAsaas.pix_expiration_date.isnot(None) & (CheckoutAsaas.pix_expiration_date <= agora)) | (CheckoutAsaas.status.in_(["CANCELLED", "CANCELED", "EXPIRED"])) | ((CheckoutAsaas.pix_expiration_date.is_(None)) & (CheckoutAsaas.dtcriacao <= agora - timedelta(minutes=10))))).with_for_update().all()
    for debito, _ in debitos_expirados:
        debito.sitcashback = "CANCELADO"
        debito.observacao = "Reserva de cashback expirada"
        saldo.vrdisponivel = dinheiro(saldo.vrdisponivel) + dinheiro(debito.vrcashback)
    liberar = db.query(CashbackMovimento).filter(CashbackMovimento.cliente_id == cliente_id, CashbackMovimento.loja_id == loja_id, CashbackMovimento.tipomovimento == "CREDITO", CashbackMovimento.sitcashback == "PENDENTE", CashbackMovimento.dtliberacao <= agora).with_for_update().all()
    for movimento in liberar:
        movimento.sitcashback = "DISPONIVEL"
        saldo.vrpendente = max(dinheiro(saldo.vrpendente) - dinheiro(movimento.vrcashback), Decimal("0"))
        saldo.vrdisponivel = dinheiro(saldo.vrdisponivel) + dinheiro(movimento.vrcashback)
    expirar = db.query(CashbackMovimento).filter(CashbackMovimento.cliente_id == cliente_id, CashbackMovimento.loja_id == loja_id, CashbackMovimento.tipomovimento == "CREDITO", CashbackMovimento.sitcashback == "DISPONIVEL", CashbackMovimento.dtvalidade <= agora).with_for_update().all()
    for credito in expirar:
        usado = dinheiro(db.query(func.coalesce(func.sum(CashbackMovimento.vrcashback), 0)).filter(CashbackMovimento.cashback_movimento_origem_id == credito.cashback_movimento_id, CashbackMovimento.sitcashback.in_(["PENDENTE", "UTILIZADO"])).scalar())
        restante = max(dinheiro(credito.vrcashback) - usado, Decimal("0"))
        credito.sitcashback = "EXPIRADO"
        saldo.vrdisponivel = max(dinheiro(saldo.vrdisponivel) - restante, Decimal("0"))
    return saldo


def reservar_uso(db: Session, *, cliente_id: int, organizacao_id: int, loja_id: int, total_produtos, valor_solicitado=None, minimo_gateway=5) -> tuple[Decimal, list[CashbackMovimento]]:
    config = db.query(CashbackConfig).filter(CashbackConfig.loja_id == loja_id, CashbackConfig.sitcashback == "ATIVO").first()
    if not config:
        return Decimal("0"), []
    saldo = obter_ou_criar_saldo(db, cliente_id, organizacao_id, loja_id, bloquear=True)
    atualizar_estados(db, cliente_id, loja_id)
    db.refresh(saldo)
    limite = (dinheiro(total_produtos) * dinheiro(config.pcmaxusocompra or 30) / Decimal("100")).quantize(CENTAVOS, rounding=ROUND_DOWN)
    desejado = dinheiro(valor_solicitado) if valor_solicitado is not None else limite
    usar = min(dinheiro(saldo.vrdisponivel), limite, desejado, max(dinheiro(total_produtos) - dinheiro(minimo_gateway), Decimal("0")))
    if usar <= 0:
        return Decimal("0"), []
    creditos = db.query(CashbackMovimento).filter(CashbackMovimento.cliente_id == cliente_id, CashbackMovimento.loja_id == loja_id, CashbackMovimento.tipomovimento == "CREDITO", CashbackMovimento.sitcashback == "DISPONIVEL", CashbackMovimento.dtvalidade > datetime.now()).order_by(CashbackMovimento.dtvalidade, CashbackMovimento.cashback_movimento_id).with_for_update().all()
    restante = usar; debitos = []
    for credito in creditos:
        comprometido = dinheiro(db.query(func.coalesce(func.sum(CashbackMovimento.vrcashback), 0)).filter(CashbackMovimento.cashback_movimento_origem_id == credito.cashback_movimento_id, CashbackMovimento.sitcashback.in_(["PENDENTE", "UTILIZADO"])).scalar())
        disponivel = max(dinheiro(credito.vrcashback) - comprometido, Decimal("0"))
        consumir = min(disponivel, restante)
        if consumir > 0:
            debito = CashbackMovimento(cliente_id=cliente_id, organizacao_id=organizacao_id, loja_id=loja_id, cashback_movimento_origem_id=credito.cashback_movimento_id, tipomovimento="DEBITO", sitcashback="PENDENTE", vrbase=dinheiro(total_produtos), vrcashback=consumir, descricao="Cashback reservado para pagamento")
            db.add(debito); debitos.append(debito); restante -= consumir
        if restante <= 0: break
    usado = usar - restante
    saldo.vrdisponivel = dinheiro(saldo.vrdisponivel) - usado
    return usado, debitos


def vincular_uso_ao_checkout(db: Session, debitos: list[CashbackMovimento], checkout: CheckoutAsaas) -> None:
    for debito in debitos: debito.checkout_asaas_id = checkout.checkout_asaas_id


def cancelar_uso_pendente(db: Session, checkout: CheckoutAsaas) -> None:
    debitos = db.query(CashbackMovimento).filter(CashbackMovimento.checkout_asaas_id == checkout.checkout_asaas_id, CashbackMovimento.tipomovimento == "DEBITO", CashbackMovimento.sitcashback == "PENDENTE").with_for_update().all()
    if not debitos: return
    saldo = db.query(CashbackSaldo).filter(CashbackSaldo.cliente_id == checkout.cliente_id, CashbackSaldo.loja_id == checkout.loja_id).with_for_update().first()
    if not saldo:
        return
    devolvido = sum((dinheiro(d.vrcashback) for d in debitos), Decimal("0"))
    saldo.vrdisponivel = dinheiro(saldo.vrdisponivel) + devolvido
    for debito in debitos:
        debito.sitcashback = "CANCELADO"; debito.observacao = "Reserva liberada sem confirmação do pagamento"


def confirmar_uso(db: Session, checkout: CheckoutAsaas, venda_id: int) -> None:
    for debito in db.query(CashbackMovimento).filter(CashbackMovimento.checkout_asaas_id == checkout.checkout_asaas_id, CashbackMovimento.tipomovimento == "DEBITO", CashbackMovimento.sitcashback == "PENDENTE").with_for_update().all():
        debito.sitcashback = "UTILIZADO"; debito.venda_uso_id = venda_id; debito.dtutilizacao = datetime.now()
        origem = db.query(CashbackMovimento).filter(CashbackMovimento.cashback_movimento_id == debito.cashback_movimento_origem_id).first()
        if origem:
            total_usado = dinheiro(db.query(func.coalesce(func.sum(CashbackMovimento.vrcashback), 0)).filter(CashbackMovimento.cashback_movimento_origem_id == origem.cashback_movimento_id, CashbackMovimento.sitcashback == "UTILIZADO").scalar())
            if total_usado >= dinheiro(origem.vrcashback): origem.sitcashback = "UTILIZADO"


def gerar_cashback_venda(db: Session, venda_id: int) -> CashbackMovimento | None:
    existente = db.query(CashbackMovimento).filter(CashbackMovimento.venda_origem_id == venda_id, CashbackMovimento.tipomovimento == "CREDITO").first()
    if existente: return existente
    venda = db.query(Venda).filter(Venda.venda_id == venda_id).first()
    if not venda or not venda.cliente_id or venda.reserva_ingresso_id is not None: return None
    config = db.query(CashbackConfig).filter(CashbackConfig.loja_id == venda.loja_id, CashbackConfig.sitcashback == "ATIVO").first()
    if not config: return None
    itens = db.query(ItVenda, Produto).join(Produto, Produto.produto_id == ItVenda.produto_id).filter(ItVenda.venda_id == venda_id, ItVenda.tipoitem == "PRODUTO", ItVenda.sititvenda == "ATIVO").all()
    base = sum((dinheiro(item.vrunititvenda) * int(item.qtitvenda or 1) for item, _ in itens), Decimal("0"))
    if base < dinheiro(config.vrmincompra): return None
    valor = sum(((dinheiro(item.vrunititvenda) * int(item.qtitvenda or 1)) * dinheiro(produto.pccashback if produto.pccashback is not None else config.pccashback) / Decimal("100") for item, produto in itens), Decimal("0")).quantize(CENTAVOS)
    if config.vrmaxcashback is not None: valor = min(valor, dinheiro(config.vrmaxcashback))
    if valor <= 0: return None
    agora = datetime.now(); liberacao = agora + timedelta(days=int(config.nrdiapliberacao or 7))
    movimento = CashbackMovimento(cliente_id=venda.cliente_id, organizacao_id=venda.organizacao_id, loja_id=venda.loja_id, venda_origem_id=venda_id, tipomovimento="CREDITO", sitcashback="PENDENTE", pcaplicado=config.pccashback, vrbase=base, vrcashback=valor, descricao=f"Cashback da compra #{venda_id}", dtliberacao=liberacao, dtvalidade=liberacao + timedelta(days=int(config.nrdiavalidade or 90)))
    db.add(movimento)
    saldo = obter_ou_criar_saldo(db, venda.cliente_id, venda.organizacao_id, venda.loja_id, bloquear=True)
    saldo.vrpendente = dinheiro(saldo.vrpendente) + valor
    return movimento


def cancelar_cashback_da_venda(db: Session, venda_id: int) -> None:
    agora = datetime.now()
    venda = db.query(Venda).filter(Venda.venda_id == venda_id).first()
    if not venda or not venda.cliente_id: return
    saldo = obter_ou_criar_saldo(db, venda.cliente_id, venda.organizacao_id, venda.loja_id, bloquear=True)
    for credito in db.query(CashbackMovimento).filter(CashbackMovimento.venda_origem_id == venda_id, CashbackMovimento.tipomovimento == "CREDITO", CashbackMovimento.sitcashback.in_(["PENDENTE", "DISPONIVEL"])).with_for_update().all():
        if credito.sitcashback == "PENDENTE": saldo.vrpendente = max(dinheiro(saldo.vrpendente) - dinheiro(credito.vrcashback), Decimal("0"))
        else:
            usado = dinheiro(db.query(func.coalesce(func.sum(CashbackMovimento.vrcashback), 0)).filter(CashbackMovimento.cashback_movimento_origem_id == credito.cashback_movimento_id, CashbackMovimento.sitcashback == "UTILIZADO").scalar())
            saldo.vrdisponivel = max(dinheiro(saldo.vrdisponivel) - max(dinheiro(credito.vrcashback) - usado, Decimal("0")), Decimal("0"))
        credito.sitcashback = "CANCELADO"
    for debito in db.query(CashbackMovimento).filter(CashbackMovimento.venda_uso_id == venda_id, CashbackMovimento.tipomovimento == "DEBITO", CashbackMovimento.sitcashback == "UTILIZADO").with_for_update().all():
        origem = db.query(CashbackMovimento).filter(CashbackMovimento.cashback_movimento_id == debito.cashback_movimento_origem_id).with_for_update().first()
        debito.sitcashback = "CANCELADO"
        if origem and origem.sitcashback != "CANCELADO" and origem.dtvalidade and origem.dtvalidade > agora:
            origem.sitcashback = "DISPONIVEL"
            saldo.vrdisponivel = dinheiro(saldo.vrdisponivel) + dinheiro(debito.vrcashback)
