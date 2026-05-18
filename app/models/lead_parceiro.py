#lead_parceiro.py
from sqlalchemy import Column, BigInteger, String, DateTime, Text, text
from app.database import Base


class LeadParceiro(Base):
    __tablename__ = "lead_parceiro"

    lead_parceiro_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)

    nome_responsavel = Column(String(120), nullable=False)
    nome_estabelecimento = Column(String(160), nullable=False)
    tipo = Column(String(30), nullable=False)

    telefone = Column(String(30), nullable=False)
    email = Column(String(160), nullable=False)
    cidade = Column(String(120), nullable=False)

    mensagem = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, server_default=text("'NOVO'"))

    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))