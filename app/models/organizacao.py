from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.sql import func
from app.database import Base

class Organizacao(Base):
    __tablename__ = "organizacao"

    organizacao_id = Column(BigInteger, primary_key=True, index=True)
    nmorganizacao = Column(String(120), nullable=False)
    cnpjorganizacao = Column(String(18))
    emailorganizacao = Column(String(255))
    telorganizacao = Column(String(25))
    sitorganizacao = Column(String(15))

    dtcriacao = Column(DateTime, server_default=func.now(), nullable=False)
    dtultatu = Column(DateTime, onupdate=func.now())
