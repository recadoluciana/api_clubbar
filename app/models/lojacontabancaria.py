from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint, text

from app.database import Base


class LojaContaBancaria(Base):
    __tablename__ = "lojacontabancaria"

    lojacontabancaria_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id", ondelete="CASCADE"), nullable=False)
    codigobanco = Column(String(10), nullable=False)
    nmbanco = Column(String(100), nullable=True)
    agencia = Column(String(20), nullable=False)
    nrconta = Column(String(30), nullable=False)
    digitoconta = Column(String(5), nullable=True)
    tipoconta = Column(String(20), nullable=False, server_default=text("'CORRENTE'"))
    nmtitular = Column(String(150), nullable=False)
    cpfcnpjtitular = Column(String(20), nullable=False)
    chavepix = Column(String(150), nullable=True)
    tipochavepix = Column(String(20), nullable=True)
    status = Column(String(15), nullable=False, server_default=text("'ATIVA'"))
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (UniqueConstraint("loja_id", name="uq_lojacontabancaria_loja"),)
