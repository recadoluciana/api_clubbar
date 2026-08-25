from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, text
from sqlalchemy.sql import func

from app.database import Base


class Organizacao(Base):
    __tablename__ = 'organizacao'

    organizacao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    nmorganizacao = Column(String(120), nullable=False, index=True)
    nmresponsavelprincipal = Column(String(120), nullable=True)
    emailorganizacao = Column(String(255), nullable=False)
    telorganizacao = Column(String(25), nullable=False)
    tipooperacao = Column(String(30), nullable=True)
    sitorganizacao = Column(
        String(15), nullable=False, server_default=text('ATIVA'), index=True
    )
    leadparceiro_id = Column(
        BigInteger,
        ForeignKey(
            'leadparceiro.leadparceiro_id',
            ondelete='RESTRICT',
            onupdate='RESTRICT',
        ),
        nullable=True,
        unique=True,
        index=True,
    )
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.now())
