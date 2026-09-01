#leadmensagem.py
from sqlalchemy import BigInteger, CHAR, Column, DateTime, Enum, ForeignKey, Text
from sqlalchemy.sql import func

from app.database import Base


class LeadMensagem(Base):
    __tablename__ = "leadmensagem"

    leadmensagem_id = Column(BigInteger, primary_key=True, autoincrement=True)
    leadparceiro_id = Column(
        BigInteger,
        ForeignKey("leadparceiro.leadparceiro_id"),
        nullable=False,
        index=True,
    )
    leadestabelecimento_id = Column(
        BigInteger,
        ForeignKey("leadestabelecimento.leadestabelecimento_id"),
        nullable=False,
        index=True,
    )
    origem = Column(
        Enum("CLUBBAR", "LEAD", name="enum_leadmensagem_origem"),
        nullable=False,
    )
    mensagem = Column(Text, nullable=False)
    lida = Column(CHAR(1), nullable=False, server_default="N")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
