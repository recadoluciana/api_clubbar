from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Organizacao(Base):
    __tablename__ = "organizacao"

    organizacao_id = Column(BigInteger, primary_key=True, autoincrement=True)

    nmorganizacao = Column(String(120), nullable=False)
    cnpjorganizacao = Column(String(18), nullable=True)
    emailorganizacao = Column(String(255), nullable=True)
    telorganizacao = Column(String(25), nullable=True)

    sitorganizacao = Column(
        String(15),
        nullable=False,
        server_default="ATIVA"
    )

    dtcriacao = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )

    dtultatu = Column(
        DateTime,
        nullable=True,
        server_default=func.now(),
        onupdate=func.now()
    )