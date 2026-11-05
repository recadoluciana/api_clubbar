#leadacesso.py
from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class LeadAcesso(Base):
    __tablename__ = "leadacesso"

    leadacesso_id = Column(BigInteger, primary_key=True, autoincrement=True)
    leadparceiro_id = Column(
        BigInteger,
        ForeignKey("leadparceiro.leadparceiro_id"),
        nullable=False,
        index=True,
    )
    tokenhash = Column(String(64), nullable=False, unique=True, index=True)
    dtvalidade = Column(DateTime, nullable=False)
    dtultimoacesso = Column(DateTime, nullable=True)
    revogado = Column(CHAR(1), nullable=False, server_default="N")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())


class LeadCodigoAcesso(Base):
    __tablename__ = "leadcodigo_acesso"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    leadparceiro_id = Column(BigInteger, ForeignKey("leadparceiro.leadparceiro_id"), nullable=False, index=True)
    documento = Column(String(14), nullable=False, index=True)
    codigo_hash = Column(String(255), nullable=False)
    expiracao = Column(DateTime, nullable=False)
    tentativas = Column(Integer, nullable=False, default=0, server_default="0")
    usado = Column(CHAR(1), nullable=False, default="N", server_default="N")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
