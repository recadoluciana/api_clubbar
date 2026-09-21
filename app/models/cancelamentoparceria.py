from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.sql import func
from app.database import Base


class CancelamentoParceria(Base):
    __tablename__ = 'cancelamentoparceria'
    cancelamentoparceria_id = Column(BigInteger, primary_key=True, autoincrement=True)
    loja_id = Column(BigInteger, ForeignKey('loja.loja_id', ondelete='RESTRICT'), nullable=False, unique=True, index=True)
    justificativa = Column(Text, nullable=False)
    dtsolicitacao = Column(DateTime, nullable=False, server_default=func.now())
    dtavisoate = Column(DateTime, nullable=False)
    sitcancelamento = Column(String(20), nullable=False, server_default='SOLICITADO')
