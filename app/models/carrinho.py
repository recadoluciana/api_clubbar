from sqlalchemy import Column, BigInteger, DateTime, Enum, String, Numeric
from sqlalchemy.sql import func
from app.database import Base


class Carrinho(Base):
    __tablename__ = "carrinho"

    carrinho_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, nullable=False)
    loja_id = Column(BigInteger, nullable=False)
    cliente_id = Column(BigInteger, nullable=False)

    sitcarrinho = Column(
        Enum("ABERTO", "FECHADO", name="sitcarrinho_enum"),
        nullable=False,
        server_default="ABERTO",
    )

    # PIX pendente reutilizável
    idpixmercadopago = Column(String(80), nullable=True)
    vrpixmercadopago = Column(Numeric(12, 2), nullable=True)

    dtcriacao = Column(
        DateTime,
        server_default=func.current_timestamp(),
        nullable=False,
    )

    dtultatu = Column(
        DateTime,
        nullable=True,
        server_onupdate=func.current_timestamp(),
    )