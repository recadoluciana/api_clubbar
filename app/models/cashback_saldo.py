from sqlalchemy import BigInteger, Column, DateTime, Numeric, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class CashbackSaldo(Base):
    __tablename__ = "cashback_saldo"
    cashback_saldo_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cliente_id = Column(BigInteger, nullable=False)
    organizacao_id = Column(BigInteger, nullable=False)
    loja_id = Column(BigInteger, nullable=False)
    vrdisponivel = Column(Numeric(10, 2), nullable=False, server_default="0")
    vrpendente = Column(Numeric(10, 2), nullable=False, server_default="0")
    dtultatu = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    __table_args__ = (UniqueConstraint("cliente_id", "loja_id", name="uk_cashback_saldo_cliente_loja"),)

