from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, UniqueConstraint, func

from app.database import Base


class Manual(Base):
    __tablename__ = "manualguia"
    manual_id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(60), nullable=False, unique=True)
    ordem = Column(Integer, nullable=False, default=0)


class ManualVersao(Base):
    __tablename__ = "manualversao"
    __table_args__ = (UniqueConstraint("manual_id", "versao", name="uq_manual_versao"),)
    manualversao_id = Column(Integer, primary_key=True, autoincrement=True)
    manual_id = Column(Integer, ForeignKey("manualguia.manual_id"), nullable=False)
    versao = Column(Integer, nullable=False)
    titulo = Column(String(160), nullable=False)
    descricao = Column(Text, nullable=False)
    etapas = Column(JSON, nullable=False)
    resumo_alteracao = Column(String(500), nullable=False)
    operador_id = Column(Integer, nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
