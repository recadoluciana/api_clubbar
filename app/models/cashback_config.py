from sqlalchemy import BigInteger, Column, DateTime, Integer, Numeric, String
from sqlalchemy.sql import func
from app.database import Base


class CashbackConfig(Base):
    __tablename__ = "cashback_config"
    cashback_config_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, nullable=False)
    loja_id = Column(BigInteger, nullable=False, unique=True)
    sitcashback = Column(String(10), nullable=False, server_default="ATIVO")
    pccashback = Column(Numeric(10, 2), nullable=False, server_default="0")
    vrmincompra = Column(Numeric(10, 2), nullable=False, server_default="0")
    vrmaxcashback = Column(Numeric(10, 2), nullable=True)
    nrdiapliberacao = Column(Integer, nullable=False, server_default="7")
    nrdiavalidade = Column(Integer, nullable=False, server_default="90")
    permiteusoparcial = Column(String(1), nullable=False, server_default="S")
    pcmaxusocompra = Column(Numeric(10, 2), nullable=False, server_default="30")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

