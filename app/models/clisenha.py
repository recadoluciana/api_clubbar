# app/models/clisenha.py

from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey
from app.database import Base


class CliSenha(Base):
    __tablename__ = "clisenha"

    clisenha_id = Column(BigInteger, primary_key=True, autoincrement=True)

    cliente_id = Column(
        BigInteger,
        ForeignKey("cliente.cliente_id", ondelete="CASCADE"),
        nullable=False,
    )

    codigo = Column(String(10), nullable=False)
    expiracao = Column(DateTime, nullable=False)
    usado = Column(String(1), nullable=False, default="N")
    dtcriacao = Column(DateTime, nullable=False)