from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class EnvioCampanhaPromocional(Base):
    __tablename__ = 'envio_campanha_promocional'
    __table_args__ = (UniqueConstraint('campanha_id', 'destinatario_chave', name='uq_envio_campanha_destinatario'),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    campanha_id = Column(BigInteger, ForeignKey('campanha_promocional.id', ondelete='CASCADE'), nullable=False, index=True)
    cliente_id = Column(BigInteger, ForeignKey('cliente.cliente_id', ondelete='CASCADE'), nullable=False)
    dispositivo_id = Column(BigInteger, ForeignKey('dispositivo_promocao.id', ondelete='SET NULL'), nullable=True)
    destinatario_chave = Column(String(80), nullable=False)
    canal = Column(String(12), nullable=False)
    status = Column(String(20), nullable=False, server_default='PENDENTE')
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
