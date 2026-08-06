from sqlalchemy import BigInteger, Column, DateTime, String, func
from app.database import Base


class Operador(Base):
    __tablename__ = "operador"
    operador_id = Column(BigInteger, primary_key=True, autoincrement=True)
    nmoperador = Column(String(200), nullable=False)
    emailoperador = Column(String(200), nullable=False, unique=True, index=True)
    senhahashoperador = Column(String(255), nullable=False)
    perfil = Column(String(30), nullable=False, default="ADMIN")
    sitoperador = Column(String(15), nullable=False, default="ATIVO")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())
