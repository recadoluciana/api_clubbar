from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Integer, Numeric
from sqlalchemy.sql import func

from app.database import Base


class ReservaIngresso(Base):
    __tablename__ = "reserva_ingresso"

    reserva_ingresso_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id"), nullable=False)
    cliente_id = Column(BigInteger, ForeignKey("cliente.cliente_id"), nullable=False)
    evento_id = Column(BigInteger, ForeignKey("evento.evento_id"), nullable=False)
    lote_id = Column(BigInteger, ForeignKey("eventolote.lote_id"), nullable=False)
    venda_id = Column(BigInteger, ForeignKey("venda.venda_id"), nullable=True)
    qtreservada = Column(Integer, nullable=False)
    vrunitario = Column(Numeric(10, 2), nullable=False)
    pctaxa = Column(Numeric(10, 2), nullable=False, server_default="0")
    vrtaxa = Column(Numeric(10, 2), nullable=False, server_default="0")
    vrtotal = Column(Numeric(10, 2), nullable=False)
    sitreserva = Column(Enum("PREENCHENDO", "AGUARDANDO_PAGAMENTO", "CONFIRMADA", "EXPIRADA", "CANCELADA", name="sitreservaingresso_enum"), nullable=False, server_default="PREENCHENDO")
    dtexpiracao = Column(DateTime, nullable=False)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())
