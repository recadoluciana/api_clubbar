from sqlalchemy import BigInteger, CHAR, Column, DateTime, Enum, ForeignKey, Text
from sqlalchemy.sql import func

from app.database import Base


class CoraMensagem(Base):
    __tablename__ = "coramensagem"

    coramensagem_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cliente_id = Column(
        BigInteger,
        ForeignKey("cliente.cliente_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    coraduvida_id = Column(
        BigInteger,
        ForeignKey("coraduvida.coraduvida_id", ondelete="SET NULL"),
        nullable=True,
    )
    origem = Column(
        Enum("CLIENTE", "CORA", name="enum_coramensagem_origem"),
        nullable=False,
    )
    mensagem = Column(Text, nullable=False)
    lida = Column(CHAR(1), nullable=False, server_default="N")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now(), index=True)
