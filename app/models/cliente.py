from sqlalchemy import Column, BigInteger, String, DateTime, text
from app.database import Base

class Cliente(Base):
    __tablename__ = "cliente"

    cliente_id   = Column(BigInteger, primary_key=True, index=True,autoincrement=True)
    nmcliente    = Column(String(120), nullable=False)
    emailcliente = Column(String(160), nullable=False, unique=True)
    senhahashcli = Column(String(255), nullable=False)
    sitcliente   = Column(String(15), nullable=False, server_default=text("'ATIVO'"))
    emailconf    = Column(String(1), nullable=False, server_default=text("'N'"))
    dtcriacao    = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu     = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))
    nrtelcliente = Column(String(15), nullable=True)
    nrcpfcliente = Column(String(15), nullable=True)
    idclienteasaas = Column(String(100), nullable=True)
    endcliente = Column(String(150), nullable=True)
    nrendcliente = Column(String(20), nullable=True)
    complcliente = Column(String(80), nullable=True)
    bairrocliente = Column(String(80), nullable=True)
    cepcliente = Column(String(10), nullable=True)
    cidadecliente = Column(String(100), nullable=True)
    ufcliente = Column(String(2), nullable=True)
    idcidadeibge = Column(BigInteger, nullable=True)