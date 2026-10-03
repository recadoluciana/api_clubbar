from sqlalchemy import BigInteger, Boolean, Column, DateTime, String
from sqlalchemy.sql import func

from app.database import Base


class BeneficioIngresso(Base):
    __tablename__ = "beneficioingresso"

    beneficio_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cdbeneficio = Column(String(40), nullable=False, unique=True)
    nmbeneficio = Column(String(100), nullable=False)
    exigecomprovante = Column(Boolean, nullable=False, server_default="1")
    situacao = Column(String(10), nullable=False, server_default="ATIVO")
    nrordem = Column(BigInteger, nullable=False, server_default="1")
    dtiniciovigencia = Column(DateTime, nullable=True)
    dtfimvigencia = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())
