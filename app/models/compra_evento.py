from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.sql import func

from app.database import Base


class CompraEvento(Base):
    __tablename__ = "compra_evento"

    compra_evento_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id"), nullable=False)
    cliente_id = Column(BigInteger, ForeignKey("cliente.cliente_id"), nullable=False)
    evento_id = Column(BigInteger, ForeignKey("evento.evento_id"), nullable=False)
    venda_id = Column(BigInteger, ForeignKey("venda.venda_id"), nullable=True, index=True)
    status = Column(Enum("ABERTA", "AGUARDANDO_PAGAMENTO", "PAGA", "EXPIRADA", "CANCELADA", name="compra_evento_status_enum"), nullable=False, server_default="ABERTA")
    valor_total = Column(Numeric(10, 2), nullable=False, server_default="0")
    dtexpiracao = Column(DateTime, nullable=False)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())


class CompraEventoItem(Base):
    __tablename__ = "compra_evento_item"

    compra_evento_item_id = Column(BigInteger, primary_key=True, autoincrement=True)
    compra_evento_id = Column(BigInteger, ForeignKey("compra_evento.compra_evento_id", ondelete="CASCADE"), nullable=False, index=True)
    tipoitem = Column(Enum("INGRESSO", "PRODUTO", name="compra_evento_tipoitem_enum"), nullable=False)
    reserva_ingresso_id = Column(BigInteger, ForeignKey("reserva_ingresso.reserva_ingresso_id"), nullable=True, index=True)
    produto_id = Column(BigInteger, ForeignKey("produto.produto_id"), nullable=True, index=True)
    quantidade = Column(BigInteger, nullable=False, server_default="1")
    valor_unitario = Column(Numeric(10, 2), nullable=False)
    valor_taxa = Column(Numeric(10, 2), nullable=False, server_default="0")
    subtotal = Column(Numeric(10, 2), nullable=False)
    descricao_snapshot = Column(String(255), nullable=True)
