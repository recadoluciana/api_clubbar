from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.sql import func

from app.database import Base


class CampanhaPromocional(Base):
    __tablename__ = 'campanha_promocional'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    loja_id = Column(BigInteger, ForeignKey('loja.loja_id', ondelete='RESTRICT'), nullable=False, index=True)
    titulo = Column(String(100), nullable=False)
    mensagem = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, server_default='RASCUNHO')
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    criado_por = Column(BigInteger, ForeignKey('usuario.usuario_id', ondelete='SET NULL'), nullable=True)
