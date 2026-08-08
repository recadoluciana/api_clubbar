from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, Numeric, String, Text, text

from app.database import Base


class RepasseFinanceiro(Base):
    __tablename__ = "repassefinanceiro"

    repassefinanceiro_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id"), nullable=False)
    venda_id = Column(BigInteger, ForeignKey("venda.venda_id"), nullable=False, unique=True)
    checkout_asaas_id = Column(BigInteger, ForeignKey("checkout_asaas.checkout_asaas_id"), nullable=True)
    vrbruto = Column(Numeric(10, 2), nullable=False)
    vrtaxaclubbar = Column(Numeric(10, 2), nullable=False, server_default="0")
    vrrepasse = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False, server_default=text("'PENDENTE'"))
    dtprevista = Column(Date, nullable=True)
    dtpagamento = Column(DateTime, nullable=True)
    idtransferencia = Column(String(100), nullable=True)
    urlcomprovante = Column(String(500), nullable=True)
    observacao = Column(Text, nullable=True)
    codigobanco = Column(String(10), nullable=True)
    agencia = Column(String(20), nullable=True)
    nrconta = Column(String(30), nullable=True)
    digitoconta = Column(String(5), nullable=True)
    tipoconta = Column(String(20), nullable=True)
    nmtitular = Column(String(150), nullable=True)
    cpfcnpjtitular = Column(String(20), nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))
