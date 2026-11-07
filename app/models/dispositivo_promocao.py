from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class DispositivoPromocao(Base):
    __tablename__ = "dispositivo_promocao"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_dispositivo_promocao_token"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    cliente_id = Column(BigInteger, ForeignKey("cliente.cliente_id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False)
    token = Column(String(4096), nullable=False)
    plataforma = Column(String(10), nullable=False)
    atualizado_em = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
