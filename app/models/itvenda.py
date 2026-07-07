# app/models/itvenda.py
from sqlalchemy import (
    BigInteger, Column, DateTime, Enum, ForeignKey, Integer, Numeric, String,Date
)
from sqlalchemy.sql import func

from datetime import datetime, timedelta

from app.database import Base


class ItVenda(Base):
    __tablename__ = "itvenda"

    itvenda_id = Column(BigInteger, primary_key=True, autoincrement=True)

    venda_id = Column(BigInteger, ForeignKey("venda.venda_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    produto_id = Column(BigInteger, ForeignKey("produto.produto_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)

    qtitvenda = Column(Integer, nullable=False, server_default="1")
    vrunititvenda = Column(Numeric(10, 2), nullable=False)

    identregaitvenda = Column(Enum("SIM", "NAO", name="identregaitvenda_enum"), nullable=False, server_default="NAO")
    dtentregaitvenda = Column(DateTime, nullable=True)

    userentregaitvenda = Column(BigInteger, ForeignKey("usuario.usuario_id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    nmuserentregaitvenda = Column(String(100), nullable=True)

    dsobsitvenda = Column(String(255), nullable=True)
    qrtokenitvenda = Column(String(120), nullable=True)

    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    dtexpiraitvenda = Column(Date, nullable=True)
    
    nmparticipante = Column(String(150), nullable=True)
    cpfparticipante = Column(String(11), nullable=True)
    lote_id = Column(BigInteger, ForeignKey("eventolote.lote_id"), nullable=True)

    pctaxaingitvenda = Column(DECIMAL(10, 2), default=0)
    vrtaxaingitvenda = Column(DECIMAL(10, 2), default=0)
    vrtotalcomtaxaitvenda = Column(DECIMAL(10, 2), default=0)