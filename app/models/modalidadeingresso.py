from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.sql import func

from app.database import Base


class ModalidadeIngresso(Base):
    __tablename__ = "modalidadeingresso"

    modalidade_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id", ondelete="RESTRICT"), nullable=True, index=True)
    cdmodalidade = Column(String(40), nullable=False, unique=True)
    nmmodalidade = Column(String(100), nullable=False)
    tipomodalidade = Column(String(20), nullable=False, server_default="COMERCIAL")
    aplicacotalegal = Column(Boolean, nullable=False, server_default="0")
    exigebeneficio = Column(Boolean, nullable=False, server_default="0")
    exigecomprovante = Column(Boolean, nullable=False, server_default="0")
    permitepersonalizarnome = Column(Boolean, nullable=False, server_default="1")
    situacao = Column(String(10), nullable=False, server_default="ATIVO")
    nrordem = Column(BigInteger, nullable=False, server_default="1")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())
