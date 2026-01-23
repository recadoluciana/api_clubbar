from sqlalchemy import Column, BigInteger, String
from app.database import Base

class Usuario(Base):
    __tablename__ = "usuario"

    usuario_id = Column(BigInteger, primary_key=True, autoincrement=True)
    nmusuario  = Column(String(100), nullable=True)
