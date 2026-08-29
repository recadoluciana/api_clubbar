from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.sql import func

from app.database import Base


class TitularFinanceiro(Base):
    __tablename__ = "titularfinanceiro"

    titularfinanceiro_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False, index=True)
    tipotitular = Column(String(2), nullable=False)
    cpfcnpj = Column(String(14), nullable=False)
    nmrazaosocial = Column(String(160), nullable=False)
    nmfantasia = Column(String(160), nullable=True)
    dtnascimento = Column(Date, nullable=True)
    email = Column(String(255), nullable=False)
    telefone = Column(String(25), nullable=False)
    cep = Column(String(9), nullable=False)
    endereco = Column(String(255), nullable=False)
    numero = Column(String(20), nullable=False)
    complemento = Column(String(120), nullable=True)
    bairro = Column(String(120), nullable=False)
    cidade_id = Column(BigInteger, ForeignKey("cidade.cidade_id"), nullable=False)
    estado_id = Column(BigInteger, ForeignKey("estado.estado_id"), nullable=False)
    vrfaturamentomensal = Column(Numeric(12, 2), nullable=False, default=0)
    asaas_account_id = Column(String(100), nullable=True)
    asaas_wallet_id = Column(String(100), nullable=True)
    asaas_api_key_criptografada = Column(Text, nullable=True)
    status_asaas = Column(String(30), nullable=False, default="NAO_INICIADO")
    onboarding_url = Column(Text, nullable=True)
    dtultimaverificacao = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
