from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.sql import func
from app.database import Base


class CashbackMovimento(Base):
    __tablename__ = "cashback_movimento"
    cashback_movimento_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cliente_id = Column(BigInteger, nullable=False)
    organizacao_id = Column(BigInteger, nullable=False)
    loja_id = Column(BigInteger, nullable=False)
    venda_origem_id = Column(BigInteger, ForeignKey("venda.venda_id"), nullable=True)
    venda_uso_id = Column(BigInteger, ForeignKey("venda.venda_id"), nullable=True)
    checkout_asaas_id = Column(BigInteger, ForeignKey("checkout_asaas.checkout_asaas_id"), nullable=True)
    cashback_movimento_origem_id = Column(BigInteger, ForeignKey("cashback_movimento.cashback_movimento_id"), nullable=True)
    tipomovimento = Column(String(15), nullable=False)
    sitcashback = Column(String(15), nullable=False)
    pcaplicado = Column(Numeric(10, 2), nullable=False, server_default="0")
    vrbase = Column(Numeric(10, 2), nullable=False, server_default="0")
    vrcashback = Column(Numeric(10, 2), nullable=False, server_default="0")
    descricao = Column(String(255), nullable=True)
    observacao = Column(String(500), nullable=True)
    dtmovimento = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtliberacao = Column(DateTime, nullable=True)
    dtvalidade = Column(DateTime, nullable=True)
    dtutilizacao = Column(DateTime, nullable=True)

