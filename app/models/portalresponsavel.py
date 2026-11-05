"""Contas de pessoas e vínculos com cadastros de parceiros no portal."""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint, text
from app.database import Base


class PortalResponsavel(Base):
    __tablename__ = "portalresponsavel"
    portalresponsavel_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cpf = Column(String(11), nullable=False, unique=True, index=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(160), nullable=False)
    senha_hash = Column(String(255), nullable=False)
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class PortalResponsavelLead(Base):
    __tablename__ = "portalresponsavel_lead"
    __table_args__ = (UniqueConstraint("portalresponsavel_id", "leadparceiro_id", name="uk_portalresponsavel_lead"),)
    portalresponsavel_lead_id = Column(BigInteger, primary_key=True, autoincrement=True)
    portalresponsavel_id = Column(BigInteger, ForeignKey("portalresponsavel.portalresponsavel_id"), nullable=False, index=True)
    leadparceiro_id = Column(BigInteger, ForeignKey("leadparceiro.leadparceiro_id"), nullable=False, index=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class PortalRecuperacaoSenha(Base):
    __tablename__ = "portalrecuperacao_senha"
    portalrecuperacao_senha_id = Column(BigInteger, primary_key=True, autoincrement=True)
    portalresponsavel_id = Column(BigInteger, ForeignKey("portalresponsavel.portalresponsavel_id"), nullable=False, index=True)
    codigo_hash = Column(String(255), nullable=False)
    expiracao = Column(DateTime, nullable=False)
    tentativas = Column(BigInteger, nullable=False, server_default="0")
    usado = Column(String(1), nullable=False, server_default="N")
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
