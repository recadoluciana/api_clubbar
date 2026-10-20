from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.sql import func

from app.database import Base


class BeneficioProdutoCampanha(Base):
    """Campanhas comerciais independentes da versão publicada do cardápio."""
    __tablename__ = "beneficioprodutocampanha"

    beneficioprodutocampanha_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False, index=True)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id"), nullable=False, index=True)
    produto_id = Column(BigInteger, ForeignKey("produto.produto_id"), nullable=False, index=True)
    tipo = Column(String(20), nullable=False)  # CORTESIA | ROLETA | PACOTE
    nmcampanha = Column(String(120), nullable=False)
    dthrinicio = Column(DateTime, nullable=False)
    dthrfim = Column(DateTime, nullable=False)
    qtlimite = Column(Integer, nullable=True)
    limite_cliente_dia = Column(Integer, nullable=False, default=1)
    # Usado somente em campanhas do tipo PACOTE. Ex.: 3 cervejas por R$ 40.
    qtitenspacote = Column(Integer, nullable=True)
    vrpacote = Column(Numeric(10, 2), nullable=True)
    situacao = Column(String(20), nullable=False, default="ATIVA")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())


class BeneficioProdutoResgate(Base):
    __tablename__ = "beneficioprodutoresgate"

    beneficioprodutoresgate_id = Column(BigInteger, primary_key=True, autoincrement=True)
    campanha_id = Column(BigInteger, ForeignKey("beneficioprodutocampanha.beneficioprodutocampanha_id"), nullable=False, index=True)
    cliente_id = Column(BigInteger, ForeignKey("cliente.cliente_id"), nullable=False, index=True)
    produto_id = Column(BigInteger, ForeignKey("produto.produto_id"), nullable=False, index=True)
    percentual_desconto = Column(Numeric(5, 2), nullable=False, default=0)
    situacao = Column(String(20), nullable=False, default="DISPONIVEL")
    dtresgate = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtexpiracao = Column(DateTime, nullable=True)
    venda_id = Column(BigInteger, ForeignKey("venda.venda_id"), nullable=True, index=True)
